from ipaddress import IPv4Network
from typing import List, Tuple, Union, Any

from datamodel_code_generator.model.pydantic_v2 import RootModel
from pydantic import BaseModel

from firewall.firewall_base import Firewall
from models import PhyPort, VrfRequest
from network_models import NetworkConfig, NetworkState
from network.nbi_msg_models import SetNetworkConfigRequestMsg, PortToNetVlansMsg
from switch import Switch
from utils import persistency, create_logger

_db = persistency.DB()
logger = create_logger('network')

class ManagedSwitches(RootModel):
    root: List[Switch]

    def get_switch_by_attribute(self, attribute: str, value: Any) -> Switch:
        return next((item for item in self.root if hasattr(item, attribute) and getattr(item, attribute) == value),
                    None)

    def get_attribute_by_selector(
            self,
            attribute_name: str,
            selector_name: str,
            selector_value: Any,
            switch_name: str = None
    ) -> Tuple[Union[Switch, None], Any]:

        def _get_attribute_by_selector_single_switch(
                switch: Switch,
                attribute_name: str,
                selector_name: str,
                selector_value: Any
        ) -> Any:
            if not hasattr(switch, attribute_name):
                raise ValueError("Switch {} doesn't have attribute {}".format(switch.name, attribute_name))
            for attribute_item in getattr(switch, attribute_name):
                if getattr(attribute_item, selector_name) == selector_value:
                    return getattr(switch, selector_name)
            return None

        if switch_name is None:
            # we should look into the attributes of all switches
            for switch in self.root:
                attribute = _get_attribute_by_selector_single_switch(
                    switch, attribute_name, selector_name, selector_value)
                if attribute:
                    return switch, attribute
            return None, None
        else:
            switch = self.get_switch_by_attribute('name', switch_name)
            return switch, _get_attribute_by_selector_single_switch(
                switch, attribute_name, selector_name, selector_value)

    def get_switch_names(self):
        return [item.name for item in self.root]

    def check_switch_ready(self):
        for switch in self.root:
            if switch.state != 'ready':
                return False
        return True

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item) -> Switch:
        return self.root[item]

    def append(self, item: Switch) -> None:
        self.root.append(item)

    def delete(self, switch_name: str) -> None:
        switch_to_destroy = self.get_switch_by_attribute('name', switch_name)
        if not switch_to_destroy:
            raise ValueError("Switch {} doesn't exist".format(switch_name))
        switch_to_destroy.destroy()
        self.root = [item for item in self.root if item.name != switch_name]


class NetworkBase(BaseModel):
    switches: ManagedSwitches = []
    vrf_switch: Switch = None
    firewall: Firewall = None
    config: NetworkConfig = None
    status: NetworkState = NetworkState()
    unconfigured: bool = True

    def __init__(self):
        db_config = _db.findone_DB('config', {})
        if db_config:
            self.config = NetworkConfig.model_validate(db_config)
            self.unconfigured = False
        db_status = _db.findone_DB('status', {})
        if db_status:
            self.status = NetworkState.model_validate(db_status)
            #FixMe: rebuild the network state

        db_switches = _db.find_DB('switches', {})
        threads = []
        for sw in db_switches:
            switch_obj, switch_thread = Switch.from_db(device_name=sw['name'])
            self.switches.append(switch_obj)
            threads.append(switch_thread)

        db_fw = _db.findone_DB('firewall', {})
        if db_fw:
            firewall, fw_thread = Firewall.from_db(device_name=db_fw['name'])
            self.firewall = firewall
            threads.append(fw_thread)

        for t in threads:
            t.join()
            logger.info('init for device thread {} terminated'.format(t.name))

    def set_config(self, msg: SetNetworkConfigRequestMsg):
        self.config = NetworkConfig.from_config_msg(msg)

    def build_network_state(self):
        self.status = NetworkState.from_config(self.config)
        for switch_item in self.switches:
            for vid in switch_item.vlans:
                self.status.remove_used_vid(vid)
            for vlan_itf in switch_item.vlan_l3_ports:
                self.status.remove_used_subnet(IPv4Network(vlan_itf.cidr, strict=False))
            # FixMe: add also routing table items?
        if self.config.vrf_switch_name:
            self.vrf_switch = self.switches.get_switch_by_attribute('name', self.config.vrf_switch_name)
            if not self.vrf_switch:
                raise ValueError("vrf_switch {} does not exists".format(self.config.vrf_switch_name))

    def _check_fw_vrf_management(self) -> bool:
        switch_names = self.switches.get_switch_names()
        if not self.config.firewall_uplink_neighbor:
            return False

        uplink_switch, uplink_port = self._get_firewall_neighbor_switch_and_port()

        return self.config.vrf_switch_name in switch_names and self.firewall and \
               self.config.firewall_uplink_vlan_port in [item.name for item in self.firewall.l3_ports] and \
               uplink_switch and uplink_port

    def _get_firewall_neighbor_switch_and_port(self) -> Tuple[Switch, PhyPort]:
        uplink_switch = self.switches.get_switch_by_attribute('name', self.config.firewall_uplink_neighbor.neighbor)
        uplink_port = uplink_switch.get_port_by_name(self.config.firewall_uplink_neighbor.remote_interface) if \
            uplink_switch else None
        return uplink_switch, uplink_port

    def backup_switch_objects(self):
        for s in self.switches:
            s.to_db(backup=True)

    def _get_port_node_objs(self, msg: PortToNetVlansMsg) -> Tuple[Union[Switch, Firewall], PhyPort]:
        managed_nodes = [s for s in self.switches]
        if self.firewall:
            managed_nodes.append(self.firewall)
        node = next(item for item in managed_nodes if item.name == msg.node)
        port = next(item for item in node.phy_ports if item.name == msg.port or item.index == msg.port)
        return node, port

    def _get_switch_by_vrf(self, vrf_name: str) -> Switch:
        switch, vrf = self.switches.get_attribute_by_selector(
            attribute_name='vrf', selector_name='name', selector_value=vrf_name
        )
        return switch

    def get_switch_by_vlan_interface(self, vlan_id: int):
        switch, l3itf = self.switches.get_attribute_by_selector(
            attribute_name='vlan_l3_ports', selector_name='vlan', selector_value=vlan_id
        )
        return switch

    def create_vrf(self, vrf_name: str) -> str:
        msg = VrfRequest.model_validate({'name': vrf_name})
        return self.vrf_switch.add_vrf(msg)

    def delete_vrf(self, vrf_name: str):
        return self.vrf_switch.remove_vrf(vrf_name)
