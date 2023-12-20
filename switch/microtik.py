from sbi.routeros import RosRestSbi
from sbi.netmiko import NetmikoSbi
from .switch_base import Switch
from models import LldpNeighbor, PhyPort, VlanL3Port, Vrf
from pydantic import IPvAnyInterface
from netaddr import IPAddress
from utils import create_logger
from typing import List, Literal

logger = create_logger('microtik')


class Microtik(Switch):
    _sbi_rest_driver: RosRestSbi = None
    _sbi_miko_driver: NetmikoSbi = None

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_rest_driver:
            self._sbi_rest_driver = RosRestSbi(self.to_device_model())
        if not self._sbi_miko_driver:
            self._sbi_miko_driver= NetmikoSbi(self.to_device_model())

    def _retrieve_info(self):
        self.reinit_sbi_drivers()
        self.retrieve_vlans()
        self.retrieve_ports()
        self.retrieve_config()
        self.retrieve_neighbors()

        print(self.model_dump())

    def retrieve_config(self) -> None:
        #export
        _config = self._sbi_miko_driver.get_info("export")
        self.store_config(_config)

    def parse_config(self) -> None:
        pass

    def retrieve_neighbors(self):
        #ip/neighbour print
        neighbours = self._sbi_rest_driver.get('ip/neighbor')

    def retrieve_vlans(self):
        #interface/bridge/vlan print
        vlans = self._sbi_rest_driver.get('interface/bridge/vlan')

    def retrieve_ports(self):
        ports = self._sbi_rest_driver.get('interface?type=ether')

    def retrieve_port_vlan(self, port_index: str) -> dict:
        # interface/bridge/port/vlan print
        pass

    def retrieve_vlan_interface(self, port_index: str) -> dict:
        #interface/vlan print
        pass

    def _add_vlan(self, vlan_ids: List[int]) -> bool:
        #/interface/bridge add name=bridge1 vlan-filtering=yes
        #goto _add_vlan_to_port()
        pass

    def _del_vlan(self, vlan_ids: List[int]) -> bool:
        #/interface/bridge remove numbers=#
        pass

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False) -> bool:
        #/interface/bridge/port add bridge = bridge1 interface = sfp-sfpplus9
        #/interface/bridge/port add bridge = bridge1 interface = sfp-sfpplus10 pvid=10
        #/interface/bridge/port add bridge = bridge1 interface = sfp-sfpplus11 pvid=11
        #goto _set_port_mode()
        pass

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort) -> bool:
        #/interface/bridge/port remove numbers=# (numbers è la riga che vogliamo togliere)
        pass

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']) -> bool:
        #/interface/bridge/vlan add bridge=bridge1 tagged=sfp-sfpplus9 untagged=sfp-sfpplus10 vlan-ids=10
        #/interface/bridge/vlan add bridge=bridge1 tagged=sfp-sfpplus9 untagged=sfp-sfpplus11 vlan-ids=11
        pass

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
