from __future__ import annotations
import datetime
from datetime import datetime
from typing import Literal, List, Union, Optional, Tuple
from enum import Enum

from ipaddress import IPv4Network
from pydantic import BaseModel, Field, IPvAnyInterface, IPvAnyNetwork, IPvAnyAddress, ConfigDict
from netdevice import Device
from network.nbi_msg_models import NetVlanMsg
from utils import persistency
import networkx as nx


_db = persistency.DB()
NetWorkerOperationType = Literal[
    'add_switch',
    'del_switch',
    'add_net_vlan',
    'del_net_vlan',
    'mod_net_vlan',
    'add_port_vlan',
    'del_port_vlan',
    'mod_port_vlan'
]
NetWorkerOperationStates = Literal['InProgress', 'Failed', 'Success']

class LinkModes(Enum):
    access = 'ACCESS'
    trunk = 'TRUNK'
    hybrid = 'HYBRID'
    routed= 'ROUTED'
    not_available = 'NA'


LinkStates = Literal['UP', 'DOWN', 'NA']
LinkAdminStates = Literal['ENABLED', 'DISABLED', 'NA']
SwitchStates = Literal["init", "reinit", "ready", "config_error", "auth_error", "net_error", "executing"]


class PollingOperationLinks(BaseModel):
    href: str
    rel: str = "self"
    method: str = "GET"


class NetVlanReport(BaseModel):
    vid: int
    cidr: Union[IPvAnyNetwork, None] = None
    gateway: Union[IPvAnyAddress, None] = None
    group: str  # project
    description: Union[str, None] = None


class PortVlanReport(BaseModel):
    trunk: List[int]
    pvid: int
    mode: str


class FirewallRequestL3Port(BaseModel):
    # Used to create a new VLAN interface
    vlan: int = 0
    intf: str
    ipaddress: IPvAnyInterface
    cidr: IPvAnyNetwork
    vrf: str = 'default'
    description: str = ''

    """@classmethod
    def from_netvlanmsg(cls, msg: NetVlanMsg, vrf_name: str):
        return (cls(
            vlan=msg.vid,
            ipaddress=msg.gateway,
            cidr=msg.cidr,
            vrf=vrf_name,
            description=msg.description
        ))"""


class SwitchRequestVlanL3Port(BaseModel):
    # Used to create a new VLAN interface
    vlan: int
    ipaddress: IPvAnyInterface
    cidr: IPvAnyNetwork
    vrf: str = ''
    description: str = ''

    @classmethod
    def from_netvlanmsg(cls, msg: NetVlanMsg, vrf_name: str):
        return (cls(
            vlan=msg.vid,
            ipaddress=msg.gateway,
            cidr=msg.cidr,
            vrf=vrf_name,
            description=msg.description
        ))


class VlanL3Port(BaseModel):
    index: str
    name: Union[str, None] = None
    vlan: int
    ipaddress: Union[IPvAnyAddress, None] = None
    cidr: Union[IPvAnyInterface, None] = None
    vrf: str = ''
    description: Union[str, None] = None

    def __eq__(self, other: VlanL3Port):
        return self.index == other.index and self.name == other.name and self.name == other.name and \
               self.ipaddress == other.ipaddress and self.cidr == other.cidr and self.vrf == other.vrf


class IpV4Route(BaseModel):
    network: IPvAnyNetwork
    nexthop: Union[IPvAnyAddress, Literal['local']]

    def __eq__(self, other: IpV4Route):
        return self.network == other.network

    def __repr__(self):
        return "{} via {}".format(self.network, self.nexthop)

    def get_prefix_and_prefixlen(self) -> Tuple[str, int]:
        addr = IPv4Network(self.network)
        return addr.network_address, addr.prefixlen

    def get_netmask(self) -> str:
        addr = IPv4Network(self.network)
        return addr.netmask

    def to_IpV4Route(self):
        return IpV4Route.model_validate(self.model_dump())


class BGPRedistribute(Enum):
    connected = 'connected'
    static = 'static'


