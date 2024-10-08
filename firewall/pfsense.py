import json
from pydantic import IPvAnyInterface
from sbi.pfsense_rest import PfSenseRestSbi
from sbi.paramiko_sbi import ParamikoSbi
from sbi.frr_vtysh import FrrConfig
from .firewall_base import Firewall, FirewallRequestL3Port
from .pfsense_models import PfSenseInterfaceMap, PfSenseAvailableInterfaceMap, PfSense_GroupList, PfSense_RuleList, \
    PfSenseInterface
from models import PhyPort, Vrf, FirewallL3Port, FirewallPortGroup, \
    BGPNeighbor, BGPRoutingProtocol, RoutingProtocols, LinkModes
from ipaddress import IPv4Network, IPv4Interface
from utils import create_logger
from typing import List, Tuple, Dict

logger = create_logger('pfsense')


class PfSense(Firewall):
    _sbi_rest_driver: PfSenseRestSbi = None
    _sbi_ssh_driver: ParamikoSbi = None
    frr_config: FrrConfig = None

    def _update_info(self):
        self.retrieve_data()

        config = self._sbi_rest_driver.get("system/config")
        # Note: pfsense config also contains the complete Frr configuration
        if 'rrddata' in config.keys():
            config.pop('rrddata')

        str_config = json.dumps(config)
        logger.warn("the size of the config is {} MB".format(len(str_config)/1024/1024))
        self.store_config(str_config)

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_rest_driver:
            device = self.to_device_model().model_copy(update={'model': 'pfsense'})
            self._sbi_rest_driver = PfSenseRestSbi(device)
        if not self._sbi_ssh_driver:
            device = self.to_device_model().model_copy(update={'model': 'pfsense'})
            self._sbi_ssh_driver = ParamikoSbi(device)

    def _retrieve_info(self):
        self.reinit_sbi_drivers()
        self.update_info()

    def retrieve_data(self) -> None:
        pf_sense_l3_ports = self._sbi_rest_driver.get("interface", parsing_class=PfSenseInterfaceMap)
        pf_sense_phy_ports = self._sbi_rest_driver.get(
            "interface/available", parsing_class=PfSenseAvailableInterfaceMap)
        self.phy_ports = pf_sense_phy_ports.to_phy_port_list()

        for port_name in pf_sense_l3_ports.root.keys():
            vlan = 1
            if pf_sense_l3_ports.root[port_name].intf:
                current_phy_port = pf_sense_phy_ports.root[pf_sense_l3_ports.root[port_name].intf]
                if current_phy_port.isvlan:

                    vlan = current_phy_port.tag
                    fw_parent_port = next(item for item in self.phy_ports
                                          if item.index == current_phy_port.vlanif.split('.')[0])
                    fw_parent_port.trunk_vlans.append(vlan)
            _ipaddr = None
            _cidr = None
            if pf_sense_l3_ports.root[port_name].ipaddr:
                _ipaddr = pf_sense_l3_ports.root[port_name].ipaddr
                _cidr = IPvAnyInterface("{}/{}".format(
                    pf_sense_l3_ports.root[port_name].ipaddr, pf_sense_l3_ports.root[port_name].subnet))
            self.l3_ports.append(FirewallL3Port(
                index=port_name,
                name=pf_sense_l3_ports.root[port_name].descr,
                vlan=vlan,
                ipaddress=_ipaddr,
                cidr=_cidr,
                vrf="default",
                interface_assignment=pf_sense_l3_ports.root[port_name].intf.split('.')[0]
            ))
        for port in self.phy_ports:
            if len(port.trunk_vlans) > 1:
                port.mode = LinkModes.trunk

        pfsense_groups = self._sbi_rest_driver.get("interface/group", parsing_class=PfSense_GroupList)
        print(pfsense_groups)
        for g in pfsense_groups:
            self.port_groups.append(FirewallPortGroup(
                name=g.ifname,
                description=g.descr,
                members=g.members.split()
            ))

        pfsense_rules = self._sbi_rest_driver.get("firewall/rule", parsing_class=PfSense_RuleList)
        for r in pfsense_rules:
            logger.debug(r.model_dump())

        self.vrfs.append(Vrf(name='default', rd='default', description="Default VRF", ports=self.l3_ports))

        raw_config = self._sbi_ssh_driver.send_command(commands=["vtysh -c \"show running-config\""])
        self.frr_config = FrrConfig.from_raw_config(raw_config[-1]['_stdout'])
        for frr_vrf in self.frr_config.routers:
            device_vrf = next(item for item in self.vrfs if item.name == frr_vrf.vrf)
            if not device_vrf.protocols:
                device_vrf.protocols = RoutingProtocols()
            device_vrf.protocols.bgp = BGPRoutingProtocol(
                as_number=frr_vrf.as_number,
                neighbors=frr_vrf.neighbors,
                address_families=frr_vrf.address_families
            )

    def _add_l3port_to_vrf(self, vrf: Vrf, vlan_interface: FirewallRequestL3Port):
        self._sbi_rest_driver.get("interface")

        itf_request = {
            'if': "{}.{}".format(vlan_interface.intf, vlan_interface.vlan),
            'ipaddr': str(IPv4Interface(vlan_interface.ipaddress).ip),
            'subnet': int(IPv4Network(vlan_interface.cidr).prefixlen),
            'descr': vlan_interface.description,
            'type': 'staticv4',
            'spoofmac': '',
            'enable': True,
            'apply': True
        }
        res = self._sbi_rest_driver.post('interface', itf_request)
        logger.debug("Operation result: {}".format(res))

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False, description: str = '') -> bool:
        msg = {
            'if': port.name,
            'tag': vlan_id,
            'descr': description
        }
        if not self._sbi_rest_driver.post("interface/vlan", msg):
            raise ValueError('Vlan {} cannot be set on port {}'.format(vlan_id, port.name))

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort) -> bool:
        data = self._sbi_rest_driver.get("interface/vlan")
        logger.warn(data)
        for vid in vlan_ids:
            itf_index = next(i for i, x in enumerate(data) if x['if'] == port.name and int(x['tag']) == vid)
            res = self._sbi_rest_driver.delete("interface/vlan?id={}".format(itf_index))
            logger.debug("Vlan {} deleted on interface {}: {}".format(vid, port.name, res))

    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: FirewallL3Port) -> bool:
        self._sbi_rest_driver.delete('interface?if={}'.format(vlan_interface.description))
        port = next(item for item in self.phy_ports if item.name == vlan_interface.interface_assignment)
        self._del_vlan_to_port([vlan_interface.vlan], port)

    def _add_bgp_peering(self, msg: BGPNeighbor):
        default_vrf = next((item for item in self.vrfs if item.name == "default"))
        local_as_number = default_vrf.protocols.bgp.as_number
        commands = self.frr_config.add_bgp_peer_cmd(neigh=msg, vrfname='default', as_number=local_as_number)
        self._sbi_ssh_driver.send_command(commands)

    def _del_bgp_peering(self, msg: BGPNeighbor):
        default_vrf = next((item for item in self.vrfs if item.name == "default"))
        local_as_number = default_vrf.protocols.bgp.as_number
        commands = self.frr_config.del_bgp_peer_cmd(neigh=msg, vrfname='default', as_number=local_as_number)
        self._sbi_ssh_driver.send_command(commands)

    def _add_l3port_to_group(self, vlan_interface: FirewallRequestL3Port, fw_port_group: str):
        interface_key, interface_name, itfs_in_group, group_to_update = self._get_data_for_group_mgt(
            vlan_interface, fw_port_group)

        if interface_key in itfs_in_group:
            logger.warn("interface {} already in the group {}".format(interface_name, fw_port_group))
            return

        itfs_in_group.append(interface_key)
        group_to_update['members'] = " ".join(itfs_in_group)
        self._sbi_rest_driver.put('interface/group', group_to_update)

    def _del_l3port_to_group(self, vlan_interface: FirewallRequestL3Port, fw_port_group: str):
        interface_key, interface_name, itfs_in_group, group_to_update = self._get_data_for_group_mgt(
            vlan_interface, fw_port_group)

        if interface_key not in itfs_in_group:
            logger.warn("interface {} is not in the group {}. Skipping".format(interface_name, fw_port_group))
            return

        itfs_in_group.remove(interface_key)
        group_to_update['members'] = " ".join(itfs_in_group)
        self._sbi_rest_driver.put('interface/group', group_to_update)

    def _get_data_for_group_mgt(self, vlan_interface: FirewallRequestL3Port, fw_port_group: str) -> Tuple[str, str,
                                                                                                          List, Dict]:
        available_itfs = self._sbi_rest_driver.get('interface/group')
        interface_name = "{}.{}".format(vlan_interface.intf, vlan_interface.vlan)
        interface_key = next((key for key in available_itfs.keys() if available_itfs[key]['if'] == interface_name),
                             None)
        if not interface_key:
            raise ValueError("Vlan Interface {} not found".format(interface_name))

        groups = self._sbi_rest_driver.get('interface/group')
        group_to_update = next((item for item in groups if item.ifname == fw_port_group), None)
        if not group_to_update:
            raise ValueError("Group {} not existing on the firewall")
        itfs_in_group = group_to_update['members'].split()

        return interface_key, interface_name, itfs_in_group, group_to_update

    def commit_and_save(self):
        self._sbi_rest_driver.post('firewall/apply', {'async': True})
