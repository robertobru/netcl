import datetime
from typing import Union, List, Literal

from pydantic import BaseModel, IPvAnyInterface, IPvAnyNetwork

from netdevice import Device


# This files contains the REST models used for switches


class SwitchRequestVlanL3Port(BaseModel):
    # Used to create a new VLAN interface
    vlan: int
    ipaddress: IPvAnyInterface
    cidr: IPvAnyNetwork
    vrf: str = ''
    description: str = ''


class ConfigItem(BaseModel):
    time: datetime.datetime
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


class SwitchDataModel(Device):
    phy_ports: List[PhyPort] = []
    vlan_l3_ports: List[VlanL3Port] = []
    vrfs: List[Vrf] = []
    vlans: List[int] = []
    config_history: List[ConfigItem] = []
    last_config: Union[ConfigItem, None] = None
    state: Literal["init", "reinit", "ready", "config_error", "auth_error", "net_error", "executing"] = "init"
