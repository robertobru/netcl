# generated by datamodel-codegen:
#   filename:  sonic_portchannel.yaml
#   timestamp: 2024-05-14T13:26:54+00:00

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SonicPortchannelAdminStatus(Enum):
    up = 'up'
    down = 'down'


class SonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus(BaseModel):
    sonic_portchannel_admin_status: Optional[SonicPortchannelAdminStatus] = Field(
        None, alias='sonic-portchannel:admin_status'
    )


class PutSonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus(
    BaseModel
):
    sonic_portchannel_admin_status: Optional[SonicPortchannelAdminStatus] = Field(
        None, alias='sonic-portchannel:admin_status'
    )


class SonicPortchannelSonicPortchannelPortchannelPortchannelListMtu(BaseModel):
    sonic_portchannel_mtu: Optional[int] = Field(None, alias='sonic-portchannel:mtu')


class PutSonicPortchannelSonicPortchannelPortchannelPortchannelListMtu(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListMtu
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelPortchannelListMtu(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListMtu
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelPortchannelListMtu(BaseModel):
    sonic_portchannel_mtu: Optional[int] = Field(None, alias='sonic-portchannel:mtu')


class SonicPortchannelSonicPortchannelPortchannelPortchannelListStatic(BaseModel):
    sonic_portchannel_static: Optional[bool] = Field(
        None, alias='sonic-portchannel:static'
    )


class PutSonicPortchannelSonicPortchannelPortchannelPortchannelListStatic(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListStatic
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelPortchannelListStatic(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListStatic
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelPortchannelListStatic(BaseModel):
    sonic_portchannel_static: Optional[bool] = Field(
        None, alias='sonic-portchannel:static'
    )


class SonicPortchannelSonicPortchannelPortchannelPortchannelListLacpKey(BaseModel):
    sonic_portchannel_lacp_key: Optional[str] = Field(
        None, alias='sonic-portchannel:lacp_key'
    )


class PutSonicPortchannelSonicPortchannelPortchannelPortchannelListLacpKey(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListLacpKey
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelPortchannelListLacpKey(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListLacpKey
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelPortchannelListLacpKey(BaseModel):
    sonic_portchannel_lacp_key: Optional[str] = Field(
        None, alias='sonic-portchannel:lacp_key'
    )


class SonicPortchannelSonicPortchannelPortchannelPortchannelListMinLinks(BaseModel):
    sonic_portchannel_min_links: Optional[int] = Field(
        None, alias='sonic-portchannel:min_links'
    )


class PutSonicPortchannelSonicPortchannelPortchannelPortchannelListMinLinks(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListMinLinks
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelPortchannelListMinLinks(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListMinLinks
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelPortchannelListMinLinks(BaseModel):
    sonic_portchannel_min_links: Optional[int] = Field(
        None, alias='sonic-portchannel:min_links'
    )


class SonicPortchannelSonicPortchannelPortchannelPortchannelListFallback(BaseModel):
    sonic_portchannel_fallback: Optional[bool] = Field(
        None, alias='sonic-portchannel:fallback'
    )


class PutSonicPortchannelSonicPortchannelPortchannelPortchannelListFallback(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListFallback
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelPortchannelListFallback(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListFallback
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelPortchannelListFallback(BaseModel):
    sonic_portchannel_fallback: Optional[bool] = Field(
        None, alias='sonic-portchannel:fallback'
    )


class GetSonicPortchannelSonicPortchannelLagTableLagTableListAdminStatus(BaseModel):
    sonic_portchannel_admin_status: Optional[SonicPortchannelAdminStatus] = Field(
        None, alias='sonic-portchannel:admin_status'
    )


class GetSonicPortchannelSonicPortchannelLagTableLagTableListMtu(BaseModel):
    sonic_portchannel_mtu: Optional[int] = Field(None, alias='sonic-portchannel:mtu')


class GetSonicPortchannelSonicPortchannelLagTableLagTableListActive(BaseModel):
    sonic_portchannel_active: Optional[bool] = Field(
        None, alias='sonic-portchannel:active'
    )


class GetSonicPortchannelSonicPortchannelLagTableLagTableListName(BaseModel):
    sonic_portchannel_name: Optional[str] = Field(None, alias='sonic-portchannel:name')


class SonicPortchannelOperStatus(Enum):
    up = 'up'
    down = 'down'


class GetSonicPortchannelSonicPortchannelLagTableLagTableListOperStatus(BaseModel):
    sonic_portchannel_oper_status: Optional[SonicPortchannelOperStatus] = Field(
        None, alias='sonic-portchannel:oper_status'
    )


class GetSonicPortchannelSonicPortchannelLagTableLagTableListTrafficDisable(BaseModel):
    sonic_portchannel_traffic_disable: Optional[bool] = Field(
        None, alias='sonic-portchannel:traffic_disable'
    )


class AdminStatus(Enum):
    up = 'up'
    down = 'down'


class SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELPORTCHANNELLIST(
    BaseModel
):
    name: str
    admin_status: Optional[AdminStatus] = None
    mtu: Optional[int] = None
    static: Optional[bool] = None
    lacp_key: Optional[str] = None
    min_links: Optional[int] = None
    fallback: Optional[bool] = None


class SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNEL(
    BaseModel
):
    PORTCHANNEL_LIST: List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELPORTCHANNELLIST
        ] = []


class SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBERPORTCHANNELMEMBERLIST(
    BaseModel
):
    name: str
    ifname: str


class SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBER(
    BaseModel
):
    PORTCHANNEL_MEMBER_LIST: List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBERPORTCHANNELMEMBERLIST
        ] = []


class SonicPortchannelSonicPortchannelSonicportchannelsonicportchannel(BaseModel):
    PORTCHANNEL: SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNEL = SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNEL()
    PORTCHANNEL_MEMBER: SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBER = SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBER()


class OperStatus(Enum):
    up = 'up'
    down = 'down'


class GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGTABLELAGTABLELIST(
    BaseModel
):
    lagname: str
    admin_status: Optional[AdminStatus] = None
    mtu: Optional[int] = None
    active: Optional[bool] = None
    name: Optional[str] = None
    oper_status: Optional[OperStatus] = None
    traffic_disable: Optional[bool] = None


class GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGTABLE(
    BaseModel
):
    LAG_TABLE_LIST: Optional[
        List[
            GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGTABLELAGTABLELIST
        ]
    ] = None


class GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGMEMBERTABLE(
    BaseModel
):
    LAG_MEMBER_TABLE_LIST: Optional[
        List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBERPORTCHANNELMEMBERLIST
        ]
    ] = None


class GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannel(BaseModel):
    PORTCHANNEL: SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNEL
    PORTCHANNEL_MEMBER: SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBER
    LAG_TABLE: GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGTABLE
    LAG_MEMBER_TABLE: GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGMEMBERTABLE


class SonicPortchannelSonicPortchannel(BaseModel):
    sonic_portchannel_sonic_portchannel: SonicPortchannelSonicPortchannelSonicportchannelsonicportchannel \
        = Field(SonicPortchannelSonicPortchannelSonicportchannelsonicportchannel(), alias='sonic-portchannel:sonic-portchannel')


class PostSonicPortchannelSonicPortchannel(SonicPortchannelSonicPortchannel):
    pass


class PutSonicPortchannelSonicPortchannel(SonicPortchannelSonicPortchannel):
    pass


class PatchSonicPortchannelSonicPortchannel(SonicPortchannelSonicPortchannel):
    pass


class GetSonicPortchannelSonicPortchannel(BaseModel):
    sonic_portchannel_sonic_portchannel: Optional[
        GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannel
    ] = Field(None, alias='sonic-portchannel:sonic-portchannel')


class SonicPortchannelSonicPortchannelPortchannel(BaseModel):
    sonic_portchannel_PORTCHANNEL: Optional[
        SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNEL
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL')


class PutSonicPortchannelSonicPortchannelPortchannel(
    SonicPortchannelSonicPortchannelPortchannel
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannel(
    SonicPortchannelSonicPortchannelPortchannel
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannel(BaseModel):
    sonic_portchannel_PORTCHANNEL: Optional[
        SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNEL
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL')


class SonicPortchannelSonicPortchannelPortchannelPortchannelList(BaseModel):
    sonic_portchannel_PORTCHANNEL_LIST: Optional[
        List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELPORTCHANNELLIST
        ]
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL_LIST')


class PutSonicPortchannelSonicPortchannelPortchannelPortchannelList(
    SonicPortchannelSonicPortchannelPortchannelPortchannelList
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelPortchannelList(
    SonicPortchannelSonicPortchannelPortchannelPortchannelList
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelPortchannelList(BaseModel):
    sonic_portchannel_PORTCHANNEL_LIST: Optional[
        List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELPORTCHANNELLIST
        ]
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL_LIST')


class PostListSonicPortchannelSonicPortchannelPortchannelPortchannelList(
    SonicPortchannelSonicPortchannelPortchannelPortchannelList
):
    pass


class PutListSonicPortchannelSonicPortchannelPortchannelPortchannelList(
    SonicPortchannelSonicPortchannelPortchannelPortchannelList
):
    pass


class PatchListSonicPortchannelSonicPortchannelPortchannelPortchannelList(
    SonicPortchannelSonicPortchannelPortchannelPortchannelList
):
    pass


class PostSonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus(
    SonicPortchannelSonicPortchannelPortchannelPortchannelListAdminStatus,
    SonicPortchannelSonicPortchannelPortchannelPortchannelListMtu,
    SonicPortchannelSonicPortchannelPortchannelPortchannelListStatic,
    SonicPortchannelSonicPortchannelPortchannelPortchannelListLacpKey,
    SonicPortchannelSonicPortchannelPortchannelPortchannelListMinLinks,
    SonicPortchannelSonicPortchannelPortchannelPortchannelListFallback,
):
    pass


class SonicPortchannelSonicPortchannelPortchannelMember(BaseModel):
    sonic_portchannel_PORTCHANNEL_MEMBER: Optional[
        SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBER
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL_MEMBER')


class PutSonicPortchannelSonicPortchannelPortchannelMember(
    SonicPortchannelSonicPortchannelPortchannelMember
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelMember(
    SonicPortchannelSonicPortchannelPortchannelMember
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelMember(BaseModel):
    sonic_portchannel_PORTCHANNEL_MEMBER: Optional[
        SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBER
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL_MEMBER')


class SonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList(BaseModel):
    sonic_portchannel_PORTCHANNEL_MEMBER_LIST: Optional[
        List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBERPORTCHANNELMEMBERLIST
        ]
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL_MEMBER_LIST')


class PutSonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList(
    SonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList
):
    pass


class PatchSonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList(
    SonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList
):
    pass


class GetSonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList(
    BaseModel
):
    sonic_portchannel_PORTCHANNEL_MEMBER_LIST: Optional[
        List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBERPORTCHANNELMEMBERLIST
        ]
    ] = Field(None, alias='sonic-portchannel:PORTCHANNEL_MEMBER_LIST')


class PostListSonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList(
    SonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList
):
    pass


class PutListSonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList(
    SonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList
):
    pass


class PatchListSonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList(
    SonicPortchannelSonicPortchannelPortchannelMemberPortchannelMemberList
):
    pass


class GetSonicPortchannelSonicPortchannelLagTable(BaseModel):
    sonic_portchannel_LAG_TABLE: Optional[
        GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGTABLE
    ] = Field(None, alias='sonic-portchannel:LAG_TABLE')


class GetSonicPortchannelSonicPortchannelLagTableLagTableList(BaseModel):
    sonic_portchannel_LAG_TABLE_LIST: Optional[
        List[
            GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGTABLELAGTABLELIST
        ]
    ] = Field(None, alias='sonic-portchannel:LAG_TABLE_LIST')


class GetSonicPortchannelSonicPortchannelLagMemberTable(BaseModel):
    sonic_portchannel_LAG_MEMBER_TABLE: Optional[
        GetSonicPortchannelSonicPortchannelSonicportchannelsonicportchannelLAGMEMBERTABLE
    ] = Field(None, alias='sonic-portchannel:LAG_MEMBER_TABLE')


class GetSonicPortchannelSonicPortchannelLagMemberTableLagMemberTableList(BaseModel):
    sonic_portchannel_LAG_MEMBER_TABLE_LIST: Optional[
        List[
            SonicPortchannelSonicPortchannelSonicportchannelsonicportchannelPORTCHANNELMEMBERPORTCHANNELMEMBERLIST
        ]
    ] = Field(None, alias='sonic-portchannel:LAG_MEMBER_TABLE_LIST')


class PostSonicPortchannelSonicPortchannelPortchannel(
    SonicPortchannelSonicPortchannelPortchannel,
    SonicPortchannelSonicPortchannelPortchannelMember,
):
    pass