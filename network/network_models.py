from pydantic import RootModel, BaseModel, ConfigDict, IPvAnyNetwork, IPvAnyInterface, IPvAnyAddress
from typing import Union, List, Tuple
from models import VlanInterfaceTermination, LldpNeighbor
from switch.switch_base import Switch
import networkx as nx
from utils import create_logger
from ipaddress import IPv4Network
from network.nbi_msg_models import SetNetworkConfigRequestMsg
from enum import Enum

logger = create_logger('network')


class BackboneVlanOps(Enum):
    add = 'add'
    delete = 'delete'
    as_is = 'as_is'


class VlanRange(BaseModel):
    min: int
    max: int


class NetworkConfig(BaseModel):  # set config da sergio
    vrf_switch_name: str  # se switch giù errore
    vrf_uplink_vlans: List[int]  # trovare reti modificate e fare commit dei cambi trovati
    vrf_uplink_ip_pool: List[IPv4Network]
    pnf_vlans_pool: List[int] = []
    pnf_merging_vrf_name: str
    pnf_ip_pool: List[IPv4Network]
    as_number: int = 1000
    firewall_uplink_vlan_port: str = None
    firewall_uplink_neighbor: LldpNeighbor = None
    firewall_port_group: str = 'projects'

    @classmethod
    def from_config_msg(cls, msg: SetNetworkConfigRequestMsg):
        def vlanpool_from_ranges(ranges: List[VlanRange]) -> List[int]:
            res = set()
            for _pool in ranges:
                for _vlan in range(_pool.min, _pool.max):
                    res.add(_vlan)
            return list(res)

        def ip_pool_from_ranges(ranges: List[IPvAnyNetwork], subnet_length: int) -> List[IPv4Network]:
            res = []
            for cidr in ranges:
                res.extend(list(IPv4Network(str(cidr)).subnets(new_prefix=subnet_length)))
            return res

        return cls(
            vrf_switch_name=msg.vrf_switch_name,
            vrf_uplink_vlans=vlanpool_from_ranges(msg.uplink_vlans_pools),
            vrf_uplink_ip_pool=ip_pool_from_ranges(msg.uplink_ipaddr_pool, msg.uplink_ipnet_mask),
            pnf_vlans_pool=vlanpool_from_ranges(msg.pnf_vlans_pool),
            pnf_merging_vrf_name=msg.pnf_merging_vrf_name,
            pnf_ip_pool=ip_pool_from_ranges(msg.pnf_ip_pool, msg.pnf_ipnet_mask),
            as_number=msg.as_number,
            firewall_uplink_vlan_port=msg.firewall_uplink_vlan_port,
            firewall_uplink_neighbor=msg.firewall_uplink_neighbor
        )


class NetworkGroupItem(BaseModel):
    name: str
    vrf_name: str
    vlan_ids: List[int] # needed to retrieve info from metal_cl
    # vlan_ip?
    bindings_by_config: List[str]
    bindings_by_status: List[str]

    def __eq__(self, other):
        return self.name == other.name


class NetworkGroups(RootModel):
    root: List[NetworkGroupItem] = []

    def get(self, group_name: str):
        return next((item for item in self.root if item.name == group_name), None)

    def exist(self, group_name: str):
        group = self.get(group_name)
        return True if group else False

    def add(self, name: str, vrf_name: str):
        self.root.append(NetworkGroupItem(name=name, vrf_name=vrf_name))

    def delete(self, group_name: str):
        self.root = [item for item in self.root if item.name != group_name]

    def get_names_of_reserved_vrfs(self):
        return [item.vrf_name for item in self.root]


class PnfElement(NetworkGroupItem):
    name: str
    vlan: int
    ip_address: IPvAnyInterface
    ip_gateway: IPvAnyAddress
    switch_name: str
    port_name: str
    bound_groups: List[str] = []


class NetworkPnfs(NetworkGroups):
    root: List[PnfElement]

    def get(self, pnf_name: str):
        return next((item for item in self.root if item.name == pnf_name), None)

    def exist(self, pnf_name: str):
        pnf = self.get(pnf_name)
        return True if pnf else False

    def add(self, item: PnfElement):
        self.root.append(item)

    def delete(self, pnf_name: str):
        self.root = [item for item in self.root if item.name != pnf_name]


