import random

from sbi.netmiko import NetmikoSbi
from .switch_base import Switch
from models import SwitchRequestVlanL3Port, LldpNeighbor, PhyPort, VlanL3Port, Vrf, VrfRequest, \
    IpV4Route, RoutingProtocols, BGPRoutingProtocol, BGPNeighbor, BGPAddressFamily, BGPRedistribute
import textfsm
import ipaddress
from pydantic import IPvAnyInterface, IPvAnyAddress
from netaddr import IPAddress, IPNetwork
from utils import create_logger
from typing import List, Literal, Any, Callable, Tuple

logger = create_logger('hp_comware')


class HpComware(Switch):
    _sbi_driver: NetmikoSbi = None

    def send_cmd_and_save(func: Callable[..., List[Any]]) -> Callable[..., List[Any]]:
        def wrapper(self, *args, **kwargs) -> List[Any]:
            cmds = func(self, *args, **kwargs)
            if not isinstance(cmds, list):
                raise TypeError("The decorated function must return a list of str.")
            if 'save' not in cmds[-1]:
                cmds.append('save force')
            res = self._sbi_driver.send_config(commands=cmds)
            return res

        return wrapper

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_driver:
            self._sbi_driver = NetmikoSbi(self.to_device_model())

    def _retrieve_info(self) -> None:
        logger.info('retrieving information for switch {}'.format(self.name))
        self.reinit_sbi_drivers()
        self._update_info()

    def _update_info(self):
        self.retrieve_config()
        self.parse_config()
        self.retrieve_runtime_ports()
        self.retrieve_bgp_peer_status()
        self.retrieve_neighbors()
        logger.info('retrieved all the information for switch {}'.format(self.name))

    def _check_config_changed(self, cfg) -> bool:
        return cfg != self.last_config.config

    def _get_port_by_shortname(self, shortname: str) -> PhyPort:
        interface = None
        if shortname[:2] == 'GE':
            interface = next(
                (item for item in self.phy_ports if item.index == 'GigabitEthernet{}'.format(shortname[2:])), None)
        elif shortname[:3] == 'XGE':
            interface = next(
                (item for item in self.phy_ports if item.index == 'Ten-GigabitEthernet{}'.format(shortname[3:])), None)
        elif shortname[:3] == 'FGE':
            interface = next(
                (item for item in self.phy_ports if item.index == 'FortyGigE{}'.format(shortname[3:])), None)
        elif shortname[:4] == 'M-GE':
            interface = next(
                (item for item in self.phy_ports if item.index == 'M-GigabitEthernet' + shortname[4:]), None)
        if not interface:
            raise ValueError('interface {} not found'.format(shortname))
        return interface

    def retrieve_runtime_ports(self) -> None:
        ports = self._sbi_driver.get_info("display interface brief", use_textfsm=False)
        fsm = textfsm.TextFSM(open("fsm_templates/hp_comware_interface_template"))
        res = fsm.ParseText(ports)
        for r in res:
            interface = self._get_port_by_shortname(r[0])
            interface.status = r[1] if r[1] != 'ADM' else 'DOWN'
            interface.admin_status = 'ENABLED' if r[1] != 'ADM' else 'DISABLED'
            if interface.status == 'DOWN':
                interface.speed = 0
            else:
                if '(a)' in r[2]:  # remove autoneg symbol
                    r[2] = r[2][:-3]
                multiplier = 1
                if r[2][-1] == 'G':  # checking if speed is in Gigabit or Megabit
                    multiplier = 1000
                interface.speed = int(r[2][:-1]) * multiplier
            if r[3][0] == 'F':
                interface.duplex = 'FULL'
            elif r[3][0] == 'H':
                interface.duplex = 'HALF'

    def retrieve_bgp_peer_status(self):

        for vrf in self.vrfs:
            if vrf.protocols and vrf.protocols.bgp:
                res = self._sbi_driver.get_info(
                    "display bgp peer ipv4 vpn-instance {}".format(vrf.name), use_textfsm=False)
                fsm = textfsm.TextFSM(open("fsm_templates/hp_comware_bgp_peer_template"))
                parsed_res = fsm.ParseText(res)
                for peer in parsed_res:
                    if peer[1] and peer[2]:
                        if not vrf.protocols.bgp.router_id:
                            vrf.protocols.bgp.router_id = peer[0]
                        configured_peer = next(
                            item for item in vrf.protocols.bgp.neighbors if
                                str(item.ip) == str(peer[1]) and int(item.remote_as) == int(peer[2])
                        )
                        configured_peer.msgrcvd = int(peer[3])
                        configured_peer.msgsent = int(peer[4])
                        configured_peer.outq = int(peer[5])
                        configured_peer.prefrcv = int(peer[6])
                        configured_peer.updowntime = peer[7]
                        configured_peer.status = peer[8].lower()

    def retrieve_config(self) -> None:
        _config = self._sbi_driver.get_info("display current-configuration")
        self.store_config(_config)

    def parse_bgp_config(self) -> None:
        config_to_parse = self.last_config.config
        local_as = None
        in_bgp_section = False
        parsing_vrf = None
        switch_vrf = None
        parsing_address_family = None
        default_vrf = next((item for item in self.vrfs if item.name == 'default'), None)
        default_address_family = None

        for line in config_to_parse.splitlines():
            if line.startswith('bgp') and not in_bgp_section:
                in_bgp_section = True
                local_as = line.split()[1]
                if not default_vrf.protocols:
                    default_vrf.protocols = RoutingProtocols()
                if not default_vrf.protocols.bgp:
                    default_vrf.protocols.bgp = BGPRoutingProtocol(as_number=local_as)
            elif line.startswith(' peer'):  # peer of default Vrf
                peer = line.split()
                default_vrf.protocols.bgp.neighbors.append(
                    BGPNeighbor(ip=IPvAnyAddress(peer[1]), remote_as=int(peer[3])))
            elif line.startswith(' address-family'):  # address family of default Vrf
                af_line = line.split()
                default_address_family = BGPAddressFamily(protocol=af_line[1], type=af_line[2], redistribute=[],
                                                          imports=[])
                default_vrf.protocols.bgp.address_families.append(default_address_family)
            elif line.startswith('  import-route'):  # import route of default vrf
                parsed_route_type = line.split()[1]
                redistributed = BGPRedistribute.connected if parsed_route_type == 'direct' else parsed_route_type
                default_address_family.redistribute.append(redistributed)
            elif line.startswith(' ip vpn-instance'):  # enter into vpn-instance
                parsing_vrf = line.split()[2]
                switch_vrf = next(item for item in self.vrfs if item.name == parsing_vrf)
                if not switch_vrf.protocols:
                    switch_vrf.protocols = RoutingProtocols()
                if not switch_vrf.protocols.bgp:
                    switch_vrf.protocols.bgp = BGPRoutingProtocol(as_number=local_as)

            elif parsing_vrf and len(line) > 1 and line[1] != ' ':  # exit from vpn-instance
                if parsing_address_family:
                    parsing_address_family = None
                parsing_vrf = None

            elif parsing_vrf and line.startswith('  peer'):  # identify peers in vpn-instance
                peer = line.split()
                switch_vrf.protocols.bgp.neighbors.append(BGPNeighbor(ip=IPvAnyAddress(peer[1]), remote_as=int(peer[3])))

            elif line.startswith('  address-family'):  # identify address families in vpn-instance
                protocol = line.split()[1]
                protocol_type = line.split()[2]
                parsing_address_family = BGPAddressFamily(protocol=protocol, type=protocol_type, redistribute=[], imports=[])
                switch_vrf.protocols.bgp.address_families.append(parsing_address_family)
            elif parsing_address_family and len(line) > 2 and line[2] != ' ':
                parsing_address_family = None
            elif parsing_address_family and line.startswith('   import-route'):
                parsed_route_type = line.split()[1]
                redistributed = BGPRedistribute.connected if parsed_route_type == 'direct' else parsed_route_type
                parsing_address_family.redistribute.append(redistributed)

    def parse_config(self) -> None:
        fsm = textfsm.TextFSM(open("fsm_templates/hp_comware_config_template"))
        res = fsm.ParseText(self.last_config.config)
        for r in res:
            if r[0]:
                # interface
                if r[0][:4] == 'Vlan':
                    if r[5] and r[6]:
                        ipaddress = IPvAnyAddress("{}".format(r[5]))
                        cidr = IPvAnyInterface(IPNetwork("{}/{}".format(r[5], r[6])).cidr)
                    else:
                        ipaddress = None
                        cidr = None
                    self.vlan_l3_ports.append(VlanL3Port(
                        index=r[0],
                        vlan=int(r[0][14:]),
                        ipaddress=ipaddress,
                        cidr=cidr,
                        vrf=r[4],
                        description=r[7]
                    ))
                else:
                    trunk_vlans = []
                    found_to = False
                    for v in r[3].split():
                        if not found_to and v != 'to':
                            trunk_vlans.append(int(v))
                        elif found_to and v != 'to':
                            trunk_vlans = trunk_vlans + [int(index) for index in range(trunk_vlans[-1] + 1, int(v))]
                            found_to = False
                        elif v == 'to':
                            found_to = True
                        else:
                            raise ValueError('error in parsing trunk vlans')

                    vlan_mode = r[1] if r[1] else 'ACCESS'
                    logger.debug('adding phy port {}'.format(r[0]))
                    self.phy_ports.append(PhyPort(
                        index=r[0],
                        name=r[0],
                        trunk_vlans=trunk_vlans,
                        access_vlan=r[2] if r[2] else 1,
                        speed=0,
                        neighbor=None,
                        mode=vlan_mode.upper(),
                        status='NA',
                        admin_status='NA',
                        duplex='NA'
                    ))
            elif r[13]:  # a Vlan item is parsed
                if 'to' in r[13]:
                    self.vlans = self.vlans + [v for v in range(int(r[13].split()[0]), int(r[13].split()[-1]))]
                else:
                    self.vlans.append(int(r[13]))
            elif r[8]:  # a VRF item is found
                """
                Value Vrf (\S+)
                Value VrfRD (\S+)
                Value VrfDescription (.*)
                Value List VrfExport (.*)
                Value List VrfImport (.*)
                """

                export_tmp_str = ""
                for item in r[11]:
                    export_tmp_str += ' ' + item

                rd_export = [c for c in export_tmp_str.split()]

                import_tmp_str = ""
                for item in r[12]:
                    import_tmp_str += ' ' + item

                rd_import = [c for c in import_tmp_str.split()]

                self.vrfs.append(
                    Vrf(
                        name=r[8],
                        rd=r[9],
                        description=r[10],
                        rd_export=rd_export,
                        rd_import=rd_import,
                        ports=[]
                    )
                )

        # adding the default vrf
        default_vrf = Vrf(
            name="default",
            rd="default",
            ports=[]
        )
        self.vrfs.append(default_vrf)
        for vlan_interface in self.vlan_l3_ports:
            if vlan_interface.vrf:
                vrf_obj = next((item for item in self.vrfs if item.name == vlan_interface.vrf), None)
                if vrf_obj:
                    vrf_obj.ports.append(vlan_interface)
                else:  # it means it is bound to the default Vrf
                    default_vrf.ports.append(vlan_interface)

        self.parse_bgp_config()

    def retrieve_neighbors(self) -> None:
        _neighbors = self._sbi_driver.get_info("display lldp neighbor-information list", use_textfsm=True)

        for n in _neighbors:
            interface = self._get_port_by_shortname(n['local_interface'])
            interface.neighbor = LldpNeighbor(neighbor=n['neighbor'], remote_interface=n['neighbor_interface'])
            logger.debug('interface {} neighbours: {}, remote port {}'.format(interface.index, n['neighbor'],
                                                                              n['neighbor_interface']))
    """def retrieve_bgp_neighbors(self):
        for vrf in self.vrfs:
            parsing_peers = self._sbi_driver.get_info(
                "display bgp peer ipv4 vpn-instance {}".format(vrf.name), use_textfsm=True)
            for p in parsing_peers:
                logger.warn(p)
                switch_peer = next(item for item in vrf.protocols.bgp.neighbors
                                   if item.ip == p[1] and item.remote_as == p[2])
                switch_peer.msgrcvd = p[3]
                switch_peer.msgsent = p[4]"""

    @send_cmd_and_save
    def _add_vlan(self, vlan_ids: List[int]):
        """
        Add vlans to the hp-comware switch
        :param vlan_ids: list
        :return: list of the text commands as a separate list to create vlans, TODO add vlan name, and add description
        """
        vlan_create_cmd = list()
        if not vlan_ids:
            raise (ValueError("Empty vlan list"))

        invalid_vlans_lst = list(filter(lambda vlan: not (1 <= vlan <= 4094), vlan_ids))
        if invalid_vlans_lst:
            raise ValueError("VLAN ID must be an integer between 1 and 4094 inclusive.")

        for vlan_id in vlan_ids:
            vlan_create_cmd.extend([f'vlan {vlan_id}', f'name vlan {vlan_id}', f'description vlan {vlan_id}'])

        return vlan_create_cmd

    @send_cmd_and_save
    def _del_vlan_itf(self, vlan_id: int):
        """
        Delete vlans interface from the hp-comware switch
        :param vlan_id: int
        :return: list of the text commands as a separate list to delete vlan interface
        """

        intf = next((item for item in self.vlan_l3_ports if item.vlan == vlan_id), None)
        if intf is None:
            raise ValueError('no vlan interface for vlan id {}'.format(vlan_id))

        vlan_delete_cmd = ["undo interface Vlan-interface {}".format(vlan_id)]
        return vlan_delete_cmd

    @send_cmd_and_save
    def _del_vlan(self, vlan_ids: List[int]):
        """
        Delete vlans from the hp-comware switch
        :param vlan_ids: list
        :return: list of the text commands as a separate list to delete vlans
        """
        vlan_delete_cmd = list()
        if not vlan_ids:
            return "Empty vlan list"

        invalid_vlans_lst = list(filter(lambda vlan: not (1 <= vlan <= 4094), vlan_ids))
        if invalid_vlans_lst:
            raise ValueError("VLAN ID must be an integer between 1 and 4094 inclusive.")
        else:
            for vlan_id in vlan_ids:
                vlan_delete_cmd.extend([f'undo vlan {vlan_id}'])
        return vlan_delete_cmd

    @send_cmd_and_save
    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False) -> bool:
        """
        Configure VLAN settings for a given interface type.
        :param vlan_id: int - VLAN ID to configure
        :param port: PhyPort - Physical port object
        :param pvid: bool - (Optional) PVID parameter
        :return: list[str] - List of commands applied
        """
        # validate VLAN-ID's different conditions
        if not port.index:
            raise ValueError("Port index cannot be empty!")

        if not (1 <= vlan_id <= 4094):
            raise ValueError("VLAN ID must be an integer between 1 and 4094 inclusive.")

        set_port_type_and_vlan = []
        # check the mode of PhyPort
        if port.mode == "ACCESS":
            port.trunk_vlans = []
            set_port_type_and_vlan = [
                f'interface {port.index}',
                'port link-type access',
                f'port access vlan {vlan_id}'
            ]
        elif port.mode in ["TRUNK", "HYBRID"]:
            port.trunk_vlans.append(vlan_id)
            if port.mode == "TRUNK":
                set_port_type_and_vlan = [
                    f'interface {port.index}',
                    'port link-type trunk',
                    f'port trunk permit vlan {vlan_id}'
                ]
            elif port.mode == "HYBRID":
                set_port_type_and_vlan = [
                    f'interface {port.index}',
                    'port link-type hybrid',
                    f'port hybrid vlan {vlan_id}'
                ]
        else:
            raise ValueError("PhyPort has no interface mode specified!")

        # Create the requested vlan
        set_vlan_port = [
            f'vlan {vlan_id}',
            f'name set for VLAN {vlan_id}',
            f'description set for VLAN {vlan_id}',
        ]
        commands_list = set_vlan_port + set_port_type_and_vlan
        return commands_list

    @send_cmd_and_save
    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort):
        """
        Delete vlans from the port ACCESS TRUNK HYBRID
        :param vlan_id: list - VLAN IDs to configure
        :param port: PhyPort - Physical port object
        :return: list[str] - List of commands applied
        """
        vlan_delete_cmd = list()

        if not vlan_ids:
            raise ValueError("Empty VLAN list")
        if not port.index:
            raise ValueError("Port index cannot be empty!")

        invalid_vlans_lst = list(filter(lambda vlan: not (1 <= vlan <= 4094), vlan_ids))
        if invalid_vlans_lst:
            raise ValueError("VLAN ID must be an integer between 1 and 4094 inclusive.")

        # check the mode of PhyPort
        commands_list = []
        if port.mode == "ACCESS":
            # port.trunk_vlans = vlan_ids
            if len(vlan_ids) > 1:
                raise ValueError("in ACCESS port there is only one vlan id!")
            else:
                for _ in vlan_ids:
                    commands_list.extend([
                        f'interface {port.index}',
                        f'undo port access vlan'
                    ])

        elif port.mode in ["TRUNK", "HYBRID"]:
            for vlan_id in vlan_ids:
                commands_list.extend([
                    f'interface {port.index}',
                    f'undo port {"trunk" if port.mode == "TRUNK" else "hybrid"} vlan {vlan_id}'
                ])
        else:
            raise ValueError("PhyPort has no interface mode specified!")

        return commands_list

    @send_cmd_and_save
    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']):
        """
        Set the interface mode (ACCESS, TRUNK, or HYBRID) for the given PhyPort object.

        :param port: PhyPort - Physical port object to configure.
        :param port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK'] - Mode to set for the port.
        :return: list[str] - List of configuration commands applied.
        :raises ValueError: If port index is empty or if an invalid interface mode is specified.
        """

        if not port.index:
            raise ValueError("Port index cannot be empty!")
        # check the mode of PhyPort has been changed
        commands_list = []
        if port_mode == "ACCESS":
            port.mode = "ACCESS"
            port.trunk_vlans = []  # Clear trunk_vlans for ACCESS mode
            commands_list = [
                f'interface {port.index}',
                'port link-type access',
            ]
        elif port_mode in ["TRUNK", "HYBRID"]:
            port.mode = port_mode
            commands_list = [
                f'interface {port.index}',
                f'port link-type {"trunk" if port.mode == "TRUNK" else "hybrid"}'
            ]
        else:
            raise ValueError("PhyPort has no interface mode specified!")
        # send commands to the switch
        return commands_list

    @send_cmd_and_save
    def _bind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        """
        Binds two Virtual Routing and Forwarding (VRF) instances by configuring VPN targets
        for export and import of extcommunity attributes.

        :param vrf1: VRF instance 1
        :param vrf2: VRF instance 2
        :return: Boolean indicating success or failure of the binding operation
        """

        # configure vpn-target for vrf1 export-extcommunity
        if vrf1.rd not in vrf1.rd_export:
            vrf1.rd_export.append(vrf1.rd)

        vrf1_conf_cmds = [f'ip vpn-instance {vrf1.name}']
        [vrf1_conf_cmds.append(f"vpn-target {rd_exp} export-extcommunity ") for rd_exp in vrf1.rd_export]

        # configure vpn-target for vrf1 import-extcommunity
        [vrf1.rd_import.append(vrf2_rd) for vrf2_rd in vrf2.rd_export if vrf2_rd not in vrf1.rd_import]
        [vrf1_conf_cmds.append(f"vpn-target {rd_import} import-extcommunity") for rd_import in vrf1.rd_import]
        vrf1_conf_cmds.append(f"quit")
        # configure vpn-target for vrf2 export-extcommunity
        if vrf2.rd not in vrf2.rd_export:
            vrf2.rd_export.append(vrf2.rd)
        vrf2_conf_cmds = [f'ip vpn-instance {vrf2.name}']
        [vrf2_conf_cmds.append(f"vpn-target {rd_exp} export-extcommunity ") for rd_exp in vrf2.rd_export]

        # configure vpn-target for vrf2 import-extcommunity
        [vrf2.rd_import.append(vrf1_rd) for vrf1_rd in vrf1.rd_export if vrf1_rd not in vrf2.rd_import]
        [vrf2_conf_cmds.append(f"vpn-target {rd_import} import-extcommunity") for rd_import in vrf2.rd_import]
        vrf2_conf_cmds.append(f"quit")

        commands_list = vrf1_conf_cmds + vrf2_conf_cmds
        return commands_list

    @send_cmd_and_save
    def _unbind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        """
        Unbinds two VRFs instances by configuring VPN targets for import of extcommunity attributes.

        :param vrf1: VRF instance 1
        :param vrf2: VRF instance 2
        :return: None
        """
        # configure vpn-target for vrf1 import-extcommunity
        if vrf1.rd == vrf2.rd:
            raise ValueError("Two VRFs have the same RD !!!")
        vrf1_conf_cmds = []
        if vrf2.rd in vrf1.rd_import:
            vrf1_conf_cmds.append(f'ip vpn-instance {vrf1.name}')
            vrf1_conf_cmds.append(f"undo vpn-target {vrf2.rd} import-extcommunity")
            vrf1.rd_import.remove(vrf2.rd)

        # configure vpn-target for vrf2 export-extcommunity
        vrf2_conf_cmds = []
        if vrf1.rd in vrf2.rd_import:
            vrf2_conf_cmds.append(f'ip vpn-instance {vrf2.name}')
            vrf2_conf_cmds.append(f"undo vpn-target {vrf1.rd} import-extcommunity ")
            vrf2.rd_import.remove(vrf1.rd)

        commands_list = vrf1_conf_cmds + vrf2_conf_cmds
        # Check for empty command list
        if not commands_list:
            print("No commands to execute. VRFs are already unbound.")
            return True
        return commands_list

    @send_cmd_and_save
    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: SwitchRequestVlanL3Port) -> bool:
        """
        Creates a VLAN interface and associates it with a specified VRF (VPN instance).

        :param vrf: Vrf - The VRF (VPN instance) to associate the VLAN interface with.
        :param vlan_interface: VlanL3Port - Details of the VLAN interface to be added.
        :return: list[str] - List of commands to configure the VLAN and VRF association.
        :raises ValueError: If VRF name is empty or if VLAN interface IP or subnet mask is not set.
        """

        netmask = str(ipaddress.IPv4Network(str(vlan_interface.cidr)).netmask)
        # check conditions
        if not vrf.name:
            raise ValueError("VRF name cannot be empty!")
        if not vlan_interface.ipaddress or not netmask:
            raise ValueError("The VLAN interface IP or subnet mask is not set!")

        # Ckeck and create vlan if not existed
        create_vlan_cmd = [
            f'vlan {vlan_interface.vlan}',
            # f'name vlan connected to vlaninterface {VlanL3Port.ipaddress}',
            # f'description vlan connected to vrf {Vrf.name}',
            f'quit'
        ]
        # Bind vlan-interface to the vrf
        add_vlan_interface_to_vpn_instance_cmd = [
            f'interface Vlan-interface{vlan_interface.vlan}',
            f'ip binding vpn-instance {vrf.name}',
            f'ip address {str(ipaddress.IPv4Interface(str(vlan_interface.ipaddress)).ip)} {netmask}',
            f'quit'
        ]
        # add vrf name to vlan_interface
        vlan_interface.vrf = vrf.name
        command_list = create_vlan_cmd + add_vlan_interface_to_vpn_instance_cmd
        return command_list

    @send_cmd_and_save
    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port) -> bool:
        """
        Deletes a VLAN interface and removes it from a specified VRF (VPN instance).

        :param vrf: Vrf - The VRF (VPN instance) to delete the VLAN-interface from.
        :param vlan_interface: VlanL3Port - Details of the VLAN interface to be added.
        :return: list[str] - List of commands to configure the VLAN-interfaces.
        :raises ValueError: If VRF name is empty. The Vlan is checked by the Pydantic.
        """

        # check conditions
        if not vrf.name:
            raise ValueError("VRF name cannot be empty!")

        # Bind vlan-interface to the vrf
        command_list = [
            # f'interface Vlan-interface {vlan_interface.vlan}',
            # f'undo ip binding vpn-instance {vrf.name}',
            f'undo interface Vlan-interface {vlan_interface.vlan}'
        ]
        # remove vrf name from vlan_interface
        vlan_interface.vrf = ""
        return command_list

    @send_cmd_and_save
    def _add_vrf(self, vrf: VrfRequest) -> Tuple[List[str], NetmikoSbi]:
        if not vrf.rd:
            vrf.rd = self.get_new_rd()

        as_number = vrf.protocols.bgp.as_number if vrf.protocols.bgp else 1000
        command_list = [
            "ip vpn-instance {}".format(vrf.name),
                "description {}".format(vrf.description),
                "route-distinguisher {}".format(vrf.rd),
            "quit",
            "bgp {}".format(as_number),
                "ip vpn-instance {}".format(vrf.name),
                    "ipv4-family unicast",
                        "import-route direct",
                        "import-route static",
                    "quit",
                "quit",
            "quit"
        ]
        return command_list, self._sbi_driver

    def get_new_rd(self):
        allocated_rds = [item.rd for item in self.vrfs]
        rd = random.randint()
        while rd in allocated_rds:
            rd = random.randint()
        return "{}:00".format(rd)

    @send_cmd_and_save
    def _del_vrf(self, vrf: Vrf) -> Tuple[List[str], NetmikoSbi]:
        command_list = [
            "undo ip vpn-instance {}".format(vrf.name)
        ]
        return command_list, self._sbi_driver

    @send_cmd_and_save
    def _add_static_route(self, route: IpV4Route, vrf_name: str ='default') -> Tuple[List[str], NetmikoSbi]:
        vpn_instance = "" if vrf_name == 'default' else "vpn-instance {} ".format(vrf_name)
        prefix, mask = route.get_prefix_and_prefixlen()
        command_list = [
            "ip route-static {}{} {} {} permanent".format(vpn_instance, prefix, mask, route.nexthop)
        ]
        return command_list, self._sbi_driver

    @send_cmd_and_save
    def _del_static_route(self, route: IpV4Route, vrf_name: str ='default') -> Tuple[List[str], NetmikoSbi]:
        vpn_instance = "" if vrf_name == 'default' else "vpn-instance {} ".format(vrf_name)
        prefix, mask = route.get_prefix_and_prefixlen()
        command_list = [
            "undo ip route-static {}{} {}".format(vpn_instance, prefix, mask)
        ]
        return command_list, self._sbi_driver

    @send_cmd_and_save
    def _add_bgp_instance(self, vrf_msg: VrfRequest):
        as_number = vrf_msg.protocols.bgp.as_number if vrf_msg.protocols.bgp else 1000
        command_list = [
            "bgp {}".format(as_number)
        ]
        if vrf_msg.name != "default":
            command_list.append("ip vpn-instance {}".format(vrf_msg.name))
            for peer in vrf_msg.protocols.bgp.neighbors:
                if peer not in self.get_bgp_peers():
                    command_list.append("peer {} as-number {}".format(peer.ip, peer.remote_as))
                    if peer.ip_source:
                        l3_interface = next(item for item in self.vlan_l3_ports if item.ipaddress == peer.ip_source)
                        command_list.append("peer {} connect-interface {}".format(peer.ip, l3_interface.name))
            for family in vrf_msg.protocols.bgp.address_families:
                if family.protocol == 'ipv4':
                    if vrf_msg.protocols.bgp.address_families == 'ipv4':
                        command_list.append("ipv4-family {}".format(family.protocol_type))
                        if 'connected' in family.redistribute:
                            command_list.append("import-route direct")
                        if 'static' in family.redistribute:
                            command_list.append("import-route static")
                    command_list("quit")  # exit from current family
            for peer in vrf_msg.protocols.bgp.neighbors:
                command_list.append("peer {} enable".format(peer.ip))
        if vrf_msg.name != "default":
            command_list.append("quit")  # exit from ip vpn-instance VRF_NAME
        command_list.append("quit")  # exit from bgp AS_NUMBER
        return command_list

    @send_cmd_and_save
    def _del_bgp_instance(self, vrf_name: str):
        command_list = []
        vrf = next(item for item in self.vrfs if item.name == vrf_name)
        if vrf.name == "default":
            command_list.append("undo bgp {}".format(vrf.protocols.bgp.as_number))
        else:
            command_list.append("bgp {}".format(vrf.protocols.bgp.as_number))
            command_list.append("undo ip vpn-instance {}".format(vrf.name))
            command_list.append("quit")
        for peer in self.get_bgp_peers():
            if peer not in self.get_bgp_peers(exclude=vrf.name):
                command_list.append("undo peer {} as-number {}".format(peer.ip, peer.remote_as))
        return command_list

    def commit_and_save(self):
        """
        Save the configuration to the switch
        :return:
        """
        command_list = ["save force"]
        res = self._sbi_driver.send_command(commands=command_list, enable=True)
        return res

