from pydantic import BaseModel, IPvAnyInterface, IPvAnyNetwork

# This files contains the REST models used for configuring the switches


class SwitchRequestVlanL3Port(BaseModel):
    vlan: int
    ipaddress: IPvAnyInterface
    cidr: IPvAnyNetwork
    vrf: str = ''
    description: str = ''
