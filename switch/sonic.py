import json

from sbi.paramiko import ParamikoSbi
from .switch_base import Switch
from models import LldpNeighbor, PhyPort, VlanL3Port, Vrf, SwitchRequestVlanL3Port
from ipaddress import IPv4Network, IPv4Interface
from utils import create_logger
from typing import List, Literal

logger = create_logger('sonic')



class Microtik(Switch):
    _sbi_ssh_driver: ParamikoSbi = None

    def _update_info(self):
        cfg = self.retrieve_config()
        self.retrieve_ports(cfg)
        self.retrieve_vlans(cfg)
        self.retrieve_port_vlan(cfg)
        self.retrieve_vlan_interfaces(cfg)
        self.create_dummy_vrf()

        self.retrieve_neighbors()

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_ssh_driver:
            ssh_device = self.to_device_model().model_copy(update={'model': 'sonic'})
            self._sbi_ssh_driver = ParamikoSbi(ssh_device)

    def _retrieve_info(self):
        self.reinit_sbi_drivers()
        self.update_info()

        print(self.model_dump())

    def retrieve_config(self) -> None:
        _config = self._sbi_ssh_driver.get_info("export")
        res = self._sbi_ssh_driver.send_command(['/usr/local/bin/sonic-cfggen -d --print-data'], json_parse=True)
        self.store_config(json.dumps(res))
        return res

    def retrieve_neighbors(self):
        neighbours = self._sbi_ssh_driver.send_command(['sudo lldpctl -f json'], json_parse=True)

        """for neigh in neighbours:
            if 'interface' in neigh:
                for i_name in neigh['interface'].split(','):
                    port = next((item for item in self.phy_ports if item.name == i_name), None)
                    if not port:
                        logger.warning("[lldp neigh] interface {} not found".format(i_name))
                        continue
                    if 'identity' in neigh:
                        port.neighbor = LldpNeighbor(
                            neighbor=neigh['identity'],
                            remote_interface=neigh['mac-address'] if 'mac-address' in neigh else 'NA'
                        )"""

    def retrieve_vlans(self, cfg):
        if 'VLANS' not in self.last_config.config:
            return False

        for vlan_name in cfg['VLAN'].keys():
            self.vlans.append(int(cfg['VLAN'][vlan_name]['vlan_id']))

    def retrieve_ports(self, cfg: dict):
        if 'PORT' not in cfg:
            return False
        port_status = self._sbi_ssh_driver.send_command(['sudo lldpctl -f json'], json_parse=False)
        """
Interface            Lanes    Speed    MTU    FEC          Alias          Vlan    Oper    Admin             Type    Asym PFC
------------  ---------------  -------  -----  -----  -------------  ------------  ------  -------  ---------------  ----------
   Ethernet0          1,2,3,4     100G   9100    N/A   hundredGigE1  PortChannel1      up       up  QSFP28 or later         N/A
   Ethernet4          5,6,7,8     100G   9100    N/A   hundredGigE2  PortChannel1      up       up  QSFP28 or later         N/A
   Ethernet8       9,10,11,12     100G   9100    N/A   hundredGigE3        routed    down       up              N/A         N/A
  Ethernet12      13,14,15,16     100G   9100    N/A   hundredGigE4       """


        for itf_name in cfg.keys():
            self.phy_ports.append(
                PhyPort(
                    index=cfg[itf_name]['index'],
                    name=itf_name,
                    trunk_vlans=[],
                    access_vlan=None,
                    speed=cfg[itf_name]['speed'],
                    neighbor=None,
                    mode='NA',
                    status='NA',
                    admin_status='ENABLED' if cfg[itf_name]['admin_status'] == 'up' else 'DISABLED',
                    duplex='NA'
                )
            )

    def retrieve_port_vlan(self) -> None:
        vlan_port_data = self._sbi_rest_driver.get("interface/bridge/port")
        for port in vlan_port_data:
            phy_port = next(item for item in self.phy_ports if item.name == port['interface'])
            phy_port.access_vlan = port['pvid'] if 'pvid' in port else None
            if 'frame-types' in port:
                match port['frame-types']:
                    case 'admit-all':
                        phy_port.mode = 'HYBRID'
                    case 'admit-only-untagged-and-priority-tagged':
                        phy_port.mode = 'ACCESS'
                    case 'admit-only-vlan-tagged':
                        phy_port.mode = 'TRUNK'

    def retrieve_vlan_interfaces(self) -> None:
        vlan_itf_data = self._sbi_rest_driver.get("interface/vlan")
        itf_ips = self._sbi_rest_driver.get("ip/address")
        for itf in vlan_itf_data:
            if itf['interface'] == default_switch_name:
                # it is a vlan interface on the managed bridge
                itf_ip = next((item for item in itf_ips if item['interface'] == itf['name']), None)
                ip_addr = None
                cidr = None
                if itf_ip:
                    itf_ip_and_mask = itf_ip['address'].split('/')
                    ip_addr = itf_ip_and_mask[0]
                    cidr = "{}/{}".format(itf_ip['network'], itf_ip_and_mask[1])

                self.vlan_l3_ports.append(
                    VlanL3Port.model_validate(
                        {
                            'index': itf['.id'],
                            'name': itf['name'],
                            'vlan': int(itf['vlan-id']),
                            'ipaddress': ip_addr,
                            'cidr': cidr,
                            'vrf': 'mobile_testbed',
                            'description': None
                        }
                    )
                )

    def _add_vlan(self, vlan_ids: List[int]):
        for _id in vlan_ids:
            data = {
                'vlan-ids': _id,
                'bridge': default_switch_name,
                'tagged': default_switch_name
            }
            self._sbi_rest_driver.put('/interface/bridge/vlan', data)

    def _del_vlan(self, vlan_ids: List[int]):
        vlan_table = self._sbi_rest_driver.get('/interface/bridge/vlan?bridge={}'.format(default_switch_name))
        for vlan_id in vlan_ids:
            row = next((item for item in vlan_table if str(vlan_id) in item['vlan-ids'].split(',')), None)
            if row:
                row_vlan_ids = row['vlan-ids'].split(',')
                if len(row_vlan_ids) == 1:
                    self._sbi_rest_driver.delete('/interface/bridge/vlan/{}'.format(row['.id']))
                else:
                    logger.debug('this row contains more than one vlans')
                    data = {'vlan-ids': ','.join(filter(lambda v: v != str(vlan_id), row_vlan_ids))}
                    self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(row['.id']), data)
            else:
                logger.warn('vlan {} not existing'.format(vlan_id))

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False):
        row = self._get_vlan_row(vlan_id)

        row_vlan_ids = row['vlan-ids'].split(',')
        untagged_ports = row['untagged'].split(',')
        tagged_ports = row['tagged'].split(',')

        if len(row_vlan_ids) > 1:
            # in this case, the old row should be updated without the vlan_id, and a new row should be added
            row_to_update = {'vlan_ids': ",".join(filter(lambda x: str(x) != str(vlan_id), row_vlan_ids))}
            self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(row['.id']), row_to_update)

        if pvid:
            if port.name in tagged_ports:
                raise ValueError('delete vlan {} from tagged set of port {} before adding as untagged'.format(
                    vlan_id, port.name))
            untagged_ports.append(port.name)
            data = {'untagged': ','.join(untagged_ports)}
        else:
            if port.name in untagged_ports:
                raise ValueError('delete vlan {} from untagged set of port {} before adding as tagged'.format(
                    vlan_id, port.name))
            tagged_ports.append(port.name)
            data = {'tagged': ','.join(tagged_ports)}

        if len(row_vlan_ids) > 1:
            # create a new row only for the vlan id under elaboration
            data['vlan_ids'] = vlan_id
            self._sbi_rest_driver.put('/interface/bridge/vlan', data)
        else:
            self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(row['.id']), data)

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort):
        vlan_table = self._sbi_rest_driver.get('/interface/bridge/vlan?bridge={}'.format(default_switch_name))
        for vlan_id in vlan_ids:
            row = next((item for item in vlan_table if str(vlan_id) in item['vlan-ids'].split(',')), None)

            if not row:
                raise ValueError('vlan {} not declared'.format(vlan_id))

            row_vlan_ids = row['vlan-ids'].split(',')
            untagged_ports = row['untagged'].split(',')
            tagged_ports = row['tagged'].split(',')

            if len(row_vlan_ids) == 1:
                # in this case we can simply patch row
                updated_row = dict()
                updated_row['tagged'] = ','.join(filter(lambda x: x != port.name, tagged_ports))
                updated_row['untagged'] = ','.join(filter(lambda x: x != port.name, untagged_ports))
                self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(row['.id']), updated_row)
            else:
                # in this case we should remove the vlan from the row, and add a new row with only that vlan and the
                # remaining ports
                data = {'vlan-ids': ','.join(filter(lambda x: str(x) != str(vlan_id), row_vlan_ids))}
                self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(row['.id']), data)
                vlan_row = dict(row)
                vlan_row['vlan-ids'] = vlan_id
                vlan_row['tagged'] = ','.join(filter(lambda x: x != port.name, tagged_ports))
                vlan_row['untagged'] = ','.join(filter(lambda x: x != port.name, untagged_ports))
                vlan_row.pop('.id')
                self._sbi_rest_driver.put('/interface/bridge/vlan', vlan_row)

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']):
        port_table = self._sbi_rest_driver.get('/interface/bridge/port?bridge')
        port_row = next(item for item in port_table if item['interface'] == port.name)
        data = {}
        match port_mode:
            case 'ACCESS':
                data['frame-types'] = 'admit-only-untagged-and-priority-tagged'
            case 'HYBRID':
                data['frame-types'] = 'admit-all'
            case 'TRUNK':
                data['frame-types'] = 'admit-only-vlan-tagged'

        self._sbi_rest_driver.patch('interfaces/bridge/port/{}'.format(port_row['.id']), data)

    def _bind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        logger.warning('VRF not supported in this switch model')
        return False

    def _unbind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        logger.warning('VRF not supported in this switch model')
        return False

    def _get_vlan_row(self, vid: int) -> dict:
        vlan_table = self._sbi_rest_driver.get('/interface/bridge/vlan?bridge={}'.format(default_switch_name))
        vlan_row = next((item for item in vlan_table if str(vid) in item['vlan-ids'].split(',')), None)
        if not vlan_row:
            raise ValueError('vlan {} not existing'.format(vid))
        return vlan_row

    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: SwitchRequestVlanL3Port):
        # create a vlan L3 interface and associate it to the dummy vrf

        # as first, we need to assure that the vlan id is enabled as trunk in the default bridge
        vlan_row = self._get_vlan_row(vlan_interface.vlan)

        bridge_tagged = vlan_row['tagged'].split(',')
        if default_switch_name not in bridge_tagged:
            bridge_tagged.append(default_switch_name)
            data = {'tagged': ','.join(bridge_tagged)}
            self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(vlan_row['.id']), data)

        # now we can create the vlan interface
        data = {
            'name': 'vlan_{}'.format(vlan_interface.vlan),
            'vlan-id': vlan_interface.vlan,
            'interface': default_switch_name
        }
        self._sbi_rest_driver.put('/interface/vlan', data)

        # finally we have to set the ip address
        netmask = str(IPv4Network(str(vlan_interface.cidr)).netmask)
        data = {
            'address': str(IPv4Interface(
                '{}/{}'.format(str(vlan_interface.ipaddress).split('/')[0], netmask)).with_prefixlen),
            'network': str(vlan_interface.cidr).split('/')[0],
            'interface': 'vlan_{}'.format(vlan_interface.vlan)
        }
        logger.debug(data)
        self._sbi_rest_driver.put('/ip/address', data)

    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port):
        # first: delete IP address
        ip_addr_table = self._sbi_rest_driver.get('/ip/address')
        ip_addr_row = next((item for item in ip_addr_table if item['interface'] == vlan_interface.name), None)
        if ip_addr_row:
            self._sbi_rest_driver.delete('/ip/address/{}'.format(ip_addr_row['.id']))

        # second: delete the vlan interface
        vlan_itf_table = self._sbi_rest_driver.get('/interface/vlan')
        vlan_itf_row = next((item for item in vlan_itf_table if item['vlan-id'] == str(vlan_interface.vlan)), None)
        if vlan_itf_row:
            self._sbi_rest_driver.delete('/interface/vlan/{}'.format(vlan_itf_row['.id']))

        # finally remove bridge interface from tagged list
        vlan_row = self._get_vlan_row(vlan_interface.vlan)
        vlans_in_row = vlan_row['vlan-ids'].split(',')
        tagged_itf = vlan_row['tagged'].split(',')
        if len(vlans_in_row) > 1:
            # remove vlan id from the original row if the row includes multiple vlans
            data = {'vlan-ids': ','.join(filter(lambda x: x != str(vlan_interface.vlan), vlans_in_row))}
            self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(vlan_row['.id']), data)
            # now add a row for the vlan under elaboration
            vlan_row['vlan-ids'] = vlan_interface.vlan
            vlan_row['tagged'] = ','.join(filter(lambda x: x != default_switch_name, tagged_itf))
            vlan_row.pop('.id')
            self._sbi_rest_driver.put('/interface/bridge/vlan', vlan_row)
        else:
            # patch the vlan row to remove the default bridge from tagged
            data = {'tagged': ','.join(filter(lambda x: x != default_switch_name, tagged_itf))}
            self._sbi_rest_driver.patch('/interface/bridge/vlan/{}'.format(vlan_row['.id']), data)

    def commit_and_save(self):
        pass