class BGPPeeringStatus(Enum):
    idle = 'idle'
    connect = 'connect'
    active = 'active'
    opensent = 'opensent'
    openconfirm = 'openconfirm'
    estabilished = 'established'


class BGPAddressFamily(BaseModel):
    protocol: str
    protocol_type: str = Field(..., alias='type')
    redistribute: List[BGPRedistribute] = []
    imports: List[str] = []

    def __eq__(self, other: BGPAddressFamily):
        return self.protocol == other.protocol and self.protocol_type == other.protocol_type and \
               self.redistribute == other.redistribute and self.imports == other.imports


class BGPNeighbor(BaseModel):
    ip: IPvAnyAddress
    remote_as: int  # = Field(..., alias='remote-as')
    description: Optional[str] = None
    ip_source: Optional[IPvAnyAddress] = Field(None, alias='update-source')
    status: Optional[BGPPeeringStatus] = None
    msgrcvd: int = 0
    msgsent: int = 0
    outq: int = 0
    prefrcv: int = 0
    updowntime: str = ''

    def __eq__(self, other: BGPNeighbor):
        return self.ip == other.ip and self.remote_as == other.remote_as and self.ip_source == other.ip_source

    def check_status_change(self, other: BGPNeighbor):
        return self.status != other.status


class BGPRoutingProtocol(BaseModel):
    as_number: int
    router_id: str = ''
    neighbors: List[BGPNeighbor] = []
    address_families: List[BGPAddressFamily] = []

    def __eq__(self, other: BGPRoutingProtocol):
        return self.as_number == other.as_number and self.router_id == other.router_id and \
               self.neighbors == other.neighbors and self.address_families == other.address_families


class StaticRoutingProtocol(BaseModel):
    routes: List[IpV4Route] = []

    def __eq__(self, other: StaticRoutingProtocol):
        return self.routes == other.routes

class RoutingProtocols(BaseModel):
    bgp: Optional[BGPRoutingProtocol] = None
    static: Optional[StaticRoutingProtocol] = None

    def __eq__(self, other: RoutingProtocols):
        return self.bgp == other.bgp and self.static == other.static


class Vrf(BaseModel):
    name: str
    rd: str
    description: str = ''
    rd_export: List[str] = []
    rd_import: List[str] = []
    ports: List[VlanL3Port]
    routing_table: List[IpV4Route] = []
    protocols: Optional[RoutingProtocols] = None

    def __eq__(self, other: Vrf):
        return self.name == other.name and self.rd == other.rd and self.rd_export == other.rd_export and \
               self.rd_import == other.rd_import and self.ports == other.ports and \
               self.routing_table == other.routing_table and self.protocols == other.protocols




class VrfRequest(BaseModel):
    name: str
    rd: Optional[str] = None
    description: str = ''
    protocols: Optional[RoutingProtocols] = None

    @classmethod
    def from_static_route(cls, name: str, route: IpV4Route) -> VrfRequest:
        protocols = RoutingProtocols()
        protocols.static = StaticRoutingProtocol()
        protocols.static.routes.append(route)
        return VrfRequest(name=name, protocols=protocols)


class NetworkVrf(Vrf):
    device: str


class ConfigItem(BaseModel):
    time: datetime
    config: str

    def __eq__(self, other: ConfigItem):
        return self.config == other.config


class LldpNeighbor(BaseModel):
    neighbor: str
    remote_interface: str

    def __eq__(self, other: LldpNeighbor):
        return self.neighbor == other.neighbor and self.remote_interface == other.remote_interface


