import datetime
import ipaddress
import json
from datetime import datetime
from typing import Literal, List, Union
from uuid import uuid4
from pydantic import BaseModel, Field, IPvAnyInterface, IPvAnyNetwork, AnyHttpUrl, model_validator
from netdevice import Device
from utils import persistency


_db = persistency.DB()


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
    operation: Literal['add_switch', 'del_switch', 'add_net_vlan', 'del_net_vlan', 'mod_net_vlan']
    status: Literal['InProgress', 'Failed', 'Success'] = 'InProgress'
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


class SwitchMsg(Device, WorkerMsg):
    pass


class DelSwitchMsg(WorkerMsg):
    switch_name: str


class NetVlan(CallbackRequest):
    vid: int
    cidr: IPvAnyNetwork
    gateway: Union[IPvAnyInterface, None] = None
    group: str  # project
    description: Union[str, None] = None

    @model_validator(mode='after')
    def _validate_gateway_ip(self):
        if self.gateway:
            gateway_ip = ipaddress.IPv4Address(str(self.gateway))
            cidr_net = ipaddress.IPv4Network(str(self.cidr))
            if gateway_ip not in cidr_net:
                raise ValueError('The gateway IP address does not match with the network CIDR')


class NetVlanMsg(NetVlan, WorkerMsg):
    pass


class PortToNetVlans(CallbackRequest):
    fqdn: str
    interface: str
    switch: str
    port: str
    vids: List[int]


class PortToNetVlansMsg(PortToNetVlans, WorkerMsg):
    pass


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
    ipaddress: Union[IPvAnyInterface, None] = None
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
    mode: Literal['ACCESS', 'TRUNK', 'HYBRID', 'NA']  # this should be converted in enum
    status: Literal['UP', 'DOWN', 'NA'] = 'NA'  # this should be converted in enum
    admin_status: Literal['ENABLED', 'DISABLED', 'NA'] = 'NA'  # this should be converted in enum





class SwitchDataModel(Device):
    phy_ports: List[PhyPort] = []
    vlan_l3_ports: List[VlanL3Port] = []
    vrfs: List[Vrf] = []
    vlans: List[int] = []
    config_history: List[ConfigItem] = []
    last_config: Union[ConfigItem, None] = None
    state: Literal["init", "reinit", "ready", "config_error", "auth_error", "net_error", "executing"] = "init"
