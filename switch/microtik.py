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
        _config = self._sbi_miko_driver.get_info("export")
        self.store_config(_config)

    def parse_config(self) -> None:
        pass

    def retrieve_neighbors(self):
        neighbours = self._sbi_rest_driver.get('ip/neighbor')

    def retrieve_vlans(self):
        vlans = self._sbi_rest_driver.get('interface/bridge/vlan')

    def retrieve_ports(self):
        ports = self._sbi_rest_driver.get('interface?type=ether')

    def retrieve_port_vlan(self, port_index: str) -> dict:
        pass

    def retrieve_vlan_interface(self, port_index: str) -> dict:
        pass

    def _add_vlan(self, vlan_ids: List[int]) -> bool:

        pass

    def _del_vlan(self, vlan_ids: List[int]) -> bool:
        pass

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False) -> bool:
        pass

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort) -> bool:
        pass

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']) -> bool:
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
