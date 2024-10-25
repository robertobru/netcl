# generated by datamodel-codegen:
#   filename:  sonic_vlan_interface.yaml
#   timestamp: 2024-05-14T13:31:13+00:00

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName(
    BaseModel
):
    sonic_vlan_interface_vrf_name: Optional[str] = Field(
        None, alias='sonic-vlan-interface:vrf_name'
    )


class PutSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName
):
    pass


class PatchSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName
):
    pass


class GetSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName(
    BaseModel
):
    sonic_vlan_interface_vrf_name: Optional[str] = Field(
        None, alias='sonic-vlan-interface:vrf_name'
    )


class SonicVlanInterfaceIpv6UseLinkLocalOnly(Enum):
    enable = 'enable'
    disable = 'disable'


class SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListIpv6UseLinkLocalOnly(
    BaseModel
):
    sonic_vlan_interface_ipv6_use_link_local_only: Optional[
        SonicVlanInterfaceIpv6UseLinkLocalOnly
    ] = Field(None, alias='sonic-vlan-interface:ipv6_use_link_local_only')


class PutSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListIpv6UseLinkLocalOnly(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListIpv6UseLinkLocalOnly
):
    pass


class PatchSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListIpv6UseLinkLocalOnly(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListIpv6UseLinkLocalOnly
):
    pass


class GetSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListIpv6UseLinkLocalOnly(
    BaseModel
):
    sonic_vlan_interface_ipv6_use_link_local_only: Optional[
        SonicVlanInterfaceIpv6UseLinkLocalOnly
    ] = Field(None, alias='sonic-vlan-interface:ipv6_use_link_local_only')


class SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary(
    BaseModel
):
    sonic_vlan_interface_secondary: Optional[bool] = Field(
        None, alias='sonic-vlan-interface:secondary'
    )


class PostSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary
):
    pass


class PutSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary
):
    pass


class PatchSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary
):
    pass


class GetSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrListSecondary(
    BaseModel
):
    sonic_vlan_interface_secondary: Optional[bool] = Field(
        None, alias='sonic-vlan-interface:secondary'
    )


class Ipv6UseLinkLocalOnly(Enum):
    enable = 'enable'
    disable = 'disable'


class SonicVlanInterfaceListItem(
    BaseModel
):
    vlanName: str
    vrf_name: Optional[str] = None
    ipv6_use_link_local_only: Optional[Ipv6UseLinkLocalOnly] = None


class SonicVlanInterfaceIPAddrListItem(
    BaseModel
):
    vlanName: str
    ip_prefix: str
    secondary: Optional[bool] = None


class SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterfaceVLANINTERFACE(
    BaseModel
):
    VLAN_INTERFACE_LIST: List[
            SonicVlanInterfaceListItem
        ] = []

    VLAN_INTERFACE_IPADDR_LIST: List[
            SonicVlanInterfaceIPAddrListItem
        ] = []



class SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterface(
    BaseModel
):
    VLAN_INTERFACE: SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterfaceVLANINTERFACE = \
        SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterfaceVLANINTERFACE()


class SonicVlanInterfaceSonicVlanInterface(BaseModel):
    sonic_vlan_interface_sonic_vlan_interface: SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterface \
        = Field(SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterface(),
                alias='sonic-vlan-interface:sonic-vlan-interface')


class PostSonicVlanInterfaceSonicVlanInterface(SonicVlanInterfaceSonicVlanInterface):
    pass


class PutSonicVlanInterfaceSonicVlanInterface(SonicVlanInterfaceSonicVlanInterface):
    pass


class PatchSonicVlanInterfaceSonicVlanInterface(SonicVlanInterfaceSonicVlanInterface):
    pass


class GetSonicVlanInterfaceSonicVlanInterface(BaseModel):
    sonic_vlan_interface_sonic_vlan_interface: Optional[
        SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterface
    ] = Field(None, alias='sonic-vlan-interface:sonic-vlan-interface')


class SonicVlanInterfaceSonicVlanInterfaceVlanInterface(BaseModel):
    sonic_vlan_interface_VLAN_INTERFACE: Optional[
        SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterfaceVLANINTERFACE
    ] = Field(None, alias='sonic-vlan-interface:VLAN_INTERFACE')


class PostSonicVlanInterfaceSonicVlanInterfaceVlanInterface(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterface
):
    pass


class PutSonicVlanInterfaceSonicVlanInterfaceVlanInterface(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterface
):
    pass


class PatchSonicVlanInterfaceSonicVlanInterfaceVlanInterface(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterface
):
    pass


class GetSonicVlanInterfaceSonicVlanInterfaceVlanInterface(BaseModel):
    sonic_vlan_interface_VLAN_INTERFACE: Optional[
        SonicVlanInterfaceSonicVlanInterfaceSonicvlaninterfacesonicvlaninterfaceVLANINTERFACE
    ] = Field(None, alias='sonic-vlan-interface:VLAN_INTERFACE')


class VlanInterfaceList(BaseModel):
    sonic_vlan_interface_VLAN_INTERFACE_LIST: List[
            SonicVlanInterfaceListItem
    ] = Field([], alias='sonic-vlan-interface:VLAN_INTERFACE_LIST')


class PutVlanInterfaceList(
    VlanInterfaceList
):
    pass


class PatchVlanInterfaceList(
    VlanInterfaceList
):
    pass


class GetSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceList(BaseModel):
    sonic_vlan_interface_VLAN_INTERFACE_LIST: Optional[
        List[
            SonicVlanInterfaceListItem
        ]
    ] = Field(None, alias='sonic-vlan-interface:VLAN_INTERFACE_LIST')


class PutListVlanInterfaceList(
    VlanInterfaceList
):
    pass


class PatchListVlanInterfaceList(
    VlanInterfaceList
):
    pass


class PostSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName(
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListVrfName,
    SonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceListIpv6UseLinkLocalOnly,
):
    pass


class VlanInterfaceIpaddrList(
    BaseModel
):
    sonic_vlan_interface_VLAN_INTERFACE_IPADDR_LIST: List[
            SonicVlanInterfaceIPAddrListItem
    ] = Field([], alias='sonic-vlan-interface:VLAN_INTERFACE_IPADDR_LIST')


class PutVlanInterfaceIpaddrList(
    VlanInterfaceIpaddrList
):
    pass


class PatchVlanInterfaceIpaddrList(
    VlanInterfaceIpaddrList
):
    pass


class GetSonicVlanInterfaceSonicVlanInterfaceVlanInterfaceVlanInterfaceIpaddrList(
    BaseModel
):
    sonic_vlan_interface_VLAN_INTERFACE_IPADDR_LIST: List[
            SonicVlanInterfaceIPAddrListItem
    ] = Field([], alias='sonic-vlan-interface:VLAN_INTERFACE_IPADDR_LIST')


class PutListVlanInterfaceIpaddrList(
    VlanInterfaceIpaddrList
):
    pass


class PatchListVlanInterfaceIpaddrList(
    VlanInterfaceIpaddrList
):
    pass


class PostListSonicVlanInterface(
    VlanInterfaceList,
    VlanInterfaceIpaddrList,
):
    pass
