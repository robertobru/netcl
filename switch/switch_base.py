from __future__ import annotations  # needed to annotate class methods returning instances
from models import *
import abc
import json
from typing import List, Union, Tuple
import traceback
from importlib import import_module
from utils import persistency, create_logger
import datetime
from threading import Thread

_db = persistency.DB()
logger = create_logger('switch')

os_models = {
    'hp_comware': {'module': 'hp_comware', 'class': 'HpComware'},
    'mellanox': {'module': 'mellanox', 'class': 'Mellanox'},
    'microtik': {'module': 'microtik', 'class': 'Microtik'},
    'sonic': {'module': 'sonic', 'class': 'Sonic'}
}


class SwitchNotConnectedException(Exception):
    pass


class SwitchNotAuthenticatedException(Exception):
    pass


class SwitchConfigurationException(Exception):
    pass


class Switch(SwitchDataModel):

    def __eq__(self, other: Switch):
        return self.name == other.name and \
               self.phy_ports == other.phy_ports and \
               self.vlans == other.vlans and self.vrfs == other.vrfs


    def retrieve_info(self):
        self.vlan_l3_ports = []
        self.phy_ports = []
        self.vlans = []
        self.vrfs = []
        self._retrieve_info()
        self.to_db()


    @abc.abstractmethod
    def _retrieve_info(self):
        pass

    def update_info(self):
        logger.info('updating information for switch {}'.format(self.name))
        self.vrfs = []
        self.vlans = []
        self.phy_ports = []
        self.vlan_l3_ports = []

        self._update_info()

    @abc.abstractmethod
    def _update_info(self):
        pass

    @classmethod
    def create(cls, input_data: Device) -> Switch:
        if _db.exists_DB("switches", {"name": input_data.name}):
            raise ValueError("A switch with name {} already exists".format(input_data.name))
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
    def from_db(cls, device_name: str) -> Tuple[Switch, Thread]:
        db_data = _db.findone_DB("switches", {'name': device_name})
        logger.debug("dbdata: {}".format(db_data))
        if not db_data:
            raise ValueError('switch {}'.format(device_name))

        if db_data['model'] not in os_models:
            raise ValueError('OS type {} for switch {} not found'.format(db_data['model'], device_name))
        switch_os = os_models[db_data['model']]
        logger.debug("trying to reinitialize object from os_model: {}".format(switch_os))
        try:
            logger.debug("module: {} data: {}".format(
                getattr(import_module(
                    "switch.{}".format(switch_os['module'])
                ), switch_os['class']),
                db_data
            ))
            switch_obj = getattr(import_module("switch.{}".format(switch_os['module'])), switch_os['class'])(**db_data)
            switch_obj.state = "reinit"
            switch_obj.to_db()
            # sbi_thread = Thread(target=switch_obj.reinit_sbi_drivers)
            sbi_thread = Thread(target=switch_obj.retrieve_info, name=switch_obj.name)
            sbi_thread.start()
            # switch_obj.reinit_sbi_drivers()
            return switch_obj, sbi_thread
        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError('re-initialization for switch {} failed'.format(device_name))

    def to_db(self, backup: bool =False) -> None:
        if backup:
            collection = 'lastconfig'
        else:
            collection = 'switches'

        if _db.exists_DB(collection, {'name': self.name}):
            _db.update_DB(collection, json.loads(self.to_switch_model().model_dump_json()), {'name': self.name})
        else:
            _db.insert_DB(collection, json.loads(self.to_switch_model().model_dump_json()))



    def destroy(self):
        _db.delete_DB("switches", {'name': self.name})

    def to_switch_model(self):
        return Switch.model_validate(self, from_attributes=True)

    def check_status(self):
        return True if self.state == 'ready' else False

    def store_config(self, cfg: str) -> bool:
        if not self.last_config or cfg != self.last_config.config:
            logger.info("switch {} changed its configuration. Updating data".format(self.name))
            self.last_config = ConfigItem(time=datetime.datetime.now(), config=cfg)
            self.config_history.append(self.last_config)
            if len(self.config_history) > 100:
                self.config_history.pop(0)
            return True
        return False

    def reinit_sbi_drivers(self) -> None:
        try:
            self._reinit_sbi_drivers()
            self.state = 'ready'
            logger.info("switch {} passed into ready state".format(self.name))
        except SwitchNotConnectedException:
            self.state = 'net_error'
            logger.error("switch {} passed into net_error state".format(self.name))
        except SwitchNotAuthenticatedException:
            self.state = 'auth_error'
            logger.error("switch {} passed into auth_error state".format(self.name))
        finally:
            # FixMe: do we need to raise an tread event to notify the network topology in case of errors?
            self.to_db()

    @abc.abstractmethod
    def _reinit_sbi_drivers(self) -> None:
        pass

    @abc.abstractmethod
    def commit_and_save(self):
        pass

    def get_port_by_name(self, port_name: str) -> Union[PhyPort, None]:
        try:
            return next(item for item in self.phy_ports if item.name == port_name)
        except StopIteration:
            logger.error("Port {} not found".format(port_name))
            return None

    def get_vlaninterface_from_vid(self, vid: int) -> VlanL3Port:
        return next((item for item in self.vlan_l3_ports if item.vlan == vid), None)

    def add_vlan(self, vlan_ids: List[int]) -> bool:
        # add only vlans not already configured in the switch
        vlan_to_add = [item for item in vlan_ids if item not in self.vlans]
        if not vlan_to_add:
            logger.warn('all the vlan are already configured')
            return True
        else:
            logger.debug("adding vlans {}".format(vlan_to_add))
            return self._add_vlan(vlan_to_add)

    def is_endpoint_for_vlan(self, vlan_id: int, managed_switches: List[str]) -> bool:
        # this function applies check to assess if the current switch is really part of the vlan overlay network
        # to this end, the switch is part if it has a vlan interface or if vlan is applied to any phy interface not
        # neighbouring with managed switches
        if vlan_id in [item.vlan for item in self.vlan_l3_ports]:
            logger.debug("switch {} has a vlan interface for vlan {}".format(self.name, vlan_id))
            return True
        for p in self.phy_ports:
            if vlan_id in p.trunk_vlans and p.neighbor.neighbor not in managed_switches:
                logger.debug("switch {} has at least a port connecting servers with vlan {}".format(self.name, vlan_id))
                return True
        return False

    @abc.abstractmethod
    def _add_vlan(self, vlan_ids: List[int]):
        pass

    def del_vlan(self, vlan_ids: List[int], force: bool = False):
        logger.info('self.vlans: {}'.format(self.vlans))
        existing_vlans = [item for item in vlan_ids if item in self.vlans]
        logger.info('existing_vlans: {}'.format(existing_vlans))
        missing_vlans = list(set(vlan_ids) - set(existing_vlans))
        logger.info('missing_vlans: {}'.format(missing_vlans))
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


    def set_port_mode(self, port_name: str, port_mode: LinkModes):
        port = self.get_port_by_name(port_name)
        if port_mode == port.mode:
            logger.warning("Port {} is already in {} mode".format(port.index, port_mode))
            return True
        return self._set_port_mode(port, port_mode)

    @abc.abstractmethod
    def _set_port_mode(self, port: PhyPort, port_mode: LinkModes) -> bool:
        pass

    def add_vlan_to_port(self, vlan_id: int, port_name: str, port_mode: LinkModes = LinkModes.trunk,
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
        if not pvid and vlan_id not in port.trunk_vlans:
            return self._add_vlan_to_port(vlan_id, port, pvid)
        elif pvid and vlan_id != port.access_vlan:
            return self._add_vlan_to_port(vlan_id, port, pvid)
        else:
            return False

    @abc.abstractmethod
    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False) -> bool:
        pass

    def del_vlan_to_port(self, vlan_ids: List[int], port_name: str, port_mode: LinkModes = LinkModes.trunk) -> bool:
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

    def add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: SwitchRequestVlanL3Port) -> bool:
        if not self.check_status():
            raise ValueError("switch {} is in {} status".format(self.name, self.state))
        if vlan_interface.vlan not in self.vlans:
            logger.warn("vlan {} not configured on switch {}. Adding it.".format(vlan_interface.vlan, self.name))
            self.add_vlan([vlan_interface.vlan])

        return self._add_vlan_to_vrf(vrf, vlan_interface)

    @abc.abstractmethod
    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: SwitchRequestVlanL3Port) -> bool:
        pass

    def del_vlan_to_vrf(self, vrf_name: str, vlan_id: int) -> bool:
        if not self.check_status():
            raise ValueError("switch {} is in {} status".format(self.name, self.state))
        vlan_interface = next((item for item in self.vlan_l3_ports if item.vlan == vlan_id), None)
        if not vlan_interface:
            raise ValueError('Vlan interface with vlan id {} non existing on switch {}'.format(
                vlan_id, self.name))
        selected_vrf = next(item for item in self.vrfs if item.name == vrf_name)
        if vlan_interface.vrf != vrf_name:
            raise ValueError('Vlan interface with vlan id {} is not associated to the vrf {} in switch {}'.format(
                vlan_id, vrf_name, self.name))
        return self._del_vlan_to_vrf(selected_vrf, vlan_interface)

    def add_vrf(self, vrf_msg: VrfRequest):
        if vrf_msg.name in [item.name for item in self.vrfs]:
            raise ValueError("VRF {} already existing in switch {}. Vrf creation aborted.".format(
                vrf_msg.name, self.name))
        self._add_vrf(vrf_msg)

    def set_vrf_routing(self, vrf: Vrf, vrf_msg: VrfRequest):
        if vrf_msg.protocols:
            if vrf_msg.protocols.bgp:
                self._add_bgp_instance(vrf_msg)
            if vrf_msg.protocols.static:
                for route in vrf_msg.protocols.static.routes:
                    self.add_route(vrf, route)

    def add_route(self, vrf: Vrf, route: IpV4Route):
        if not vrf.protocols:
            vrf.protocols = RoutingProtocols()
        if not vrf.protocols.static:
            vrf.protocols.static = StaticRoutingProtocol

        self._add_route(vrf, route)

    def del_route(self, vrf: Vrf, route: IpV4Route):
        self._del_route(vrf, route)

    @abc.abstractmethod
    def _add_route(self, vrf: Vrf, route: IpV4Route):
        pass

    @abc.abstractmethod
    def _del_route(self, vrf: Vrf, route: IpV4Route):
        pass

    def _add_bgp_instance(self, vrf_msg: VrfRequest):
        raise ValueError('BGP Routing not supported in this switch OS')

    def _del_bgp_instance(self, vrf_name: str):
        raise ValueError('BGP Routing not supported in this switch OS')

    def get_bgp_peers(self, exclude: str =None):
        peers = []
        for vrf in self.vrfs:
            if vrf.protocols.bgp and exclude != vrf.name:
                for vrf_peer in vrf.protocols.bgp.neighbors:
                    if vrf_peer not in peers:
                        peers.append(vrf_peer)
        return peers

    @abc.abstractmethod
    def _add_vrf(self, vrf_msg: VrfRequest):
        pass

    def del_vrf(self, vrf_name: str):
        vrf = next((item for item in self.vrfs if item.name == vrf_name), None)
        if not vrf:
            raise ValueError("Vrf {} not found on switch {}".format(vrf_name, self.name))
        self._del_vrf(vrf_name)

    @abc.abstractmethod
    def _del_vrf(self, vrf_name: str):
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

    def get_neighbors(self, port_name=None) -> Union[LldpNeighbor, List[LldpNeighbor]]:
        if port_name:
            return next(
                (item.neighbor for item in self.phy_ports if item.name == port_name or item.index == port_name), None)
        else:
            return [item.neighbor for item in self.phy_ports if item.neighbor]

    def get_last_config(self) -> str:
        return self.last_config.config
