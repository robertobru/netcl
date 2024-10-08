from pydantic import RootModel, BaseModel, Field
from typing import Optional, Dict, Any, List

#### BGP Status ###############################################

class Timers(BaseModel):
    configuredRestartTimer: Optional[int]
    receivedRestartTimer: Optional[int]


class GracefulRestartInfo(BaseModel):
    endOfRibSend: Dict[str, Any]
    endOfRibRecv: Dict[str, Any]
    localGrMode: Optional[str]
    remoteGrMode: Optional[str]
    rBit: Optional[bool]
    timers: Timers


class MessageStats(BaseModel):
    depthInq: Optional[int]
    depthOutq: Optional[int]
    opensSent: Optional[int]
    opensRecv: Optional[int]
    notificationsSent: Optional[int]
    notificationsRecv: Optional[int]
    updatesSent: Optional[int]
    updatesRecv: Optional[int]
    keepalivesSent: Optional[int]
    keepalivesRecv: Optional[int]
    routeRefreshSent: Optional[int]
    routeRefreshRecv: Optional[int]
    capabilitySent: Optional[int]
    capabilityRecv: Optional[int]
    totalSent: Optional[int]
    totalRecv: Optional[int]


class AddPath(BaseModel):
    ipv4Unicast: Optional[Dict[str, bool]]


class MultiprotocolExtensions(BaseModel):
    ipv4Unicast: Optional[Dict[str, bool]]


class HostName(BaseModel):
    advHostName: Optional[str]
    advDomainName: Optional[str]


class NeighborCapabilities(BaseModel):
    byteAs: Optional[str] = Field(None, alias="4byteAs")
    addPath: Optional[AddPath]
    routeRefresh: Optional[str]
    multiprotocolExtensions: Optional[MultiprotocolExtensions]
    hostName: Optional[HostName]
    gracefulRestartCapability: Optional[str]


class AddressFamilyInfo(BaseModel):
    ipv4Unicast: Optional[Dict[str, Any]]


class Neighbor(BaseModel):
    remoteAs: Optional[int]
    localAs: Optional[int]
    nbrInternalLink: Optional[bool]
    nbrDesc: Optional[str]
    bgpVersion: Optional[int]
    remoteRouterId: Optional[str]
    localRouterId: Optional[str]
    bgpState: Optional[str]
    bgpTimerLastRead: Optional[int]
    bgpTimerLastWrite: Optional[int]
    bgpInUpdateElapsedTimeMsecs: Optional[int]
    bgpTimerHoldTimeMsecs: Optional[int]
    bgpTimerKeepAliveIntervalMsecs: Optional[int]
    gracefulRestartInfo: Optional[GracefulRestartInfo]
    messageStats: Optional[MessageStats]
    minBtwnAdvertisementRunsTimerMsecs: Optional[int]
    updateSource: Optional[str]
    addressFamilyInfo: Optional[AddressFamilyInfo]
    connectionsEstablished: Optional[int] = None
    connectionsDropped: Optional[int] = None
    lastResetTimerMsecs: Optional[int] = None
    lastResetDueTo: Optional[str] = None
    lastResetCode: Optional[int] = None
    connectRetryTimer: Optional[int] = None
    nextConnectTimerDueInMsecs: Optional[int] = None
    readThread: Optional[str] = None
    writeThread: Optional[str] = None
    neighborCapabilities: Optional[NeighborCapabilities] = Field(None, alias="neighborCapabilities")
    bgpTimerUpMsec: Optional[int] = None
    bgpTimerUpString: Optional[str] = None
    bgpTimerUpEstablishedEpoch: Optional[int] = None
    hostLocal: Optional[str] = None
    portLocal: Optional[int] = None
    hostForeign: Optional[str] = None
    portForeign: Optional[int] = None
    nexthop: Optional[str] = None
    nexthopGlobal: Optional[str] = None
    nexthopLocal: Optional[str] = None
    bgpConnection: Optional[str] = None
    estimatedRttInMsecs: Optional[int] = None


class BGPStatusData(RootModel):
    root: Dict[str, Neighbor]

#### END BGP Status ###############################################

#### FRR Routing Table ############################################


class NextHop(BaseModel):
    flags: int
    fib: Optional[bool] = None
    ip: Optional[str] = None
    afi: Optional[str] = None
    active: Optional[bool] = None
    interfaceIndex: Optional[int] = None
    interfaceName: Optional[str] = None
    weight: Optional[int] = None


class Route(BaseModel):
    prefix: str
    protocol: str
    vrfId: int
    vrfName: str
    selected: Optional[bool] = False
    destSelected: Optional[bool] = False
    distance: int
    metric: int
    installed: Optional[bool] = False
    internalStatus: int
    internalFlags: int
    internalNextHopNum: int
    internalNextHopActiveNum: int
    uptime: str
    nexthops: List[NextHop]


class FRRRoutingTable(RootModel):
    root: Dict[str, List[Route]]