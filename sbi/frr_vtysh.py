import json
from pydantic import BaseModel, Field
from typing import List, Optional, Callable, Any
import paramiko
from .frr_models import BGPStatusData, FRRRoutingTable
from models import Vrf, RoutingProtocols, BGPRoutingProtocol, BGPNeighbor, BGPAddressFamily, SwitchDataModel


class BGPRouters(BaseModel):
    as_number: int = Field(..., alias='as')
    vrf: str = 'default'
    neighbors: List[BGPNeighbor] = []
    address_families: List[BGPAddressFamily] = []


def frr_configterm_and_save(func: Callable[..., List[Any]]) -> Callable[..., List[Any]]:
    def wrapper(*args, **kwargs) -> List[Any]:
        commands = func(*args, **kwargs)
        if not isinstance(commands, list):
            raise TypeError("The decorated function must return a list.")
        commands.insert(0, "configure terminal")
        commands.append('do write memory')
        result = "vtysh"
        for cmd in commands:
            result += " -c \"{}\"".format(cmd)
        return [result]
    return wrapper


class FrrConfig(BaseModel):
    frr_version: Optional[str]
    frr_defaults: Optional[str]
    hostname: Optional[str]
    service: Optional[str]
    routers: List[BGPRouters]

    @classmethod
    def from_raw_config(cls, config: str):
        lines = config.splitlines()
        config_dict = {'routers': []}
        static_routes = []

        current_router = None
        current_af = None
        current_vrf = None

        for line in lines:
            line = line.strip()
            parts = line.split() if line else []
            # Skip empty lines or lines with just a "!"
            if not line or line.startswith("!"):
                continue
            elif current_router:
                if line.startswith("neighbor") and not current_af:
                    neighbor_ip = parts[1]
                    # find if neighbor exists
                    neighbor = next((item for item in current_router['neighbors'] if item['ip'] == neighbor_ip), None)
                    if not neighbor:
                        neighbor = {'ip': neighbor_ip}
                        current_router['neighbors'].append(neighbor)
                    if parts[2] == 'remote-as':
                        neighbor.update({'remote_as': parts[3]})
                    elif parts[2] == 'description':
                        neighbor.update({'description': parts[3] if len(parts) == 3 else " ".join(parts[3:])})
                    elif parts[2] == 'update-source':
                        neighbor.update({'ip_source': parts[3]})
                elif current_af:
                    if line.startswith("redistribute"):
                        protocol = parts[1]
                        current_af['redistribute'].append(protocol)
                    elif line.startswith("import vrf"):
                        current_af['imports'].append(parts[2])
                    elif line == "exit-address-family":
                        current_af = None
                elif line.startswith("address-family"):
                    current_af = {'protocol': parts[1], 'type': parts[2], 'neighbors': [], 'imports': [],
                                  'redistribute': []}
                    current_router['address_families'].append(current_af)
                elif line.startswith('exit'):
                    current_router = None

            elif line.startswith("frr version"):
                config_dict['frr_version'] = line.split()[2]
            elif line.startswith("frr defaults"):
                config_dict['frr_defaults'] = line.split()[2]
            elif line.startswith("hostname"):
                config_dict['hostname'] = line.split()[1]
            elif line.startswith("agentx"):
                config_dict['agentx'] = True
            elif line.startswith("service"):
                config_dict['service'] = line.split()[1]
            elif line.startswith("router bgp"):
                parts = line.split()
                bgp_as = parts[2]
                vrf = parts[4] if len(parts) > 4 else 'default'

                current_router = next(
                    (item for item in config_dict['routers'] if item['as'] == bgp_as and item['vrf'] == vrf), None)
                if not current_router:
                    current_router = {'as': bgp_as, 'vrf': vrf, 'neighbors': [], 'address_families': []}
                    config_dict['routers'].append(current_router)
            elif line.startswith("vrf"):
                parts = line.split()
                current_vrf = parts[1]
            elif line.startswith("ip route"):
                parts = line.split()
                static_routes.append(
                    {
                        'prefix': parts[2],
                        'nexthop': parts[3] if len(parts) > 3 else None,
                        'vrf': 'default' if not current_vrf else current_vrf
                    }
                )
            elif line.startswith('exit-vrf'):
                current_vrf = None

        print(static_routes)  # FIXME! to be integrate in the parsed config
        return FrrConfig.model_validate(config_dict)

    @frr_configterm_and_save
    def add_static_route_cmd(self, route, vrfname: str = 'default', as_number: int = 1000) -> List[str]:
        pass

    @frr_configterm_and_save
    def del_static_route_cmd(self, route, vrfname: str = 'default', as_number: int = 1000) -> List[str]:
        pass

    @frr_configterm_and_save
    def add_bgp_instance_cmd(self, vrfname: str, as_number: int = 1000, afs: List[BGPAddressFamily] = []) -> List[str]:
        cmd = []
        vrf_part = "" if vrfname == "default" else "vrf {}".format(vrfname)
        cmd.append("router bgp {} {}".format(as_number, vrf_part))
        for af in afs:
            cmd.append("address family {} {}".format(af.protocol, af.protocol_type))
            for import_item in af.imports:
                cmd.append("import vrf {}".format(import_item))
            for redistribute_item in af.redistribute:
                cmd.append("redistribute {}".format(redistribute_item))
            cmd.append('exit-address-family')
        return cmd

    @frr_configterm_and_save
    def del_bgp_instance_cmd(self, vrfname: str, as_number: int = 1000) -> List[str]:
        vrf_part = "" if vrfname == "default" else "vrf {}".format(vrfname)
        return ["no router bgp {} {}".format(as_number, vrf_part)]

    @frr_configterm_and_save
    def add_bgp_instance_routing_advertise_cmd(self) -> List[str]:
        cmd = []
        return cmd

    @frr_configterm_and_save
    def del_bgp_instance_routing_advertise_cmd(self) -> List[str]:
        cmd = []
        return cmd

    @frr_configterm_and_save
    def add_bgp_peer_cmd(self, neigh: BGPNeighbor, vrfname: str = 'default', as_number: int = 1000) -> List[str]:
        cmd = []
        vrf_part = "" if vrfname == "default" else "vrf {}".format(vrfname)
        cmd.append("router bgp {} {}".format(as_number, vrf_part))
        cmd.append("neighbor {} remote-as {}".format(neigh.ip, neigh.remote_as))
        if neigh.description:
            cmd.append("neighbor {} description {}".format(neigh.ip, neigh.description))
        if neigh.ip_source:
            cmd.append("neighbor {} update-source {}".format(neigh.ip, neigh.ip_source))
        return cmd

    @frr_configterm_and_save
    def del_bgp_peer_cmd(self, neigh: BGPNeighbor, vrfname: str = 'default', as_number: int = 1000) -> List[str]:
        cmd = []
        vrf_part = "" if vrfname == "default" else "vrf {}".format(vrfname)
        cmd.append("router bgp {} {}".format(as_number, vrf_part))
        cmd.append("no neighbor {} remote-as {}".format(neigh.ip, neigh.remote_as))
        return cmd

    @frr_configterm_and_save
    def add_vrf_binding(self, vrf_name1: str, vrf_name2: str, as_number=1000, protocol='ipv4', protocol_type='unicast'):
        if vrf_name1 == vrf_name2:
            raise ValueError("the two Vrfs have the same name {}!".format(vrf_name2))
        # the import of Vrfs should be bidirectional otherwise routing will be asymmetrical
        cmd = []
        vrf_part_1 = "" if vrf_name1 == "default" or not vrf_name1 else "vrf {}".format(vrf_name1)
        vrf_part_2 = "" if vrf_name2 == "default" or not vrf_name2 else "vrf {}".format(vrf_name2)
        cmd.append("router bgp {} {}".format(as_number, vrf_part_1))
        cmd.append("address-family {} {}".format(protocol, protocol_type))
        cmd.append("import {}".format(vrf_part_2))
        cmd.append("exit")
        cmd.append("router bgp {} {}".format(as_number, vrf_part_2))
        cmd.append("address-family {} {}".format(protocol, protocol_type))
        cmd.append("import {}".format(vrf_part_1))
        cmd.append("exit")
        return cmd

    def to_switch_vrf_protocols(self) -> dict[str, RoutingProtocols]:
        res = {}  # res will have vrf names as keys and models.vrf.protocols as content
        for frr_vrf in self.routers:
            res[frr_vrf.vrf] = RoutingProtocols()
            res[frr_vrf.vrf].bgp = BGPRoutingProtocol(
                as_number=frr_vrf.as_number,
                neighbors=frr_vrf.neighbors,
                address_families=frr_vrf.address_families)
        return res

    @classmethod
    def from_switch_model(cls, switchobj: SwitchDataModel):
        routers = []
        for vrf in switchobj.vrfs:
            routers.append(BGPRouters(
                as_number=vrf.protocols.bgp.as_number,
                vrf=vrf.name,
                neighbors=vrf.protocols.bgp.neighbors,
                address_families=vrf.protocols.bgp.address_families
            ))
        return FrrConfig(routers=routers)
