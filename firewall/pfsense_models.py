from pydantic import BaseModel, Field, IPvAnyAddress, RootModel, model_validator, ValidationError
from typing import List, Optional, Any, Dict, Literal, Union
from models import PhyPort
from enum import Enum


class PfSenseInterfaceMapItem(BaseModel):
    intf: str = Field(..., alias='if')
    descr: str
    spoofmac: Optional[str] = None
    enable: bool
    ipaddr: Optional[IPvAnyAddress] = None
    subnet: Optional[int] = None
    ipaddrv6: Optional[IPvAnyAddress] = None
    subnetv6: Optional[int] = None

    @model_validator(mode="wrap")
    def _check_whether_interface_is_enabled(self, handler):
        # this validator is needed because in the rest reply if the interface is enabled, it only puts a key "enable"
        # with an empty string
        self["enable"] = True if "enable" in self.keys() else False
        return handler(self)


class PfSenseInterfaceMap(RootModel):
    root: Dict[str, PfSenseInterfaceMapItem]


class PfSenseInterface(BaseModel):
    adv_dhcp_config_advanced: bool = False
    adv_dhcp_config_file_override: bool = False
    adv_dhcp_config_file_override_file: str = None
    adv_dhcp_option_modifiers: str = None
    adv_dhcp_pt_backoff_cutoff: int = Field(None, ge=1)
    adv_dhcp_pt_initial_interval: int = Field(None, ge=1)
    adv_dhcp_pt_reboot: int = Field(None, ge=1)
    adv_dhcp_pt_retry: int = Field(None, ge=1)
    adv_dhcp_pt_select_timeout: int = Field(None, ge=1)
    adv_dhcp_pt_timeout: int = Field(None, ge=1)
    adv_dhcp_request_options: str = None
    adv_dhcp_required_options: str = None
    adv_dhcp_send_options: str = None
    alias_address: str = Field(None, alias='alias-address')
    alias_subnet: int = Field(None, ge=1, le=32, alias='alias-subnet')
    apply: bool = False
    blockbogons: bool = False
    descr: str
    dhcpcvpt: int = Field(None, ge=0, le=7)
    dhcphostname: str = None
    dhcprejectfrom: List[str] = None
    dhcpvlanenable: bool = False
    enable: bool = False  # Enable interface upon creation.
    gateway: str = None  # Name of the upstream IPv4 gateway
    gateway_6rd: str = Field(None, alias='gateway-6rd')
    gatewayv6: str = None  # Name of the upstream IPv6 gateway
    intf: str
    ipaddr: IPvAnyAddress = None  # Interface's static IPv4 address. Required if type is set to staticv4.
    ipaddrv6: IPvAnyAddress = None  # Interface's static IPv6 address. Required if type6 is set to staticv6.
    ipv6usev4iface: bool = False
    media: str = None
    mss: str = None  # maximum: 65535, minimum: 576
    mtu: int = Field(None, ge=1280, le=8192)
    prefix_6rd: str = Field(0, alias='prefix-6rd', le=0, ge=32)
    spoofmac: str  # Custom MAC addr to assign to the interface
    subnet: int = Field(None, ge=1, le=32)
    subnetv6: str = None
    track6_interface: str = Field(None, alias='track6-interface')
    track6_prefix_id_hex: int = Field(None, alias='track6-prefix-id-hex')
    type: Literal['staticv4', 'dhcp'] = None
    type6: Literal['staticv6', 'dhcp6', 'slaac', '6rd', 'track6', '6to4 ']


class PfSenseAvailableInterfaceItem(BaseModel):
    mac: str = None
    up: bool = None
    dmesg: Optional[str] = None
    ipaddr: IPvAnyAddress = None
    friendly: str = None
    in_use: str = None
    tag: int = None
    pcp: str = None
    descr: str = None
    vlanif: str = None
    isvlan: bool = False


class PfSenseAvailableInterfaceMap(RootModel):
    root: Dict[str, PfSenseAvailableInterfaceItem]

    def to_phy_port_list(self):
        return [PhyPort(
            index=index,
            name=self.root[index].descr if self.root[index].descr else index,
            trunk_vlans=[],
            status='UP' if self.root[index].up else 'DOWN',
            mode='ROUTED',
            admin_status='ENABLED'
        ) for index in self.root.keys() if not self.root[index].isvlan]


class PfSenseGroup(BaseModel):
    members: str = ""
    descr: str = ''
    ifname: str


class PfSense_GroupList(RootModel):
    root: List[PfSenseGroup]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class PfSense_Rule_EndpointWildcard(BaseModel):
    any: str = ""


class PfSense_Rule_Endpoint(BaseModel):
    address: str = ""
    port: str = ""

    @model_validator(mode='after')
    def check_address_and_port(cls, values):
        if not values.address and not values.port:
            raise ValidationError('Both address and port cannot be empty')
        return values


class PfSense_TimeRecord(BaseModel):
    time: str
    username: str


class IPProtocol(Enum):
    inet = 'inet'
    inet6 = 'inet6'
    inet46 = 'inet46'


class Direction(Enum):
    ingress = 'in'
    egress = 'out'


class YesNo(Enum):
    yes = 'yes'
    no = 'no'


class RuleActionType(Enum):
    block = "block"
    accept = "pass"

class RuleStateType(Enum):
    keep = "keep state"

class PfSense_Rule(BaseModel):
    id: str = ""
    tracker: Optional[str] = None
    type: RuleActionType = None
    interface: List[str]  # "opt7,opt8,opt9,opt10,opt11,opt12,opt13,opt14,opt15,opt16",
    ipprotocol: IPProtocol = IPProtocol.inet,
    tag: Optional[str] = None
    tagged: Optional[str] = None
    direction: Direction = Direction.egress
    floating: YesNo = YesNo.yes
    max: Optional[str] = None
    max_src_nodes: Optional[str] = Field(None, alias="max-src-nodes")
    max_src_conn: Optional[str] = Field(None,  alias="max-src-conn")
    max_src_states: Optional[str] = Field(None,  alias="max-src-states")
    statetimeout: Optional[str] = None
    statetype: RuleStateType = RuleStateType.keep
    os: str = ""
    source: Union[PfSense_Rule_Endpoint, PfSense_Rule_EndpointWildcard] = PfSense_Rule_EndpointWildcard()
    destination: Union[PfSense_Rule_Endpoint, PfSense_Rule_EndpointWildcard] = PfSense_Rule_EndpointWildcard()
    protocol: Optional[Literal['tcp', 'udp', 'icmp', 'tcp/udp']] = None
    associated_rule_id: Optional[str] = Field(None, alias="associated-rule-id")
    descr: str = ""
    updated: PfSense_TimeRecord = None
    created: PfSense_TimeRecord = None
    disabled: str = ""

    @model_validator(mode="wrap")
    def _transform_interface_from_str_to_list(self, handler):
        # this validator is needed because in the rest reply if the interface is enabled, it only puts a key "enable"
        # with an empty string
        self["interface"] = self["interface"].split(',')
        return handler(self)


class PfSense_RuleList(RootModel):
    root: List[PfSense_Rule]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]
