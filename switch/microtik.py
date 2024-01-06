from sbi.routeros import RosRestSbi
from sbi.netmiko import NetmikoSbi
from .switch_base import Switch
from models import LldpNeighbor, PhyPort, VlanL3Port, Vrf
from pydantic import IPvAnyInterface
from netaddr import IPAddress
from utils import create_logger
from typing import List, Literal

logger = create_logger('microtik')
default_switch_name ='tnt'


class Microtik(Switch):
    _sbi_rest_driver: RosRestSbi = None
    _sbi_ssh_driver: NetmikoSbi = None

    def _update_info(self):
        pass

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_rest_driver:
            self._sbi_rest_driver = RosRestSbi(self.to_device_model())
        if not self._sbi_ssh_driver:
            ssh_device = dict(self.to_device_model())
            ssh_device.model = 'mikrotik_routeros'
            self._sbi_ssh_driver = NetmikoSbi(ssh_device)

    def _retrieve_info(self):
        self.reinit_sbi_drivers()
        self.retrieve_ports()
        logger.info('1--------------------------------------------')
        self.retrieve_vlans()
        logger.info('2--------------------------------------------')
        self.retrieve_port_vlan()
        logger.info('3--------------------------------------------')
        self.retrieve_vlan_interfaces()
        logger.info('4--------------------------------------------')
        self.create_dummy_vrf()
        logger.info('5--------------------------------------------')
        self.retrieve_config()
        logger.info('6--------------------------------------------')
        self.retrieve_neighbors()

        print(self.model_dump())

    def retrieve_config(self) -> None:
        _config = self._sbi_ssh_driver.get_info("export")
        res = "{}".join(_config.split("\n")[1:])  # removing first lince since it contain the date of exporting
        self.store_config(res)

    def retrieve_neighbors(self):
        neighbours = self._sbi_rest_driver.get('ip/neighbor')
        for neigh in neighbours:
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
                    )

    def create_dummy_vrf(self):
        self.vrfs = [Vrf(
            name='mobile_testbed',
            rd=default_switch_name,
            description='dummy Vrf for the mobile testbed',
            rd_export=[],
            rd_import=[],
            ports=self.vlan_l3_ports
        )]

    def retrieve_vlans(self):
        res = self._sbi_rest_driver.get('interface/bridge/vlan?bridge={}'.format(default_switch_name))
        for item in res:
            vlans_in_row = item["vlan-ids"].split(',')
            for vlan_id in vlans_in_row:
                if vlan_id not in self.vlans:
                    self.vlans.append(vlan_id)
            for _port_name in item['tagged'].split(','):
                port = next((p for p in self.phy_ports if p.name == _port_name), None)
                if not port:
                    logger.warning('port {} not found while retrieving vlans {}'.format(_port_name, vlans_in_row))
                    continue
                for vlan_id in vlans_in_row:
                    port.trunk_vlans.append(vlan_id)

    def retrieve_ports(self):
        res = self._sbi_rest_driver.get('interface?type=ether')
        logger.warning(res)
        for item in res:
            logger.warning(item)
            ports_data = self._sbi_rest_driver.post(
                'interface/ethernet/monitor',
                {"once": "1", "numbers": "{}".format(item['.id'])}
            )
            port_data = next(p for p in ports_data if p['name'] == item['name'])
            logger.warning(port_data)
            speed = 0
            if 'rate' in port_data:
                if 'Gbps' in port_data['rate']:
                    speed = int(port_data['rate'][:-4]) * 1000
                if 'Mbps' in port_data['rate']:
                    speed = int(port_data['rate'][:-4])
            duplex = 'NA'
            if 'full-duplex' in port_data:
                if port_data['full-duplex'] == 'true':
                    duplex = 'FULL'
                else:
                    duplex = 'HALF'

            self.phy_ports.append(
                PhyPort(
                    index=item['.id'],
                    name=item['name'],
                    trunk_vlans=[],
                    access_vlan=None,
                    speed=speed,
                    neighbor=None,
                    mode='NA',
                    status='UP' if port_data['status'] == 'link-ok' else 'DOWN',
                    admin_status='ENABLED' if item['disabled'] == 'false' else 'DISABLED',
                    duplex=duplex
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
                    ip_addr = itf_ip['address'].split('/')[0]
                    cidr = itf_ip['network']

                self.vlan_l3_ports.append(
                    VlanL3Port.model_validate(
                        {
                            'index': itf['.id'],
                            'name': itf['name'],
                            'vlan': itf['vlan-id'],
                            'ipaddress': ip_addr,
                            'cidr': cidr,
                            'vrf': 'mobile_testbed',
                            'description': None
                        }
                    )
                )
    def _add_vlan(self, vlan_ids: List[int]) -> bool:
        for _id in vlan_ids:
            data = {
                'vlan_ids': _id,
                'bridge': default_switch_name,
                'tagged': default_switch_name
            }
            res = self._sbi_rest_driver.put('/interface/bridge/vlan', data)

    def _del_vlan(self, vlan_ids: List[int]) -> bool:
        numbers = []
        vlan_table = self._sbi_rest_driver.get('/interface/bridge/vlan?bridge={}'.format(default_switch_name))
        for vlan_id in vlan_ids:
            row = next((item for item in vlan_table if vlan_id in item['vlan-ids'].split(',')), None)
            if row:
                row_vlan_ids = row['vlan-ids'].split(',')
                if len(row_vlan_ids) == 1:
                    data = {
                        'bridge': default_switch_name,
                        'numbers': [row['.id']]
                    }
                    self._sbi_rest_driver.delete('/interface/bridge/vlan', data)
                else:
                    logger.debug('this row contains more than one vlans')
                    row['vlan-ids'] = ','.join(filter(lambda v: v != vlan_id, row_vlan_ids))
                    self._sbi_rest_driver.patch('/interface/bridge/vlan', row)
            else:
                logger.warn('vlan {} not existing'.format(vlan_id))
        return True

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False) -> bool:
        vlan_table = self._sbi_rest_driver.get('/interface/bridge/vlan?bridge={}'.format(default_switch_name))
        row = next((item for item in vlan_table if vlan_id in item['vlan-ids'].split(',')), None)

        if not row:
            raise ValueError('vlan {} not declared'.format(vlan_id))

        row_vlan_ids = row['vlan-ids'].split(',')
        untagged_ports = row['untagged'].split(',')
        tagged_ports = row['tagged'].split(',')

        if len(row_vlan_ids) == 1:

            if pvid:
                if port.name in tagged_ports:
                    raise ValueError('delete vlan {} from tagged set of port {} before adding as untagged'.format(
                        vlan_id, port.name))
                untagged_ports.append(port.name)
                row['untagged'] = ','.join(untagged_ports)
            else:
                if port.name in untagged_ports:
                    raise ValueError('delete vlan {} from untagged set of port {} before adding as tagged'.format(
                        vlan_id, port.name))
                tagged_ports.append(port.name)
                row['tagged'] = ','.join(tagged_ports)
            self._sbi_rest_driver.patch('/interface/bridge/vlan', row)
        else:
            # in this case, the old row should be updated without the vlan_id, and a new row should be added
            row_to_update = dict(row)
            row_to_update['vlan_ids'] = ",".join(filter(lambda x: x != vlan_id, row_vlan_ids))
            self._sbi_rest_driver.patch('/interface/bridge/vlan', row_to_update)
            new_row = dict(row)
            new_row['vlan_ids'] = vlan_id
            if pvid:
                if port.name in tagged_ports:
                    raise ValueError('delete vlan {} from tagged set of port {} before adding as untagged'.format(
                        vlan_id, port.name))
                untagged_ports.append(port.name)
                new_row['untagged'] = ','.join(untagged_ports)
            else:
                if port.name in untagged_ports:
                    raise ValueError('delete vlan {} from untagged set of port {} before adding as tagged'.format(
                        vlan_id, port.name))
                tagged_ports.append(port.name)
                new_row['tagged'] = ','.join(tagged_ports)
            self._sbi_rest_driver.patch('/interface/bridge/vlan', new_row)

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort) -> bool:
        vlan_table = self._sbi_rest_driver.get('/interface/bridge/vlan?bridge={}'.format(default_switch_name))
        for vlan_id in vlan_ids:
            row = next((item for item in vlan_table if vlan_id in item['vlan-ids'].split(',')), None)

            if not row:
                raise ValueError('vlan {} not declared'.format(vlan_id))

            row_vlan_ids = row['vlan-ids'].split(',')
            untagged_ports = row['untagged'].split(',')
            tagged_ports = row['tagged'].split(',')

            if len(row_vlan_ids) == 1:
                # in this case we can simply patch row
                updated_row = dict(row)
                updated_row['tagged'] = ','.join(filter(lambda x: x != port.name, tagged_ports))
                updated_row['untagged'] = ','.join(filter(lambda x: x != port.name, untagged_ports))
                self._sbi_rest_driver.patch('/interface/bridge/vlan', updated_row)
            else:
                # in this case we should remove the vlan from the row, and add a new row with only that vlan and the
                # remaining ports
                row['vlan-ids'] = ','.join(filter(lambda x: x != vlan_id, row['vlan-ids']))
                self._sbi_rest_driver.patch('/interface/bridge/vlan', row)
                vlan_row = dict(row)
                vlan_row['vlan-ids'] = vlan_id
                vlan_row['tagged'] = ','.join(filter(lambda x: x != port.name, tagged_ports))
                vlan_row['untagged'] = ','.join(filter(lambda x: x != port.name, untagged_ports))
                self._sbi_rest_driver.put('/interface/bridge/vlan', vlan_row)

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']) -> bool:
        port_table = self._sbi_rest_driver('/interface/bridge/port?bridge')

    def _bind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        logger.warning('VRF not supported in this switch model')
        return False

    def _unbind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        logger.warning('VRF not supported in this switch model')
        return False

    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port) -> bool:
        pass

    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port) -> bool:
        pass

    def commit_and_save(self) -> bool:
        pass