class PhyPort(BaseModel):
    index: str
    name: Union[str, None] = None
    trunk_vlans: List[int]  # here trunk or access
    access_vlan: Union[int, None] = None
    neighbor: Union[LldpNeighbor, None] = None
    speed: Union[int, None] = None
    duplex: str = 'NA'  # this should be converted in enum
    mode: LinkModes
    status: LinkStates = 'NA'
    admin_status: LinkAdminStates = 'NA'

    def __eq__(self, other: PhyPort):
        return self.index == other.index and self.name == other.name and self.trunk_vlans == other.trunk_vlans and \
               self.access_vlan == other.access_vlan and self.mode == other.mode and \
               self.admin_status == other.admin_status

    def check_vlan(self, vid: int) -> bool:
        return (vid in self.trunk_vlans and self.mode in ['TRUNK', 'HYBRID']) or \
                   (vid == self.access_vlan and self.mode in ['ACCESS', 'HYBRID'])

    def get_neighbor_name(self) -> str:
        if self.neighbor:
            return self.neighbor.neighbor
        else:
            return None

    def is_up(self):
        return self.status == 'UP'


class DiffResult(BaseModel):
    added: SwitchDataModel
    changed: SwitchDataModel
    deleted: SwitchDataModel

class SwitchDataModel(Device):
    phy_ports: List[PhyPort] = []
    vlan_l3_ports: List[VlanL3Port] = []
    vrfs: List[Vrf] = []
    vlans: List[int] = []
    config_history: List[ConfigItem] = []
    last_config: Union[ConfigItem, None] = None
    state: SwitchStates = "init"

    def __eq__(self, other: SwitchDataModel):
        return self.phy_ports == other.phy_ports and self.vlan_l3_ports == other.vlan_l3_ports and \
               self.vrfs == other.vrfs and self.vlans == other.vlans

    def get_diff(self, other: SwitchDataModel) -> DiffResult:
        result = DiffResult()

        def check_difference(first: List, second: List, discr_name: dict) -> dict:
            res = {'added': [], 'changed': [], 'deleted': []}
            if first != second:
                for first_element in first:
                    other_element = next((item for item in second if
                                          getattr(item, discr_name) == getattr(first_element, discr_name)), None)
                    if not other_element:
                        res['added'].append(first_element)
                    else:
                        if first_element != other_element:
                            res['changed'].append(first_element)
                for other_element in second:
                    first_element = next((item for item in first if
                                          getattr(item, discr_name) == getattr(other_element, discr_name)), None)
                    if not first_element:
                        res['deleted'].append(other_element)
            return res

        port_diff = check_difference(self.phy_ports, other.phy_ports, 'index')
        result.added.phy_ports = port_diff['added']
        result.changed.phy_ports = port_diff['changed']
        result.deleted.phy_ports = port_diff['deleted']

        l3port_diff = check_difference(self.vlan_l3_ports, other.vlan_l3_ports, 'index')
        result.added.vlan_l3_ports = l3port_diff['added']
        result.changed.vlan_l3_ports = l3port_diff['changed']
        result.deleted.vlan_l3_ports = l3port_diff['deleted']

        vrf_diff = check_difference(self.vrfs, other.vrfs, 'name')
        result.added.vrfs = vrf_diff['added']
        result.changed.vrfs = vrf_diff['changed']
        result.deleted.vrfs = vrf_diff['deleted']



class VlanInterfaceTermination(BaseModel):
    name: str
    switch_name: str


class VlanTerminations(BaseModel):
    # Attention: This class should not be stored into mongo
    model_config = ConfigDict(arbitrary_types_allowed=True)

    vlan_interface: Union[VlanInterfaceTermination, None] = None
    server_ports: dict[str, List[str]] = {}
    topology: Union[nx.MultiGraph, None] = None

    def get_switch_names(self) -> set:
        res = set()
        if self.vlan_interface:
            res.add(self.vlan_interface.switch_name)
        for p in self.server_ports.keys():
            res.add(self.server_ports[p])
        return res


class FirewallL3Port(VlanL3Port):
    interface_assignment: str


class FirewallPortGroup(BaseModel):
    members: List[str] = []
    description: str
    name: str

class FirewallDataModel(Device):
    phy_ports: List[PhyPort] = []
    l3_ports: List[FirewallL3Port] = []
    vrfs: List[Vrf] = []
    # vlans: List[int] = []
    port_groups: List[FirewallPortGroup] = []
    config_history: List[ConfigItem] = []
    last_config: Union[ConfigItem, None] = None
    state: SwitchStates = "init"
