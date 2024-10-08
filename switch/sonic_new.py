import json
from sbi.rest import RestSbi
from sbi.paramiko_sbi import ParamikoSbi
from .switch_base import Switch
from models import LldpNeighbor, PhyPort, VlanL3Port, Vrf, SwitchRequestVlanL3Port, VrfRequest, IpV4Route
from switch.sonic_portchannel_model import SonicPortchannelSonicPortchannel
from switch.sonic_port_model import SonicPortSonicPort
from switch.sonic_vlan_model import SonicVlanSonicVlan, TaggingMode, PostListSonicVlanList, SonicVlanListItem, \
    SonicVlanMemberListItem, SonicVlanMemberList
from switch.sonic_vlan_itf_model import SonicVlanInterfaceSonicVlanInterface, PostListSonicVlanInterface, \
    SonicVlanInterfaceListItem, SonicVlanInterfaceIPAddrListItem
from switch.sonic_vrf_model import SonicVrfSonicVrf, SonicVrfListItem
from switch.sonic_lldp_model import SonicLLDPMsg
from ipaddress import IPv4Network
from utils import create_logger
from typing import List, Literal
import requests
from sbi.frr_vtysh import FrrConfig

logger = create_logger('sonic')
RESTPATH = 'restconf/data'


class SonicNew(Switch):
    # double sbi driver to access to the FRR routing suite, while using REST for Sonic native info
    _sbi_rest_driver: RestSbi = None
    _sbi_ssh_driver: ParamikoSbi = None

    def _update_info(self):
        cfg = dict()
        cfg.update(self.retrieve_ports())
        cfg.update(self.retrieve_vlans())
        cfg.update(self.retrieve_vrf())
        routing_config = self.retrieve_routing()
        logger.debug("routing_config: {}".format(routing_config))
        self.retrieve_neighbors()
        self.store_config(json.dumps(cfg))

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_rest_driver:
            device = self.to_device_model().model_copy(update={'model': 'sonic'})
            self._sbi_rest_driver = RestSbi(device)
        if not self._sbi_ssh_driver:
            ssh_device = self.to_device_model().model_copy(update={'model': 'sonic'})
            self._sbi_ssh_driver = ParamikoSbi(ssh_device)

    def _retrieve_info(self):
        self.reinit_sbi_drivers()
        self.update_info()

    def retrieve_routing(self) -> dict:
        msg = self._sbi_ssh_driver.send_command(commands=["vtysh -c \"show running-config\""], json_parse=False)
        frr_obj = FrrConfig.from_raw_config(msg[0]['_stdout'])

        frr_vrfs = frr_obj.to_switch_vrf_protocols()
        for frr_vrf_name in frr_vrfs.keys():
            switch_vrf = next((item for item in self.vrfs if item.name == frr_vrf_name), None)
            if not switch_vrf:
                raise ValueError("Vrf {} not found on the switch".format(frr_vrf_name))
            switch_vrf.protocols = frr_vrfs[frr_vrf_name]

    def retrieve_neighbors(self):
        rest_lldp = SonicLLDPMsg.model_validate(
            self._sbi_rest_driver.get("{}/openconfig-lldp:lldp/interfaces".format(RESTPATH)))
        for neigh_item in rest_lldp.openconfig_lldp_interfaces.interface:
            phy_port = next((item for item in self.phy_ports if item.name == neigh_item.name), None)
            if not phy_port:
                logger.warning("Phyport {} not found".format(neigh_item.name))
                continue

            neigh_info = neigh_item.neighbors.neighbor[0] if len(neigh_item.neighbors.neighbor) > 0 else None
            if not neigh_info:
                logger.warning("No neighbour information for interface {}".format(neigh_item.name))
                continue
            logger.debug("Found neighbour {} remote port {} on local port {}".format(
                neigh_info.state.system_name, neigh_info.state.port_description, phy_port.name))
            phy_port.neighbor = LldpNeighbor.model_validate({
                'neighbor': neigh_info.state.system_name,
                'remote_interface': neigh_info.state.port_description
            })

    def retrieve_vlans(self) -> dict:
        rest_vlan = SonicVlanSonicVlan.model_validate(
            self._sbi_rest_driver.get('{}/sonic-vlan:sonic-vlan'.format(RESTPATH)))
        for vlan_item in rest_vlan.sonic_vlan_sonic_vlan.VLAN.VLAN_LIST:
            self.vlans.append(int(vlan_item.vlanid))

        for vlan_member_item in rest_vlan.sonic_vlan_sonic_vlan.VLAN_MEMBER.VLAN_MEMBER_LIST:
            vid = next((item.vlanid for item in rest_vlan.sonic_vlan_sonic_vlan.VLAN.VLAN_LIST if \
                        item.name == vlan_member_item.name), None)
            if not vid:
                raise ValueError("Vlan {} not found in the VLAN list".format(vlan_member_item.name))
            itf = next((item for item in self.phy_ports if item.name == vlan_member_item.ifname), None)
            if not itf:
                raise ValueError("Phy Port with name {} not found".format(vlan_member_item.ifname))
            if vlan_member_item.tagging_mode == TaggingMode.untagged:
                itf.access_vlan = int(vid)
            elif vlan_member_item.tagging_mode == TaggingMode.tagged and vid not in itf.trunk_vlans:
                itf.trunk_vlans.append(vid)
            else:
                raise ValueError("Tagging mode {} not supported".format(vlan_member_item.tagging_mode))

        rest_vlan_itf = SonicVlanInterfaceSonicVlanInterface.model_validate(
            self._sbi_rest_driver.get('{}/sonic-vlan-interface:sonic-vlan-interface'.format(RESTPATH))
        )

        for vlan_itf in rest_vlan_itf.sonic_vlan_interface_sonic_vlan_interface.VLAN_INTERFACE.VLAN_INTERFACE_LIST:
            # find vlan id from vlan name
            vid = next((item.vlanid for item in rest_vlan.sonic_vlan_sonic_vlan.VLAN.VLAN_LIST if \
                        item.name == vlan_itf.vlanName), None)
            ip_item = next(
                (item for item in
                 rest_vlan_itf.sonic_vlan_interface_sonic_vlan_interface.VLAN_INTERFACE.VLAN_INTERFACE_IPADDR_LIST if
                 item.vlanName == vlan_itf.vlanName), None)

            if ip_item:
                ip_addr = ip_item.ip_prefix.split('/')[0]
                cidr = str(IPv4Network(ip_item.ip_prefix, strict=False))
            else:
                ip_addr = None
                cidr = None

            self.vlan_l3_ports.append(
                VlanL3Port.model_validate(
                    {
                        'index': vlan_itf.vlanName,
                        'name': vlan_itf.vlanName,
                        'vlan': int(vid),
                        'ipaddress': ip_addr,
                        'cidr': cidr,
                        'vrf': vlan_itf.vrf_name,
                        'description': None
                    }
                )
            )
        cfg = json.loads(rest_vlan.sonic_vlan_sonic_vlan.model_dump_json(by_alias=True))
        cfg.update(json.loads(rest_vlan_itf.sonic_vlan_interface_sonic_vlan_interface.model_dump_json(by_alias=True)))
        return cfg

    def retrieve_ports(self) -> dict:
        port_channels = {}
        rest_portchannel = SonicPortchannelSonicPortchannel.model_validate(
            self._sbi_rest_driver.get('{}/sonic-portchannel:sonic-portchannel'.format(RESTPATH)))

        logger.debug('checking portchannels')
        for member in rest_portchannel.sonic_portchannel_sonic_portchannel.PORTCHANNEL_MEMBER.PORTCHANNEL_MEMBER_LIST:
            port_channels[member.ifname] = member.name  # name is the one of port channel

        rest_port = SonicPortSonicPort.model_validate(self._sbi_rest_driver.get(
            '{}/sonic-port:sonic-port'.format(RESTPATH)))

        try:

            alternative_rest_ports = requests.get("http://{}:8123/interfaces_status".format(self.address))
            if not alternative_rest_ports.ok:
                logger.error(alternative_rest_ports.text)
                raise ValueError("ALTERNATIVE REST error!")
        except requests.HTTPError as ex:
            raise ex
        except:
            raise ValueError("ALTERNATIVE REST error!")
        alternative_ports_state = alternative_rest_ports.json()
        # port_status_res = {}
        for itf in rest_port.sonic_port_sonic_port.PORT.PORT_LIST:
            # port_status_res[itf.ifname] = {'vlan': 'NA', 'oper': 'NA', 'admin': 'NA', 'speed': 'NA'}
            is_in_port_channel = itf.ifname in port_channels.keys()
            port_name = port_channels[itf.ifname] if is_in_port_channel else itf.ifname

            # ADD here code for dynamic state info
            match alternative_ports_state[port_name]['vlan']:
                case 'routed':
                    pmode = 'ROUTED'
                case 'trunk':
                    pmode = 'TRUNK'
                case 'access':
                    pmode = 'ACCESS'
                case _:
                    pmode = 'NA'
            logger.debug("adding port {} with index {}".format(port_name, str(itf.index)))
            self.phy_ports.append(
                PhyPort(
                    index=str(itf.index),
                    name=port_name,
                    trunk_vlans=[],
                    access_vlan=None,
                    speed=int(alternative_ports_state[port_name]['speed'].split('G')[0]) * 1000 if \
                        alternative_ports_state[port_name]['speed'] != 'NA' else 0,
                    neighbor=None,
                    mode=pmode,
                    status='DOWN' if alternative_ports_state[itf.ifname]['oper'] == 'down' else 'UP',
                    admin_status='ENABLED' if alternative_ports_state[itf.ifname]['admin'] == 'up' else 'DISABLED',
                    duplex='NA'
                )
            )
        cfg = json.loads(rest_portchannel.sonic_portchannel_sonic_portchannel.model_dump_json(by_alias=True))
        cfg.update(json.loads(rest_port.sonic_port_sonic_port.model_dump_json(by_alias=True)))
        return cfg

    def retrieve_vrf(self) -> dict:
        rest_vrf = SonicVrfSonicVrf.model_validate(self._sbi_rest_driver.get('{}/sonic-vrf:sonic-vrf'.format(RESTPATH)))

        for vrf_item in rest_vrf.sonic_vrf_sonic_vrf.VRF.VRF_LIST:
            self.vrfs.append(
                Vrf.model_validate({
                    'name': vrf_item.vrf_name,
                    'rd': str(vrf_item.vni),
                    'ports': [item for item in self.vlan_l3_ports if item.vrf == vrf_item.vrf_name]
                })
            )
        if 'default' not in [item.name for item in self.vrfs]:
            self.vrfs.append(
                Vrf.model_validate({
                    'name': 'default',
                    'rd': "default",
                    'ports': [item for item in self.vlan_l3_ports if item.vrf == None]
                })
            )
        return json.loads(rest_vrf.model_dump_json(by_alias=True))

    def _add_vlan(self, vlan_ids: List[int]):
        msg = PostListSonicVlanList()
        for vlan in vlan_ids:
            item = SonicVlanListItem(name='Vlan{}'.format(vlan), vlanid=vlan)
            msg.sonic_vlan_VLAN_LIST.append(item)
            self._sbi_rest_driver.post('{}/sonic-vlan:sonic-vlan/VLAN'.format(RESTPATH), msg.model_dump(by_alias=True))

    def _del_vlan(self, vlan_ids: List[int]):
        for _id in vlan_ids:
            self._sbi_rest_driver.delete("{path}/sonic-vlan:sonic-vlan/VLAN/VLAN_LIST=Vlan{_id}".format(
                path=RESTPATH, _id=_id))

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False):
        msg = SonicVlanMemberList()
        tag_mode = TaggingMode.untagged if pvid else TaggingMode.tagged
        item = SonicVlanMemberListItem(name="Vlan{}".format(vlan_id), ifname=port.name, tagging_mode=tag_mode)
        msg.sonic_vlan_VLAN_MEMBER_LIST.append(item)
        self._sbi_rest_driver.post("{}/sonic-vlan:sonic-vlan/VLAN_MEMBER".format(RESTPATH),
                                   msg.model_dump(by_alias=True))

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort):
        for _id in vlan_ids:
            self._sbi_rest_driver.delete(
                "{path}/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST={name},{ifname}".format(
                    path=RESTPATH,
                    name="Vlan{}".format(_id),
                    ifname=port.name
                ))

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']):
        pass

    def _bind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    def _unbind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    def _add_vrf(self, vrf: VrfRequest):
        data = SonicVrfSonicVrf()
        data.sonic_vrf_sonic_vrf.VRF.VRF_LIST = [SonicVrfListItem(vrf_name=vrf.name)]
        res = self._sbi_rest_driver.post(
            '{}/sonic-vrf:sonic-vrf'.format(RESTPATH),
            data.model_dump(by_alias=True)
        )

    def _del_vrf(self, vrf: Vrf):
        res = self._sbi_rest_driver.delete(
            "{path}/sonic-vrf:sonic-vrf/VRF/VRF_LIST={vrf_name}".format(
                path=RESTPATH,
                vlanName=vrf.name)
        )

    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: SwitchRequestVlanL3Port):
        # create a vlan L3 interface and associate it to the requested vrf

        data = PostListSonicVlanInterface()
        item = SonicVlanInterfaceListItem(
            vlanName="Vlan{}".format(vlan_interface.vlan),
            vrf_name=vrf.name
        )
        data.sonic_vlan_interface_VLAN_INTERFACE_LIST.append(item)
        ip_config = SonicVlanInterfaceIPAddrListItem(
            vlanName="Vlan{}".format(vlan_interface.vlan),
            ip_prefix="{}/{}".format(vlan_interface.ipaddress, str(vlan_interface.cidr).split('/')[1])
        )
        logger.debug('sending request')
        res = self._sbi_rest_driver.post(
            '{}/sonic-vlan-interface:sonic-vlan-interface/VLAN_INTERFACE'.format(RESTPATH),
            data.model_dump(by_alias=True)
        )

    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port):
        res = self._sbi_rest_driver.delete(
            "{path}/sonic-vlan-interface:sonic-vlan-interface/VLAN_INTERFACE/VLAN_INTERFACE_LIST={vlanName}".format(
                path=RESTPATH,
                vlanName=vlan_interface.name)
        )

    def _add_bgp_instance(self, vrf_msg: VrfRequest):
        frr_obj = FrrConfig()

        frr_cmds = frr_obj.add_bgp_instance_cmd(
            vrfname=vrf_msg.name,
            as_number=vrf_msg.protocols.bgp.as_number,
            afs=vrf_msg.protocols.bgp.address_families
        )
        self._sbi_ssh_driver.send_command(commands=frr_cmds, json_parse=False)

        for neighbor in vrf_msg.protocols.bgp.neighbors:
            frr_cmds = frr_obj.add_bgp_peer_cmd(
                neighbor=neighbor,
                vrfname=vrf_msg.name,
                as_number=vrf_msg.protocols.bgp.as_number
            )
            self._sbi_ssh_driver.send_command(commands=frr_cmds, json_parse=False)

    def _del_bgp_instance(self, vrf_name: str):
        vrf_config = next(item for item in self.vrfs if item.name == vrf_name)
        frr_obj = FrrConfig()
        frr_cmds = frr_obj.del_bgp_instance_cmd(vrfname=vrf_name, as_number=vrf_config.protocols.bgp.as_number)
        self._sbi_ssh_driver.send_command(commands=frr_cmds, json_parse=False)

    def _add_static_route(self, route: IpV4Route, vrf_name: str = 'default'):
        frr_obj = FrrConfig()

    def _del_static_route(self, route: IpV4Route, vrf_name: str = 'default'):
        pass

    def commit_and_save(self):
        pass
