from pydantic import BaseModel, AnyHttpUrl, IPvAnyNetwork, IPvAnyInterface, Field, field_validator
from netdevice import Vrf
from typing import List, Union, Literal
from uuid import UUID, uuid4
from utils import persistency
from datetime import datetime
import json


_db = persistency.DB()


class PollingOperationLinks(BaseModel):
    href: str
    rel: str = "self"
    method: str = "GET"


class RestAnswer202(BaseModel):
    # id: str
    # description: str ='operation submitted'
    status: str = 'InProgress'
    links: List[PollingOperationLinks]


class WorkerMsg(BaseModel):
    operation_id: str = Field(default_factory=lambda: str(uuid4()))
    operation: Literal['add_switch', 'del_switch', 'add_net_vlan', 'del_net_vlan']
    status: Literal['InProgress', 'Failed', 'Success'] = 'InProgress'
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: datetime = None

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


class CallbackModel(BaseModel):
    id: str
    operation: str
    status: str
    detailed_status: str


class CallbackRequest(BaseModel):
    callback: Union[AnyHttpUrl, None] = None


class NetworkVrf(Vrf):
    device: str


class NetVlan(CallbackRequest):
    vid: int
    cidr: IPvAnyNetwork
    gateway: Union[IPvAnyInterface, None] = None
    group: str  # project
    description: Union[str, None] = None


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
