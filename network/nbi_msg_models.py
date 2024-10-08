from __future__ import annotations

import datetime
import ipaddress
import json
from datetime import datetime

from typing import Union, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, AnyHttpUrl, Field, IPvAnyNetwork, IPvAnyAddress, model_validator
from pydantic.v1 import IPvAnyInterface

from models import PollingOperationLinks, NetWorkerOperationType, NetWorkerOperationStates, _db, LldpNeighbor, \
    NetVlanReport, IpV4Route
from netdevice import Device
from network.network_models import VlanRange


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
    # this class is the mother class to inherit rest messages and transform them into
    # messages to be elaborated by the main worker thread
    operation_id: str = Field(default_factory=lambda: str(uuid4()))
    operation: NetWorkerOperationType
    status: NetWorkerOperationStates = 'InProgress'
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Union[datetime, None] = None
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

class AddSwitchRequest(Device):
    pass

class AddSwitchRequestMsg(WorkerMsg, Device):
    pass


class DelSwitchRequestMsg(WorkerMsg):
    switch_name: str

class AddPnfRequest(BaseModel):
    name: str
    switch_name: str
    switch_port: str
    vid: Optional[int] = None
    ip_address: IPvAnyInterface
    ip_gateway: IPvAnyAddress

class AddPnfRequestMsg(WorkerMsg, AddPnfRequest):
    pass


class DelPnfRequestMsg(WorkerMsg):
    pnf_name: str


class AddRouteRequest(IpV4Route):
    group: str


class AddRouteRequestMsg(WorkerMsg, AddRouteRequest):
    pass


class DelRouteRequest(IpV4Route):
    group: str


class DelRouteRequestMsg(WorkerMsg, AddRouteRequest):
    pass

class SetNetworkConfigRequestMsg(WorkerMsg):
    vrf_switch_name: str
    uplink_vlans_pools: List[VlanRange]
    uplink_ipaddr_pool: List[IPvAnyNetwork]
    uplink_ipnet_mask: int
    pnf_vlans_pool: List[VlanRange] = []
    pnf_ipaddr_pool: List[IPvAnyNetwork] = []
    pnf_ipnet_mask: int = 0
    pnf_merging_vrf_name: str = 'vrf_router'
    as_number: int = 1000
    firewall_uplink_vlan_port: str = None
    firewall_uplink_neighbor: LldpNeighbor = None


class NetVlan(CallbackRequest, NetVlanReport):
    cidr: IPvAnyNetwork
    gateway: IPvAnyAddress

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
    node: str
    port: str
    vids: List[int]


class PortToNetVlansMsg(WorkerMsg, PortToNetVlans):
    pass
