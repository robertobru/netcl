from pydantic import BaseModel
from typing import List, Optional, Any, Dict, Literal, Union
import requests
from pydantic import ValidationError, RootModel, Field, IPvAnyAddress, model_validator, IPvAnyInterface
from models import PhyPort, VlanL3Port, ConfigItem, Vrf, SwitchStates


# Modelli per le Regole (invariati)
class Rule(BaseModel):
    id: Optional[int]
    description: Optional[str]
    source: str
    destination: str
    action: str
    protocol: str

class RuleCreate(BaseModel):
    description: Optional[str]
    source: str
    destination: str
    action: str
    protocol: str

class RuleUpdate(BaseModel):
    id: int
    description: Optional[str]
    source: str
    destination: str
    action: str
    protocol: str

# Modelli per le Interfacce
class Interface(BaseModel):
    id: Optional[int]
    name: str
    description: Optional[str]
    type: str
    enabled: bool


class InterfaceCreate(BaseModel):
    name: str
    description: Optional[str]
    type: str
    enabled: bool


class InterfaceUpdate(BaseModel):
    id: int
    name: str
    description: Optional[str]
    type: str
    enabled: bool


# Modelli per le VLAN
class VLAN(BaseModel):
    id: Optional[int]
    name: str
    description: Optional[str]
    vlan_tag: int
    parent_interface: str


class VLANCreate(BaseModel):
    name: str
    description: Optional[str]
    vlan_tag: int
    parent_interface: str


class VLANUpdate(BaseModel):
    id: int
    name: str
    description: Optional[str]
    vlan_tag: int
    parent_interface: str


# Modelli per i Bridge
class Bridge(BaseModel):
    id: Optional[int]
    name: str
    description: Optional[str]
    members: List[str]


class BridgeCreate(BaseModel):
    name: str
    description: Optional[str]
    members: List[str]


class BridgeUpdate(BaseModel):
    id: int
    name: str
    description: Optional[str]
    members: List[str]


# Modelli per l'Availability (disponibilità)
class Availability(BaseModel):
    id: Optional[int]
    name: str
    description: Optional[str]
    interfaces: List[str]


class AvailabilityCreate(BaseModel):
    name: str
    description: Optional[str]
    interfaces: List[str]


class AvailabilityUpdate(BaseModel):
    id: int
    name: str
    description: Optional[str]
    interfaces: List[str]


# Modelli per i Gruppi di Interfacce
class InterfaceGroup(BaseModel):
    id: Optional[int]
    name: str
    description: Optional[str]
    members: List[str]


class InterfaceGroupCreate(BaseModel):
    name: str
    description: Optional[str]
    members: List[str]


class InterfaceGroupUpdate(BaseModel):
    id: int
    name: str
    description: Optional[str]
    members: List[str]


# Modello per la risposta API
class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None


class AuthToken(BaseModel):
    client_id: str
    api_key: str









# Funzioni per le Regole (invariato)
def get_rules(api_url: str, api_key: str) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to fetch data: {response.status_code}")
        response.raise_for_status()


