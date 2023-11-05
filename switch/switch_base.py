from netdevice import Device, PhyPort, VlanL3Port, Vrf, ConfigItem, LldpNeighbor
import abc
from typing import List, Literal, Union
import traceback
from importlib import import_module
from utils import persistency, create_logger
import datetime

_db = persistency.DB()
logger = create_logger('switch')

os_models = {
    'hp_comware': {'module': 'hp_comware', 'class': 'HpComware'},
    'mellanox': {'module': 'mellanox', 'class': 'Mellanox'},
}


class SwitchNotConnectedException(Exception):
    pass


class SwitchNotAuthenticatedException(Exception):
    pass


class SwitchConfigurationException(Exception):
    pass


class Switch(Device):
    phy_ports: List[PhyPort] = []
    vlan_l3_ports: List[VlanL3Port] = []
    vrfs: List[Vrf] = []
    vlans: List[int] = []
    config_history: List[ConfigItem] = []
    last_config: ConfigItem = None
    state: Literal["init", "ready", "config_error", "auth_error", "net_error", "executing"] = "init"

    @abc.abstractmethod
    def retrieve_info(self):
        pass

    @classmethod
    def create(cls, input_data: Device):
        # Fixme: check db to assure there are no other switches with the same name/address
        if input_data.model not in os_models:
            raise ValueError("Switch OS model not supported")
        switch = getattr(
            import_module(
                "switch.{}".format(os_models[input_data.model]['module'])
            ), os_models[input_data.model]['class']
        ).model_validate(input_data.model_dump())
        try:
            switch.retrieve_info()
            switch.state = "ready"
        except SwitchNotAuthenticatedException:
            logger.error("switch {} authentication failed".format(input_data.name))
            switch.state = "auth_error"
        except SwitchNotConnectedException:
            logger.error("switch {} not reachable".format(input_data.name))
            switch.state = "net_error"
        return switch

    @classmethod
    def from_db(cls, device_name: str):
        db_data = _db.findone_DB("switches", {'name': device_name})
        if not db_data:
            raise ValueError('switch {}'.format(device_name))

        if db_data['model'] not in os_models:
            raise ValueError('OS type {} for switch {} not found'.format(db_data['model'], device_name))
        switch_os = os_models[db_data['model']]
        try:
            return getattr(import_module(
                    "switch.{}".format(os_models[switch_os]['module'])
                ), os_models[switch_os]['class'])(**db_data)
        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError('re-initialization for switch {} failed'.format(device_name))

    def to_db(self):
        if self.db.exists_DB("switches", {'name': self.name}):
            self.db.update_DB("switches", self.to_switch_model().model_dump_json(), {'name': self.name})
        else:
            self.db.insert_DB("switches", self.to_switch_model().model_dump_json())

    def to_switch_model(self):
        return Switch.model_validate(self, from_attributes=True)

    def to_device_model(self) -> Device:
        return Device.model_validate(self, from_attributes=True)

    def store_config(self, cfg: str) -> bool:
        if not self.last_config or cfg != self.last_config.config:
            logger.info("switch {} changed its configuration. Updating data")
            self.last_config = ConfigItem(time=datetime.datetime.now(), config=cfg)
            self.config_history.append(self.last_config)
            if len(self.config_history) > 100:
                self.config_history.pop(0)
            return True
        return False

    @abc.abstractmethod
    def commit_and_save(self):
        pass

    def get_port_by_name(self, port_name: str) -> Union[PhyPort, None]:
        try:
            return next(item for item in self.phy_ports if item.name == port_name)
        except StopIteration:
            logger.error("Port {} not found".format(port_name))
            return None

    def add_vlan(self, vlan_ids: List[int]) -> bool:
        # add only vlans not already configured in the switch
        vlan_to_add = [item for item in vlan_ids if item not in self.vlans]
        if not vlan_to_add:
            logger.warn('all the vlan are already configured')
            return True
        else:
            return self._add_vlan(vlan_to_add)

    @abc.abstractmethod
    def _add_vlan(self, vlan_ids: List[int]):
        pass

    def del_vlan(self, vlan_ids: List[int], force: bool = False):
        existing_vlans = [item for item in vlan_ids if item in self.vlans]
        missing_vlans = list(set(vlan_ids) - set(existing_vlans))
        if missing_vlans:
            if force:
                logger.warn('vlans {} are not configured in this switch. Skipping.'.format(missing_vlans))
            else:
                logger.warn('vlans {} are not configured in this switch. Aborting.'.format(missing_vlans))
                return False
        return self._del_vlan(existing_vlans)

    @abc.abstractmethod
    def _del_vlan(self, vlan_ids: List[int]):
        pass

    def get_vlans(self) -> List[int]:
        return self.vlans

    def set_port_mode(self, port_name: str, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']):
        port = self.get_port_by_name(port_name)
        if port_mode == port.mode:
            logger.warning("Port {} is already in {} mode".format(port_mode))
        return self._set_port_mode()

    @abc.abstractmethod
    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']) -> bool:
        pass

    def add_vlan_to_port(self, vlan_id: int, port_name: str, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK'] = 'TRUNK',
                         pvid: bool = False) -> bool:
        port = self.get_port_by_name(port_name)
        if not port:
            return False
        if port.mode != port_mode:
            logger.error("Port {} is not in mode {}. aborting!".format(port_name, port_mode))
            return False
        if vlan_id not in self.vlans:
            logger.warn("vlan {} not found, adding to the switch vlans")
            self.add_vlan([vlan_id])
        return self._add_vlan_to_port(vlan_id, port, pvid)

    @abc.abstractmethod
    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False) -> bool:
        pass

    def del_vlan_to_port(self, vlan_ids: List[int], port_name: str, port_mode: Literal['ACCESS', 'TRUNK'] = 'TRUNK') -> bool:
        port = self.get_port_by_name(port_name)
        if not port:
            return False
        if port.mode != port_mode:
            logger.error("Port {} is not in mode {}. aborting!".format(port_name, port_mode))
            return False
        for vid in vlan_ids:
            if vid not in self.vlans:
                logger.warn("vlan {} not found, deletion aborted")
                return False
        return self._del_vlan_to_port(vlan_ids, port)

    @abc.abstractmethod
    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort) -> bool:
        pass

    def get_vrf_by_rd(self, rd: str) -> Vrf:
        return next(item for item in self.vrfs if item.rd == rd)

    def get_vrf_by_name(self, name: str) -> Vrf:
        return next(item for item in self.vrfs if item.rd == name)

    def get_bound_vrfs(self, vrf_name: str) -> List[Vrf]:
        try:
            vrf = next(item for item in self.vrfs if item.name == vrf_name)
        except StopIteration:
            logger.error("Vrf {} not found".format(vrf_name))
            return []
        bound_vrf = []
        for bound_rd in vrf.rd_import:
            try:
                logger.debug("checking RD {} bound to VRF {}".format(bound_rd, vrf_name))
                vrf_to_add = self.get_vrf_by_rd(bound_rd)
                bound_vrf.append(vrf_to_add)
            except StopIteration:
                logger.warning("Route Descriptor {} not found in the switch".format(bound_rd))

    def bind_vrf(self, vrf_name1: str, vrf_name2: str) -> bool:
        try:
            vrf1 = self.get_vrf_by_name(vrf_name1)
            vrf2 = self.get_vrf_by_name(vrf_name2)
        except StopIteration:
            logger.error("one of the vrfs is not existing")
            return False
        if not self.check_vrfs_binding(vrf1, vrf2):
            return self._bind_vrf(vrf1, vrf2)
        else:
            # the two vrfs are already bound
            return True

    def check_vrfs_binding(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        # this function return True if the two vrfs are bound, False if they are unbound
        # if the relationship is asymmetrical, the function raises an exception

        # we need to check if they are bidirectionally bound
        if vrf1 == vrf2:
            # the two vrfs are the same
            return True
        vrfs_bound_to_vrf1 = self.get_bound_vrfs(vrf1.name)
        vrfs_bound_to_vrf2 = self.get_bound_vrfs(vrf2.name)
        vrf2_to_vrf1 = True if [item for item in vrfs_bound_to_vrf1 if item == vrf2] else False
        vrf1_to_vrf2 = True if [item for item in vrfs_bound_to_vrf2 if item == vrf1] else False
        if vrf2_to_vrf1 and vrf1_to_vrf2:
            logger.debug("VRFs {} and {} are bidirectionally bound".format(vrf1.name, vrf2.name))
            return True
        elif not vrf2_to_vrf1 and not vrf1_to_vrf2:
            logger.debug("VRFs {} and {} are bidirectionally unbound".format(vrf1.name, vrf2.name))
            return False
        else:
            raise ValueError("VRFs {} and {} are asymmetrically bound!".format(vrf1.name, vrf2.name))

    def unbind_vrf(self, vrf_name1, vrf_name2):
        try:
            vrf1 = self.get_vrf_by_name(vrf_name1)
            vrf2 = self.get_vrf_by_name(vrf_name2)
        except StopIteration:
            logger.error("one of the vrfs is not existing")
            return False
        if self.check_vrfs_binding(vrf1, vrf2):
            return self._unbind_vrf(vrf1, vrf2)
        else:
            # the two vrfs are already unbound
            return True

    @abc.abstractmethod
    def _bind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    @abc.abstractmethod
    def _unbind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    def add_vlan_to_vrf(self, vrf_name: str, vlan_interface: VlanL3Port) -> bool:
        pass

    @abc.abstractmethod
    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port) -> bool:
        pass

    def del_vlan_to_vrf(self, vrf_name: str, vlan_id: str) -> bool:
        pass

    @abc.abstractmethod
    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port) -> bool:
        pass

    def get_ports(self) -> List[PhyPort]:
        return self.phy_ports

    def get_vlan_interfaces(self, vrf_name: str = None) -> List[VlanL3Port]:
        if not vrf_name:
            return self.vlan_l3_ports
        else:
            vrf_item = next(item for item in self.vrfs if item.name == vrf_name)
            return vrf_item.ports

    def get_vrfs(self) -> List[Vrf]:
        return self.vrfs

    def get_neighbors(self, port_name=None) -> List[LldpNeighbor]:
        if port_name:
            return [item.neighbor for item in self.phy_ports if item.name == port_name]
        else:
            return [item.neighbor for item in self.phy_ports if item.neighbor]

    def get_last_config(self) -> str:
        return self.last_config.config
