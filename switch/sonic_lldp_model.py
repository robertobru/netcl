from pydantic import BaseModel, Field
from typing import List


class LLDPNeighInterfaceNeighItemState(BaseModel):
    # chassis_id: str
    # chassis_id_type: "MAC_ADDRESS"
    # id: str
    # management_address: str,
    port_description: str = Field(..., alias='port-description')  # "enp161s0f1np1",
    port_id: str = Field(..., alias='port-id') # "94:6d:ae:ac:1c:75",
    port_id_type: str = Field(..., alias='port-id-type')
    # "port-id-type": "MAC_ADDRESS",
    system_name: str = Field(..., alias='system-name')  # "r2sm2023-0.maas"


class LLDPNeighInterfaceNeighItem(BaseModel):
    id: str
    state: LLDPNeighInterfaceNeighItemState


class LLDPNeighInterfaceNeigh(BaseModel):
    neighbor: List[LLDPNeighInterfaceNeighItem]


class LLDPNeighInterface(BaseModel):
    name: str
    neighbors: LLDPNeighInterfaceNeigh


class LLDPNeigh(BaseModel):
    interface: List[LLDPNeighInterface] = []


class SonicLLDPMsg(BaseModel):
    openconfig_lldp_interfaces: LLDPNeigh = Field(LLDPNeigh(), alias="openconfig-lldp:interfaces")
