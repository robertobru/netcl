from sbi.xml import MlnxOsXgRequest, XmlRestSbi, create_multinode_request
from .switch_base import Switch
from netdevice import PhyPort, VlanL3Port, LldpNeighbor, Vrf
from pydantic import IPvAnyInterface
from netaddr import IPAddress
from utils import create_logger
from sbi.netmiko import NetmikoSbi
from typing import List, Literal
import textfsm

logger = create_logger('mlnx_os')


class Mellanox(Switch):
    _sbi_xml_driver: XmlRestSbi = None
    _sbi_ssh_driver: NetmikoSbi = None

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_xml_driver:
            self._sbi_xml_driver = XmlRestSbi(self.to_device_model())
        if not self._sbi_ssh_driver:
            self._sbi_ssh_driver = NetmikoSbi(self.to_device_model())

    def retrieve_info(self):
        self.reinit_sbi_drivers()
        self.retrieve_vlans()
        self.retrieve_ports()
        self.retrieve_config()
        self.retrieve_neighbors()

        print(self.model_dump())

    def retrieve_config(self):
        _config = self._sbi_ssh_driver.get_info("show configuration", enable=True)
        self.store_config(_config[6:])

    def retrieve_neighbors(self):
        neighdata = self._sbi_ssh_driver.get_info("show lldp remote")
        logger.info('{}'.format(neighdata))
        fsm = textfsm.TextFSM(open("fsm_templates/mlnx_lldp_template"))
        res = fsm.ParseText(neighdata)
        logger.info(res)
        for line in res:
            port = next(item for item in self.phy_ports if item.name == line[0])
            port.neighbor = LldpNeighbor(neighbor=line[3], remote_interface=line[2])

    def retrieve_vlans(self):
        vlans_request = self._sbi_xml_driver.post(
            MlnxOsXgRequest.create_single_node_request('/mlnxos/v1/vsr/vsr-default/vlans/*'))
        logger.info(vlans_request.model_dump())
        self.vlans = [int(item.value) for item in vlans_request.actionResponse.nodes.node if item]
        logger.info("VLANs defined: {}".format(self.vlans))

    def retrieve_ports(self):
        ports = self._sbi_xml_driver.post(
            MlnxOsXgRequest.create_single_node_request('/mlnxos/v1/vsr/vsr-default/interfaces/*'))
        logger.info(ports.model_dump())

        port_indexes = [item.value for item in ports.actionResponse.nodes.node]

        port_data_request = create_multinode_request(
            '/mlnxos/v1/vsr/vsr-default/interfaces/{}/*', port_indexes)
        port_data_replies = self._sbi_xml_driver.multi_post(port_data_request)
        logger.info(port_data_replies)

        port_map = {}
        for line in port_data_replies:
            name_split = line.name.split('/')
            port_index = name_split[6]

            if port_index not in port_map:
                port_map[port_index] = {'index': port_index}
            if len(name_split) < 8:
                continue
            if name_split[7] == 'type':
                port_map[port_index]['type'] = line.value
                # check if ethernet port
                if line.value in ['eth', 'splitter']:
                    if 'physical_location' in port_map[port_index].keys():
                        port_map[port_index]['name'] = "Eth{}".format(port_map[port_index]['physical_location'])

                    port_map[port_index] = port_map[port_index] | self.retrieve_port_vlan(port_index)  # merging dicts

                if line.value == 'vlan':
                    port_map[port_index] = port_map[port_index] | self.retrieve_vlan_interface(port_index)

            elif name_split[7] == 'physical_location':
                port_map[port_index]['physical_location'] = line.value
                if 'type' in port_map[port_index].keys() and port_map[port_index]['type'] in ['eth', 'splitter']:
                    port_map[port_index]['name'] = "Eth{}".format(port_map[port_index]['physical_location'])
            elif name_split[7] == 'enabled':
                port_map[port_index]['status'] = 'UP' if line.value == 'true' else 'DOWN'
            elif name_split[7] == 'operational_state':
                port_map[port_index]['admin_status'] = 'ENABLED' if line.value == 'Up' else 'DISABLED'
            elif name_split[7] == 'actual_speed':
                port_map[port_index]['speed'] = int(line.value)
            elif name_split[7] == 'description':
                port_map[port_index]['description'] = line.value

        logger.info(port_map)
        for k in port_map.keys():
            if port_map[k]['type'] in ['eth', 'splitter']:
                port = PhyPort.model_validate(port_map[k])
                self.phy_ports.append(port)
            elif port_map[k]['type'] == 'vlan':
                print('vlan interface {}'.format(port_map[k]))
                port_map[k]['name'] = port_map[k]['physical_location']
                port_map[k]['vlan'] = str(port_map[k]['physical_location'].split()[-1])
                self.vlan_l3_ports.append(VlanL3Port.model_validate(port_map[k]))
            else:
                logger.warning(
                    'found unclassified interface with index {} and type {}'.format(k, port_map[k]['type']))

    def retrieve_port_vlan(self, port_index: str) -> dict:
        # retrieving info on vlans
        port_data = {}
        port_vlan_requests = create_multinode_request(
            '/mlnxos/v1/vsr/vsr-default/interfaces/{}/vlans/**', [port_index])
        logger.info('port_vlan_requests {}'.format(port_vlan_requests))
        port_vlan_replies = self._sbi_xml_driver.multi_post(port_vlan_requests)
        logger.info('port_vlan_replies {}'.format(port_vlan_replies))
        port_data['trunk_vlans'] = []
        port_data['access_vlan'] = None
        for vlan_line in port_vlan_replies:
            if '/{}/vlans/allowed/'.format(port_index) in vlan_line.name:
                port_data['trunk_vlans'].append(int(vlan_line.value))
            elif '/{}/vlans/mode'.format(port_index) in vlan_line.name:
                port_data['mode'] = vlan_line.value.upper()
            elif '/{}/vlans/pvid'.format(port_index) in vlan_line.name:
                port_data['access_vlan'] = int(vlan_line.value)
        return port_data

    def retrieve_vlan_interface(self, port_index: str) -> dict:
        port_data = {}
        # ipv4/ip_address
        ip_port_vlan_requests = create_multinode_request(
            '/mlnxos/v1/vsr/vsr-default/interfaces/{}/ipv4/**', [port_index])
        logger.info('ip_port_vlan_requests {}'.format(ip_port_vlan_requests))
        ip_port_vlan_replies = self._sbi_xml_driver.multi_post(ip_port_vlan_requests)
        logger.info('ip_port_vlan_replies {}'.format(ip_port_vlan_replies))
        _ip_addr = {}
        for ip_line in ip_port_vlan_replies:
            if '/{}/ipv4/ip_address'.format(port_index) in ip_line.name:
                if ip_line.value != '0.0.0.0':
                    _ip_addr['ip_address'] = ip_line.value
            elif '/{}/ipv4/net_mask'.format(port_index) in ip_line.name:
                _ip_addr['net_mask'] = ip_line.value
        if 'ip_address' in _ip_addr.keys() and 'net_mask' in _ip_addr.keys():
            ip_str = "{}/{}".format(_ip_addr['ip_address'], IPAddress(_ip_addr['net_mask']).netmask_bits())
            port_data['ipaddress'] = IPvAnyInterface(ip_str)
        else:
            port_data['ipaddress'] = None
        logger.debug(port_data['ipaddress'])
        port_data['vrf'] = 'vsr-default'
        return port_data

    def _add_vlan(self, vlan_ids: List[int]) -> bool:
        node_template = '/mlnxos/v1/vsr/vsr-default/vlans/add|vlan_id={}'
        port_vlan_requests = create_multinode_request(node_template, vlan_ids, request_type='action')
        logger.info('port_vlan_requests {}'.format(port_vlan_requests))
        try:
            port_vlan_replies = self._sbi_xml_driver.multi_post(port_vlan_requests)
            logger.info('port_vlan_replies {}'.format(port_vlan_replies))
            self.vlans = self.vlans + vlan_ids
            return True
        except Exception:
            logger.error('problems in adding vlan')
            return False

    def _del_vlan(self, vlan_ids: List[int]) -> bool:
        node_template = '/mlnxos/v1/vsr/vsr-default/vlans/delete|vlan_id={}'
        port_vlan_requests = create_multinode_request(node_template, vlan_ids, request_type='action')
        logger.info('port_vlan_requests {}'.format(port_vlan_requests))
        try:
            port_vlan_replies = self._sbi_xml_driver.multi_post(port_vlan_requests)
            logger.info('port_vlan_replies {}'.format(port_vlan_replies))
            self.vlans = list(set(self.vlans) - set(vlan_ids))
            return True
        except Exception:
            logger.error('problems in deleting vlan')
            return False

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, access_vlan: bool = False) -> bool:
        if access_vlan:
            if port.mode == 'TRUNK':
                raise ValueError('Pvid cannot be configured in TRUNK mode, \
                    please consider to switch the mode to HYBRID')
            node_template = '/mlnxos/v1/vsr/vsr-default/interfaces/' + port.index + '/vlans/pvid={}'
            port_vlan_requests = create_multinode_request(node_template, [vlan_id], request_type='action')
            logger.info('port_vlan_requests {}'.format(port_vlan_requests))
            try:
                port_vlan_replies = self._sbi_xml_driver.multi_post(port_vlan_requests)
                logger.info('port_vlan_replies {}'.format(port_vlan_replies))
                port.access_vlan = vlan_id
                return True
            except Exception:
                logger.error('problems in adding access vlan on Port {}'.format(port.name))
                return False
        else:
            if port.mode == 'ACCESS':
                raise ValueError('Tagged Vlans cannot be configured in ACCESS mode, \
                                    please consider to switch the mode to TRUNK/HYBRID')
            node_template = '/mlnxos/v1/vsr/vsr-default/interfaces/' + port.index + '/vlans/allowed/add|vlan_ids={}'
            port_vlan_requests = create_multinode_request(node_template, [vlan_id], request_type='action')
            logger.info('port_vlan_requests {}'.format(port_vlan_requests))
            try:
                port_vlan_replies = self._sbi_xml_driver.multi_post(port_vlan_requests)
                logger.info('port_vlan_replies {}'.format(port_vlan_replies))
                port.trunk_vlans.append(vlan_id)
                return True
            except Exception:
                logger.error('problems in adding tagged vlan on Port {}'.format(port.name))
                return False

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort) -> bool:
        if port.mode == 'ACCESS':
            raise ValueError('Tagged Vlans cannot be configured in ACCESS mode, \
                                please consider to switch the mode to TRUNK/HYBRID')
        node_template = '/mlnxos/v1/vsr/vsr-default/interfaces/{}/vlans/allowed/delete'
        for vid in vlan_ids:
            node_template = node_template + "|vlan_ids={}".format(vid)
        port_vlan_requests = create_multinode_request(node_template, [port.index], request_type='action')
        logger.info('port_vlan_requests {}'.format(port_vlan_requests))
        try:
            port_vlan_replies = self._sbi_xml_driver.multi_post(port_vlan_requests)
            logger.info('port_vlan_replies {}'.format(port_vlan_replies))
            port.trunk_vlans = list(set(port.trunk_vlans) - set(vlan_ids))
            return True
        except Exception:
            logger.error('problems in adding tagged vlan on Port {}'.format(port.name))
            return False

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']) -> bool:
        node_template = '/mlnxos/v1/vsr/vsr-default/interfaces/{}' + '/vlans/mode={}'.format(port_mode.lower())
        port_vlan_requests = create_multinode_request(node_template, [port.index], request_type='action')
        logger.info('port_vlan_requests {}'.format(port_vlan_requests))
        try:
            port_vlan_replies = self._sbi_xml_driver.multi_post(port_vlan_requests)
            logger.info('port_vlan_replies {}'.format(port_vlan_replies))
            port.mode = port_mode
            return True
        except Exception:
            logger.error('problems in adding access vlan on Port {}'.format(port.name))
            return False

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
        #
        # Note: there is no need on this switch to save and commit changes done through the xml rest api
        #
        pass
