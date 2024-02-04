import json

from sbi.paramiko import ParamikoSbi
from .switch_base import Switch
from models import LldpNeighbor, PhyPort, VlanL3Port, Vrf, SwitchRequestVlanL3Port
from ipaddress import IPv4Network
from utils import create_logger
from typing import List, Literal

logger = create_logger('sonic')


class Sonic(Switch):
    _sbi_ssh_driver: ParamikoSbi = None

    def _update_info(self):
        cfg = self.retrieve_config()
        self.retrieve_ports(cfg)
        self.retrieve_vlans(cfg)
        self.retrieve_port_vlan(cfg)
        self.retrieve_vlan_interfaces(cfg)
        self.retrieve_vrf(cfg)

        self.retrieve_neighbors()

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_ssh_driver:
            ssh_device = self.to_device_model().model_copy(update={'model': 'sonic'})
            self._sbi_ssh_driver = ParamikoSbi(ssh_device)

    def _retrieve_info(self):
        self.reinit_sbi_drivers()
        self.update_info()

        print(self.model_dump())

    def retrieve_config(self) -> dict:
        _config = self._sbi_ssh_driver.send_command(["export"])
        res = self._sbi_ssh_driver.send_command(['/usr/local/bin/sonic-cfggen -d --print-data'], json_parse=True)
        self.store_config(json.dumps(res[0]['_stdout']))
        return res[0]['_stdout']

    def retrieve_neighbors(self):
        lldp_data = self._sbi_ssh_driver.send_command(['sudo lldpctl -f json'], json_parse=True)[0]['_stdout']
        if 'lldp' not in lldp_data.keys() or 'interface' not in lldp_data['lldp'].keys():
            raise ValueError('lldp data malformed')
        for itf in lldp_data['lldp']['interface']:
            itf_name = list(itf.keys())[0]
            phy_port = next((item for item in self.phy_ports if item.name == itf_name), None)
            if not phy_port:
                continue
            phy_port.neighbor = LldpNeighbor.model_validate({
                'neighbor': list(itf[itf_name]['chassis'].keys())[0],
                'remote_interface': itf[itf_name]['port']['descr']
            })

    def retrieve_vlans(self, cfg):
        if 'VLAN' not in self.last_config.config:
            return False

        for vlan_name in cfg['VLAN'].keys():
            self.vlans.append(int(cfg['VLAN'][vlan_name]['vlanid']))

    def retrieve_ports(self, cfg: dict):
        port_channels = {}

        if 'PORTCHANNEL' and 'PORTCHANNEL_MEMBER' in cfg:
            logger.debug('checking portchannels')
            for member in cfg['PORTCHANNEL_MEMBER'].keys():
                mdata = member.split('|')
                pc_name = mdata[0]
                itf_name = mdata[1]
                port_channels[itf_name] = pc_name

        if 'PORT' not in cfg:
            return False

        port_status_res = self._sbi_ssh_driver.send_command(['./dump_itf_status'], json_parse=True)[0]['_stdout']
        for itf_name in cfg['PORT'].keys():
            is_in_port_channel = itf_name in port_channels.keys()

            port_name = port_channels[itf_name] if is_in_port_channel else itf_name
            if next((item for item in self.phy_ports if item.name == port_name), None):
                # portchannel already stored
                continue

            if port_name not in port_status_res:
                port_status_res[itf_name] = {'vlan': 'NA', 'oper': 'NA', 'admin': 'NA', 'speed': 'NA'}

            match port_status_res[port_name]['vlan']:
                case 'routed':
                    pmode = 'ROUTED'
                case 'trunk':
                    pmode = 'TRUNK'
                case 'access':
                    pmode = 'ACCESS'
                case _:
                    pmode = 'NA'

            self.phy_ports.append(
                PhyPort(
                    index=cfg['PORT'][itf_name]['index'],
                    name=port_name,
                    trunk_vlans=[],
                    access_vlan=None,
                    speed=int(port_status_res[port_name]['speed'].split('G')[0]) * 1000,
                    neighbor=None,
                    mode=pmode,
                    status='DOWN' if port_status_res[itf_name]['oper'] == 'down' else 'UP',
                    admin_status='ENABLED' if port_status_res[itf_name]['admin'] == 'up' else 'DISABLED',
                    duplex='NA'
                )
            )

    def retrieve_port_vlan(self, cfg) -> None:
        if 'VLAN_MEMBER' not in cfg:
            logger.warn('no VLAN MEMBER node in Sonic DB!!')
            return

        for member in cfg['VLAN_MEMBER'].keys():
            inf_vlan_list = member.split('|')
            itf_name = inf_vlan_list[1]
            vlan_name = inf_vlan_list[0]
            vid = int(cfg['VLAN'][vlan_name]['vlanid'])
            phyport = next((item for item in self.phy_ports if item.name == itf_name), None)
            if not phyport:
                continue
            match cfg['VLAN_MEMBER'][member]['tagging_mode']:
                case 'tagged':
                    phyport.trunk_vlans.append(vid)
                case 'untagged':
                    phyport.access_vlan = vid
                case _:
                    raise ValueError('vlan mode {} not supported'.format(cfg['VLAN_MEMBER'][member]['tagging_mode']))

        for p in self.phy_ports:
            if p.mode == 'TRUNK' and len(p.trunk_vlans) == 0 and p.access_vlan:
                p.mode = 'ACCESS'
            elif p.mode == 'TRUNK' and p.access_vlan:
                p.mode = 'HYBRID'

    def retrieve_vlan_interfaces(self, cfg: dict) -> None:
        if 'VLAN_INTERFACE' not in cfg.keys():
            return
        for member in cfg['VLAN_INTERFACE'].keys():
            vdata = member.split('|')
            vlan_name = vdata[0]
            vid = cfg['VLAN'][vlan_name]['vlanid'] if vlan_name in cfg['VLAN'] else None

            ip_addr_str = vdata[1] if len(vdata) > 1 else None
            ip_addr = ip_addr_str.split('/')[0] if ip_addr_str else None
            cidr = str(IPv4Network(ip_addr_str, strict=False)) if ip_addr_str else None

            vrf = cfg['VLAN_INTERFACE'][member]['vrf_name'] if 'vrf_name' in cfg['VLAN_INTERFACE'][member] else None

            vlan_port = next((item for item in self.vlan_l3_ports if item.name == vlan_name), None)
            if vlan_port:
                if ip_addr:
                    vlan_port.ipaddress = ip_addr
                    vlan_port.cidr = cidr
                if vrf:
                    vlan_port.vrf = vrf
            else:
                self.vlan_l3_ports.append(
                    VlanL3Port.model_validate(
                        {
                            'index': vlan_name,
                            'name': vlan_name,
                            'vlan': int(vid),
                            'ipaddress': ip_addr,
                            'cidr': cidr,
                            'vrf': vrf,
                            'description': None
                        }
                    )
                )

    def retrieve_vrf(self, cfg: dict) -> None:
        if 'VRF' not in cfg:
            return
        for vrf_name in cfg['VRF'].keys():
            self.vrfs.append(
                Vrf.model_validate({
                    'name': vrf_name,
                    'rd': vrf_name,
                    'ports': [item for item in self.vlan_l3_ports if item.vrf == vrf_name]
                })
            )

    def _add_vlan(self, vlan_ids: List[int]):
        for _id in vlan_ids:
            res = self._sbi_ssh_driver.send_command(["sudo config vlan add {}".format(_id)])
            if res[0]['_stderr']:
                raise ValueError(res[0]['_stderr'])

    def _del_vlan(self, vlan_ids: List[int]):
        for _id in vlan_ids:
            res = self._sbi_ssh_driver.send_command(["sudo config vlan del {}".format(_id)])
            if res[0]['_stderr']:
                raise ValueError(res[0]['_stderr'])

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False):
        if pvid:
            res = self._sbi_ssh_driver.send_command(["sudo config vlan member add -u {} {}".format(vlan_id, port.name)])
        else:
            res = self._sbi_ssh_driver.send_command(["sudo config vlan member add {} {}".format(vlan_id, port.name)])
        if res[0]['_stderr']:
            raise ValueError(res[0]['_stderr'])

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort):
        for _id in vlan_ids:
            res = self._sbi_ssh_driver.send_command(["sudo config vlan member del {} {}".format(_id, port.name)])
            if res[0]['_stderr']:
                raise ValueError(res[0]['_stderr'])

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']):
        pass

    def _bind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    def _unbind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: SwitchRequestVlanL3Port):
        # create a vlan L3 interface and associate it to the requested vrf

        # as first, we need to assure that the vlan id is enabled as trunk in the default bridge
        """
        sudo config interface ip add --help
        Usage: config interface ip add [OPTIONS] <interface_name> <ip_addr> <default gateway IP address>
        """
        res = self._sbi_ssh_driver.send_command(["sudo config interface ip add Vlan{} {}/{}".format(
            vlan_interface.vlan, vlan_interface.ipaddress, str(vlan_interface.cidr).split('/')[1])])
        if res[0]['_stderr']:
            raise ValueError(res[0]['_stderr'])

        """
        sudo config interface vrf bind --help
        Usage: config interface vrf bind [OPTIONS] <interface_name> <vrf_name>
        """
        res = self._sbi_ssh_driver.send_command(["sudo config interface vrf bind Vlan{} {}".format(
            vlan_interface.vlan, vrf.name)])
        if res[0]['_stderr']:
            raise ValueError(res[0]['_stderr'])

    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port):
        """
        sudo config interface vrf unbind --help
        Usage: config interface vrf unbind [OPTIONS] <interface_name>
        """
        res = self._sbi_ssh_driver.send_command(["sudo config interface vrf unbind Vlan{}".format(
            vlan_interface.vlan)])
        if res[0]['_stderr']:
            raise ValueError(res[0]['_stderr'])
        """
        sudo config interface ip remove --help
        Usage: config interface ip remove [OPTIONS] <interface_name> <ip_addr>
        """
        res = self._sbi_ssh_driver.send_command(["sudo config interface ip remove Vlan{} {}/{}".format(
            vlan_interface.vlan, vlan_interface.ipaddress, str(vlan_interface.cidr).split('/')[1])])
        if res[0]['_stderr']:
            raise ValueError(res[0]['_stderr'])

    def commit_and_save(self):
        res = self._sbi_ssh_driver.send_command(["sudo config save -y"])
        if res[0]['_stderr']:
            raise ValueError(res[0]['_stderr'])
