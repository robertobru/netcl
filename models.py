import datetime
import ipaddress
import json
from datetime import datetime
from typing import Literal, List, Union
from uuid import uuid4
from pydantic import BaseModel, Field, IPvAnyInterface, IPvAnyNetwork, IPvAnyAddress, AnyHttpUrl, model_validator, \
    ConfigDict
from netdevice import Device
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
LinkModes = Literal['ACCESS', 'TRUNK', 'HYBRID', 'NA']
LinkStates = Literal['UP', 'DOWN', 'NA']
LinkAdminStates = Literal['ENABLED', 'DISABLED', 'NA']
SwitchStates = Literal["init", "reinit", "ready", "config_error", "auth_error", "net_error", "executing"]


class PollingOperationLinks(BaseModel):
    href: str
    rel: str = "self"
    method: str = "GET"


class CallbackModel(BaseModel):
    id: str
    operation: str
    status: str
    detailed_status: str


class CallbackRequest(BaseModel):
    callback: Union[AnyHttpUrl, None] = None


class RestAnswer202(BaseModel):
    # id: str
    # description: str ='operation submitted'
    status: str = 'InProgress'
    links: List[PollingOperationLinks]


class WorkerMsg(BaseModel):
    operation_id: str = Field(default_factory=lambda: str(uuid4()))
    operation: NetWorkerOperationType
    status: NetWorkerOperationStates = 'InProgress'
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: datetime = None
    # error_detail: Union[None, str] = str

    def produce_rest_answer_202(self) -> RestAnswer202:
        self.to_db()
        return RestAnswer202.model_validate({'links': [{'href': '/operation/{}'.format(self.operation_id)}]})

    def to_db(self) -> None:
        if _db.exists_DB("operations", {'operation_id': self.operation_id}):
            _db.update_DB("operations", json.loads(self.model_dump_json()), {'operation_id': self.operation_id})
        else:
            _db.insert_DB("operations", json.loads(self.model_dump_json()))

    def update_status(self, status: Literal['Failed', 'Success']) -> None:
        self.status = status
        self.end_time = datetime.now()
        self.to_db()
        if hasattr(self, 'callback') and status in ['Failed', 'Success']:
            # FIXME: implement callback
            pass


class SwitchMsg(WorkerMsg, Device):
    pass


class DelSwitchMsg(WorkerMsg):
    switch_name: str


class NetVlan(CallbackRequest):
    vid: int
    cidr: IPvAnyNetwork
    gateway: Union[IPvAnyAddress, None] = None
    group: str  # project
    description: Union[str, None] = None

    @model_validator(mode='after')
    def _validate_gateway_ip(self):
        if self.gateway:
            gateway_ip = ipaddress.IPv4Address(str(self.gateway))
            cidr_net = ipaddress.IPv4Network(str(self.cidr))
            if self.vid > 4000 or self.vid < 20:
                raise ValueError('Vlan identifier out of range')
            if gateway_ip not in cidr_net:
                raise ValueError('The gateway IP address does not match with the network CIDR')
            return self


class NetVlanMsg(WorkerMsg, NetVlan):
    pass


class PortToNetVlans(CallbackRequest):
    fqdn: str
    interface: str
    switch: str
    port: str
    vids: List[int]


class PortToNetVlansMsg(PortToNetVlans, WorkerMsg):
    pass


class PortVlanReport(BaseModel):
    trunk: List[int]
    pvid: int
    mode: str


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


class Vrf(BaseModel):
    name: str
    rd: str
    description: str = ''
    rd_export: List[str] = []
    rd_import: List[str] = []
    ports: List[VlanL3Port]

    def __eq__(self, other):
        return self.name == other.name and self.rd == other.rd


class NetworkVrf(Vrf):
    device: str


class ConfigItem(BaseModel):
    time: datetime
    config: str


class LldpNeighbor(BaseModel):
    neighbor: str
    remote_interface: str


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


class SwitchDataModel(Device):
    phy_ports: List[PhyPort] = []
    vlan_l3_ports: List[VlanL3Port] = []
    vrfs: List[Vrf] = []
    vlans: List[int] = []
    config_history: List[ConfigItem] = []
    last_config: Union[ConfigItem, None] = None
    state: SwitchStates = "init"


class VlanInterfaceTermination(BaseModel):
    name: str
    switch_name: str


class VlanTerminations(BaseModel):
    # Attention: This class should not be stored into mongo
    model_config = ConfigDict(arbitrary_types_allowed=True)

    vlan_interface: Union[VlanInterfaceTermination, None] = None
    server_ports: dict[str, List[str]] = {}
    topology: Union[nx.MultiGraph, None] = None