class NetworkState(BaseModel):
    available_vrf_uplink_vlans: List[int] = []
    available_vrf_uplink_subnets: List[IPv4Network] = []
    available_pnf_vlans: List[int] = []
    available_pnf_subnets: List[IPv4Network] = []

    def check_available_vlan(self, vid: int) -> bool:
        return vid in self.available_vrf_uplink_vlans or vid in self.available_pnf_vlans

    def reserve_uplink(self) -> Tuple[int, IPv4Network]:
        return self.available_vrf_uplink_vlans.pop(0), self.available_vrf_uplink_subnets.pop(0)

    def release_uplink(self, vid: int, cidr: Union[IPv4Network, str]):
        if type(cidr) is str:
            cidr = IPv4Network(cidr)
        if vid in self.available_vrf_uplink_vlans:
            raise ValueError('vlan Id {} already available!'.format(vid))
        if cidr in self.available_vrf_uplink_subnets:
            raise ValueError('IP subnet {} already available!'.format(cidr))
        self.available_vrf_uplink_vlans.append(vid)
        self.available_vrf_uplink_vlans.sort()
        self.available_vrf_uplink_subnets.append(cidr)
        self.available_vrf_uplink_subnets.sort()

    def remove_used_vid(self, vid):
        if vid in self.available_vrf_uplink_vlans:
            self.available_vrf_uplink_vlans.remove(vid)
        elif vid in self.available_pnf_vlans:
            self.available_pnf_vlans.remove(vid)

    def remove_used_subnet(self, subnet: Union[IPv4Network, str]):
        if type(subnet) is str:
            subnet = IPv4Network(subnet)

        self.available_vrf_uplink_subnets = [
            item for item in self.available_vrf_uplink_subnets if not item.overlaps(subnet)]

        self.available_pnf_subnets = [
            item for item in self.available_pnf_subnets if not item.overlaps(subnet)]

    def get_and_reserve_pnf_vlan(self):
        return self.available_pnf_vlans.pop(0)

    def get_and_reserve_pnf_subnet(self):
        return self.available_pnf_subnets.pop(0)

    @classmethod
    def from_config(cls, network_config: NetworkConfig):
        return cls(
            available_vrf_uplink_vlans=network_config.vrf_uplink_vlans,
            available_vrf_uplink_ip_pool=network_config.vrf_uplink_ip_pool,
            available_pnf_vlans_pool=network_config.pnf_vlans_pool
        )


class VlanTerminationItemServerPortItem(BaseModel):
    switch_name: str
    port_names: List[str]


class VlanTerminationItemServerPortList(RootModel):
    root: List[VlanTerminationItemServerPortItem] = []

    def get_by_switch(self, switch_name: str) -> VlanTerminationItemServerPortItem:
        return next((item for item in self.root if item.switch_name == switch_name), None)

    def add(self, switch_name: str, port_name: str):
        termination_switch = self.get_by_switch(switch_name)
        if termination_switch:
            if port_name not in termination_switch.port_names:
                termination_switch.port_names.append(port_name)
        else:
            termination_switch = VlanTerminationItemServerPortItem(switch_name=switch_name, port_names=[port_name])
            self.root.append(termination_switch)

    def delete(self, switch_name: str, port_name: str):
        termination_switch = self.get_by_switch(switch_name)
        if termination_switch:
            termination_switch.port_names.remove(port_name)

    def empty(self, switch_name: str) -> bool:
        return len(self.get_by_switch(switch_name).port_names) == 0


class VlanTerminationItem(BaseModel):
    # Attention: This class should not be stored into mongo
    model_config = ConfigDict(arbitrary_types_allowed=True)

    vid: int
    vlan_interface: Union[VlanInterfaceTermination, None] = None
    server_ports: VlanTerminationItemServerPortList = VlanTerminationItemServerPortList()
    topology: Union[nx.MultiGraph, None] = None

    def get_switch_names(self) -> set:
        res = set()
        if self.vlan_interface:
            res.add(self.vlan_interface.switch_name)
        for p in self.server_ports.keys():
            res.add(self.server_ports[p])
        return res

    def check_vlan_need_on_switch(self, switch_name: str):
        return len(self.server_ports[switch_name]) < 1 and self.vlan_interface and \
                            self.vlan_interface.switch_name != switch_name

    def get_tagged_ports_in_switch(self, switch_name: str) -> List[str]:
        return self.server_ports.get_by_switch(switch_name).port_names


class VlanTerminationList(RootModel):
    root: List[VlanTerminationItem] = []

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item) -> VlanTerminationItem:
        return self.root[item]

    def get_by_vid(self, vid: int, create_if_missing: bool = False) -> VlanTerminationItem:
        result = next((item for item in self.root if item.vid == vid), None)
        if not result and create_if_missing:
            result = VlanTerminationItem()
            self.root.append(result)
        return result

    def get_all_vids(self):
        return [item.vid for item in self.root]

    def set_vlan_interface(self, switch: Switch, vid: int):
        termination_item = self.get_by_vid(vid, create_if_missing=True)
        vlan_interface = switch.get_vlaninterface_from_vid(vid)
        termination_item.vlan_interface = VlanInterfaceTermination(name=vlan_interface.index, switch_name=switch.name)

    def set_vlan_server(self, switch: Switch, vid: int, managed_switch_names: List[str]):
        for phy_port in switch.phy_ports:
            if phy_port.is_up() and phy_port.get_neighbor_name() not in managed_switch_names and \
                    phy_port.check_vlan(vid):
                logger.debug('found Vlan {} termination on switch {} port {} towards server {}'
                             .format(vid, switch.name, phy_port.name, phy_port.get_neighbor_name()))
                termination_item = self.get_by_vid(vid, create_if_missing=True)
                termination_item.server_ports.add(switch_name=switch.name, port_name=phy_port.name)