def create_rule(api_url: str, api_key: str, rule_data: RuleCreate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(api_url, headers=headers, json=rule_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to create data: {response.status_code}")
        response.raise_for_status()


def update_rule(api_url: str, api_key: str, rule_data: RuleUpdate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.put(api_url, headers=headers, json=rule_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to update data: {response.status_code}")
        response.raise_for_status()


def delete_rule(api_url: str, api_key: str, rule_id: int) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    params = {'id': rule_id}
    response = requests.delete(api_url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to delete data: {response.status_code}")
        response.raise_for_status()


class PfSense(FwDevice):



    def get_interfaces(self) -> None:
        pf_sense_l3_ports = rest_get(
            "http://firewall.maas/api/v1/interface",
            AuthToken(client_id="61646d696e", api_key="c8c1e700c805058666f84ada2b1f04dc"),
            parsing_class=PfSense_InterfaceMap
        )
        print(pf_sense_l3_ports)
        pf_sense_phy_ports = rest_get(
            "http://firewall.maas/api/v1/interface/available",
            AuthToken(client_id="61646d696e", api_key="c8c1e700c805058666f84ada2b1f04dc"),
            parsing_class=PfSense_AvailableInterfaceMap
        )
        print(pf_sense_phy_ports)
        self.phy_ports = pf_sense_phy_ports.to_phy_port_list()

        for port_name in pf_sense_l3_ports.root.keys():
            vlan = 1
            if pf_sense_l3_ports.root[port_name].intf:
                current_phy_port = pf_sense_phy_ports.root[pf_sense_l3_ports.root[port_name].intf]
                if current_phy_port.isvlan:

                    vlan = current_phy_port.tag
                    fw_parent_port = next(item for item in self.phy_ports
                                          if item.index == current_phy_port.vlanif.split('.')[0])
                    fw_parent_port.trunk_vlans.append(vlan)
            _ipaddr = None
            _cidr = None
            if pf_sense_l3_ports.root[port_name].ipaddr:
                _ipaddr = pf_sense_l3_ports.root[port_name].ipaddr
                _cidr = IPvAnyInterface("{}/{}".format(
                    pf_sense_l3_ports.root[port_name].ipaddr, pf_sense_l3_ports.root[port_name].subnet))
            self.l3_ports.append(FWL3Port(
                index=port_name,
                name=pf_sense_l3_ports.root[port_name].descr,
                vlan=vlan,
                ipaddress=_ipaddr,
                cidr=_cidr,
                vrf="default",
                interface_assignment=pf_sense_l3_ports.root[port_name].intf.split('.')[0]
            ))


        for port in self.phy_ports:
            if len(port.trunk_vlans) > 1:
                port.mode = 'TRUNK'
            print(port)




def create_interface(api_url: str, api_key: str, interface_data: InterfaceCreate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(api_url, headers=headers, json=interface_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to create data: {response.status_code}")
        response.raise_for_status()


def update_interface(api_url: str, api_key: str, interface_data: InterfaceUpdate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.put(api_url, headers=headers, json=interface_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to update data: {response.status_code}")
        response.raise_for_status()


def delete_interface(api_url: str, api_key: str, interface_id: int) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    params = {'id': interface_id}
    response = requests.delete(api_url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to delete data: {response.status_code}")
        response.raise_for_status()


# Funzioni per le VLAN
def get_vlans(api_url: str, api_key: str) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to fetch data: {response.status_code}")
        response.raise_for_status()


def create_vlan(api_url: str, api_key: str, vlan_data: VLANCreate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(api_url, headers=headers, json=vlan_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to create data: {response.status_code}")
        response.raise_for_status()


def update_vlan(api_url: str, api_key: str, vlan_data: VLANUpdate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.put(api_url, headers=headers, json=vlan_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to update data: {response.status_code}")
        response.raise_for_status()


def delete_vlan(api_url: str, api_key: str, vlan_id: int) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    params = {'id': vlan_id}
    response = requests.delete(api_url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to delete data: {response.status_code}")
        response.raise_for_status()


# Funzioni per i Bridge
def get_bridges(api_url: str, api_key: str) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to fetch data: {response.status_code}")
        response.raise_for_status()


def create_bridge(api_url: str, api_key: str, bridge_data: BridgeCreate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(api_url, headers=headers, json=bridge_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to create data: {response.status_code}")
        response.raise_for_status()


def update_bridge(api_url: str, api_key: str, bridge_data: BridgeUpdate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.put(api_url, headers=headers, json=bridge_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to update data: {response.status_code}")
        response.raise_for_status()


def delete_bridge(api_url: str, api_key: str, bridge_id: int) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    params = {'id': bridge_id}
    response = requests.delete(api_url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to delete data: {response.status_code}")
        response.raise_for_status()


# Funzioni per l'Availability (disponibilità)
def get_availability(api_url: str, api_key: str) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to fetch data: {response.status_code}")
        response.raise_for_status()


def create_availability(api_url: str, api_key: str, availability_data: AvailabilityCreate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(api_url, headers=headers, json=availability_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to create data: {response.status_code}")
        response.raise_for_status()


def update_availability(api_url: str, api_key: str, availability_data: AvailabilityUpdate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.put(api_url, headers=headers, json=availability_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to update data: {response.status_code}")
        response.raise_for_status()


def delete_availability(api_url: str, api_key: str, availability_id: int) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    params = {'id': availability_id}
    response = requests.delete(api_url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to delete data: {response.status_code}")
        response.raise_for_status()


# Funzioni per i Gruppi di Interfacce
def get_interface_groups(api_url: str, api_key: str) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to fetch data: {response.status_code}")
        response.raise_for_status()


def create_interface_group(api_url: str, api_key: str, group_data: InterfaceGroupCreate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(api_url, headers=headers, json=group_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to create data: {response.status_code}")
        response.raise_for_status()


def update_interface_group(api_url: str, api_key: str, group_data: InterfaceGroupUpdate) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.put(api_url, headers=headers, json=group_data.dict())

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to update data: {response.status_code}")
        response.raise_for_status()


def delete_interface_group(api_url: str, api_key: str, group_id: int) -> APIResponse:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    params = {'id': group_id}
    response = requests.delete(api_url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            return APIResponse(**data)
        except ValidationError as e:
            print("Error parsing response:", e)
    else:
        print(f"Failed to delete data: {response.status_code}")
        response.raise_for_status()

