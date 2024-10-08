from __future__ import annotations  # needed to annotate class methods returning instances
from netdevice import Device
from models import ConfigItem, LldpNeighbor, PhyPort, FirewallL3Port, Vrf, FirewallDataModel, FirewallRequestL3Port, \
    LinkModes, BGPNeighbor
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, \
    SwitchConfigurationException
import abc
import json
from typing import List, Literal, Union, Tuple
import traceback
from importlib import import_module
from utils import persistency, create_logger
import datetime
from threading import Thread

_db = persistency.DB()
logger = create_logger('firewall')

fw_os_models = {
    'pfsense': {'module': 'pfsense', 'class': 'PfSense'}
}


class Firewall(FirewallDataModel):

    def retrieve_info(self):
        self.l3_ports = []
        self.phy_ports = []
        self.port_groups = []
        self.vrfs = []
        self._retrieve_info()
        self.to_db()


    @abc.abstractmethod
    def _retrieve_info(self):
        pass

    def update_info(self):
        logger.info('updating information for firewall {}'.format(self.name))
        self.vrfs = []
        self.phy_ports = []
        self.l3_ports = []
        self.port_groups = []
        self._update_info()

    @abc.abstractmethod
    def _update_info(self):
        pass

    @classmethod
    def create(cls, input_data: Device) -> Firewall:
        if _db.exists_DB("firewalls", {"name": input_data.name}):
            raise ValueError("A firewall with name {} already exists".format(input_data.name))
        if input_data.model not in fw_os_models:
            raise ValueError("Firewall OS model not supported")
        firewall = getattr(
            import_module(
                "firewall.{}".format(fw_os_models[input_data.model]['module'])
            ), fw_os_models[input_data.model]['class']
        ).model_validate(input_data.model_dump())
        try:
            firewall.retrieve_info()
            firewall.state = "ready"
        except SwitchNotAuthenticatedException:
            logger.error("firewall {} authentication failed".format(input_data.name))
            firewall.state = "auth_error"
        except SwitchNotConnectedException:
            logger.error("firewall {} not reachable".format(input_data.name))
            firewall.state = "net_error"
        return firewall

    @classmethod
    def from_db(cls, device_name: str) -> Tuple[Firewall, Thread]:
        db_data = _db.findone_DB("firewalls", {'name': device_name})
        # logger.debug("dbdata: {}".format(db_data))
        if not db_data:
            raise ValueError('switch {}'.format(device_name))

        if db_data['model'] not in fw_os_models:
            raise ValueError('OS type {} for switch {} not found'.format(db_data['model'], device_name))
        firewall_os = fw_os_models[db_data['model']]
        logger.debug("trying to reinitialize object from fw_os_model: {}".format(firewall_os))
        try:
            firewall_obj = getattr(import_module("firewall.{}".format(firewall_os['module'])), firewall_os['class'])(**db_data)
            firewall_obj.state = "reinit"
            firewall_obj.to_db()
            # sbi_thread = Thread(target=switch_obj.reinit_sbi_drivers)
            sbi_thread = Thread(target=firewall_obj.retrieve_info, name=firewall_obj.name)
            sbi_thread.start()
            # switch_obj.reinit_sbi_drivers()
            return firewall_obj, sbi_thread
        except Exception:
            logger.error(traceback.format_exc())
            raise ValueError('re-initialization for firewall {} failed'.format(device_name))

    def to_db(self) -> None:
        if _db.exists_DB("firewalls", {'name': self.name}):
            _db.update_DB("firewalls", json.loads(self.to_firewall_model().model_dump_json()), {'name': self.name})
        else:
            _db.insert_DB("firewalls", json.loads(self.to_firewall_model().model_dump_json()))

    def destroy(self) -> None:
        _db.delete_DB("switches", {'name': self.name})

    def to_firewall_model(self) -> FirewallDataModel:
        return FirewallDataModel.model_validate(self, from_attributes=True)

    def check_status(self):
        return True if self.state == 'ready' else False

    def store_config(self, cfg: str) -> bool:
        if not self.last_config or cfg != self.last_config.config:
            logger.info("firewall {} changed its configuration. Updating data".format(self.name))
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
            logger.info("firewall {} passed into ready state".format(self.name))
        except SwitchNotConnectedException:
            self.state = 'net_error'
            logger.error("firewall {} passed into net_error state".format(self.name))
        except SwitchNotAuthenticatedException:
            self.state = 'auth_error'
            logger.error("firewall {} passed into auth_error state".format(self.name))
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

    def add_vlan_to_port(self, vlan_id: int, port_name: str, port_mode: LinkModes = LinkModes.trunk,
                         pvid: bool = False, description: str = '') -> bool:
        port = self.get_port_by_name(port_name)
        if not port:
            return False
        if port.mode != port_mode:
            logger.error("Port {} is not in mode {}. aborting!".format(port_name, port_mode))
            return False

        return self._add_vlan_to_port(vlan_id, port, pvid, description)

    @abc.abstractmethod
    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False, description: str = '') -> bool:
        pass

    def del_vlan_to_port(self, vlan_ids: List[int], port_name: str, port_mode: LinkModes = LinkModes.trunk,
                         description: str = '') -> bool:
        port = self.get_port_by_name(port_name)
        if not port:
            return False
        if port.mode != port_mode:
            logger.error("Port {} is not in mode {}. aborting!".format(port_name, port_mode))
            return False
        for vid in vlan_ids:
            if vid in port.trunk_vlans or vid == port.access_vlan:
                logger.warn("vlan {} already configured  in port {}, aborting operation.".format(vid, port_name))
                return False
        return self._del_vlan_to_port(vlan_ids, port, description)

    @abc.abstractmethod
    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort, description: str = '') -> bool:
        pass

    def add_l3port_to_vrf(self, vrf: Vrf, vlan_interface: FirewallRequestL3Port) -> bool:
        if not self.check_status():
            raise ValueError("Firewall {} is in {} status".format(self.name, self.state))
        port = next(item for item in self.phy_ports if item.name == vlan_interface.intf)
        if not port:
            raise ValueError("Port {} not found".format(vlan_interface.intf))
        if vrf.name not in [item.name for item in self.vrfs]:
            raise ValueError("Vrf {} not found".format(vrf.name))

        if vlan_interface.vlan not in port.trunk_vlans or int(vlan_interface.vlan) != port.access_vlan:
            logger.warn("vlan {} not configured on port {}. Adding it.".format(vlan_interface.vlan, port.name))
            self.add_vlan_to_port(
                vlan_id=vlan_interface.vlan,
                port_name=vlan_interface.intf,
                port_mode=LinkModes.trunk,
                description=vlan_interface.description
            )

        return self._add_l3port_to_vrf(vrf, vlan_interface)

    @abc.abstractmethod
    def _add_l3port_to_vrf(self, vrf: Vrf, vlan_interface: FirewallRequestL3Port) -> bool:
        pass

    def del_vlan_to_vrf(self, vrf_name: str, vlan_id: int) -> bool:
        if not self.check_status():
            raise ValueError("switch {} is in {} status".format(self.name, self.state))
        vlan_interface = next((item for item in self.vlan_l3_ports if item.vlan == vlan_id), None)
        if not vlan_interface:
            raise ValueError('Vlan interface with vlan id {} non existing on firewall {}'.format(
                vlan_id, self.name))
        selected_vrf = next(item for item in self.vrfs if item.name == vrf_name)
        if vlan_interface.vrf != vrf_name:
            raise ValueError('Vlan interface with vlan id {} is not associated to the vrf {} in firewall {}'.format(
                vlan_id, vrf_name, self.name))
        return self._del_vlan_to_vrf(selected_vrf, vlan_interface)

    @abc.abstractmethod
    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: FirewallL3Port) -> bool:
        pass

    def get_ports(self) -> List[PhyPort]:
        return self.phy_ports

    def get_vlan_interfaces(self, vrf_name: str = None) -> List[FirewallL3Port]:
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

    def add_bgp_peering(self, msg: BGPNeighbor):
        self._add_bgp_peering(msg)

    @abc.abstractmethod
    def _add_bgp_peering(self, msg: BGPNeighbor):
        pass

    def del_bgp_peering(self, msg: BGPNeighbor):
        self._del_bgp_peering(msg)

    @abc.abstractmethod
    def _del_bgp_peering(self, msg: BGPNeighbor):
        pass

    @abc.abstractmethod
    def _add_l3port_to_group(self, vlan_interface: FirewallRequestL3Port, fw_port_group: str):
        pass

    @abc.abstractmethod
    def _del_l3port_to_group(self, vlan_interface: FirewallRequestL3Port, fw_port_group: str):
        pass
