from sbi.netmiko import NetmikoSbi
from .switch_base import Switch
from netdevice import Vrf, PhyPort, VlanL3Port, LldpNeighbor
import textfsm
from pydantic import IPvAnyInterface
from netaddr import IPAddress
from utils import create_logger
from typing import List, Literal

logger = create_logger('hp_comware')


class HpComware(Switch):
    _sbi_driver: NetmikoSbi = None

    def _reinit_sbi_drivers(self) -> None:
        if not self._sbi_driver:
            self._sbi_driver = NetmikoSbi(self.to_device_model())

    def retrieve_info(self) -> None:
        logger.info('retrieving information for switch {}'.format(self.name))
        self.reinit_sbi_drivers()
        self.retrieve_config()
        self.parse_config()
        self.retrieve_runtime_ports()
        self.retrieve_neighbors()
        logger.info('retrieved all the information for switch {}'.format(self.name))

    def _get_port_by_shortname(self, shortname: str) -> PhyPort:
        interface = None
        if shortname[:2] == 'GE':
            interface = next(
                (item for item in self.phy_ports if item.index == 'GigabitEthernet' + shortname[2:]), None)
        if shortname[:3] == 'XGE':
            interface = next(
                (item for item in self.phy_ports if item.index == 'Ten-GigabitEthernet' + shortname[3:]), None)
        if shortname[:3] == 'FGE':
            interface = next((item for item in self.phy_ports if item.index == 'FortyGigE' + shortname[3:]), None)
        if shortname[:4] == 'M-GE':
            interface = next(
                (item for item in self.phy_ports if item.index == 'M-GigabitEthernet' + shortname[4:]), None)
        if not interface:
            raise ValueError('interface {} not found'.format(shortname))
        return interface

    def retrieve_runtime_ports(self) -> None:
        logger.debug("retrieve_runtime_ports")
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

    def retrieve_config(self) -> None:
        _config = self._sbi_driver.get_info("display current-configuration")
        self.store_config(_config)

    def parse_config(self) -> None:
        fsm = textfsm.TextFSM(open("fsm_templates/hp_comware_config_template"))
        res = fsm.ParseText(self.last_config.config)
        for r in res:
            if r[0]:
                # interface
                if r[0][:4] == 'Vlan':
                    if r[5] and r[6]:
                        ipaddress = IPvAnyInterface("{}/{}".format(r[5], IPAddress(r[6]).netmask_bits()))
                    else:
                        ipaddress = None

                    self.vlan_l3_ports.append(VlanL3Port(
                        index=r[0],
                        vlan=int(r[0][14:]),
                        ipaddress=ipaddress,
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

        for vlan_interface in self.vlan_l3_ports:
            if vlan_interface.vrf:
                vrf_obj = next(item for item in self.vrfs if item.name == vlan_interface.vrf)
                vrf_obj.ports.append(vlan_interface)

    def retrieve_neighbors(self) -> None:
        _neighbors = self._sbi_driver.get_info("display lldp neighbor-information list", use_textfsm=True)
        logger.debug('neighbours: {}, Type {}'.format(_neighbors, type(_neighbors)))

        for n in _neighbors:
            interface = self._get_port_by_shortname(n['local_interface'])
            interface.neighbor = LldpNeighbor(neighbor=n['neighbor'], remote_interface=n['neighbor_interface'])

    def _add_vlan(self, vlan_ids: List[int]):
        """
        Add vlans to the hp-comware switch
        :param vlan_ids: list
        :return: list of the text commands as a separate list to create vlans, TODO add vlan name, and add description
        """
        vlan_create_cmd = list()
        if not len(vlan_ids):
            return "Empty vlan list"
        else:
            for vlan_id in vlan_ids:
                vlan_create_cmd.append([f'vlan {vlan_id}', f'name vlan {vlan_id}', f'description vlan {vlan_id}'])
        return vlan_create_cmd

    def _del_vlan(self, vlan_ids: List[int]):
        """
            Delete vlans from the hp-comware switch
            :param vlan_ids: list
            :return: list of the text commands as a separate list to delete vlans
            """
        vlan_delete_cmd = list()
        if not len(vlan_ids):
            return "Empty vlan list"
        else:
            for vlan_id in vlan_ids:
                vlan_delete_cmd.append([f'undo vlan {vlan_id}'])
        return vlan_delete_cmd

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

        # check the mode of PhyPort
        if port.mode == "ACCESS":
            port.trunk_vlans = [vlan_id]
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
                    commands_list.append([
                        f'interface {port.index}',
                        f'undo port access vlan'
                    ])

        elif port.mode in ["TRUNK", "HYBRID"]:
            for vlan_id in vlan_ids:
                commands_list.append([
                    f'interface {port.index}',
                    f'undo port {"trunk" if port.mode == "TRUNK" else "hybrid"} vlan {vlan_id}'
                ])
        else:
            raise ValueError("PhyPort has no interface mode specified!")

        return commands_list

    def _set_port_mode(self, port: PhyPort, port_mode: Literal['ACCESS', 'HYBRID', 'TRUNK']) -> bool:
        pass

    def _bind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    def _unbind_vrf(self, vrf1: Vrf, vrf2: Vrf) -> bool:
        pass

    def _add_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port) -> bool:
        pass

    def _del_vlan_to_vrf(self, vrf: Vrf, vlan_interface: VlanL3Port) -> bool:
        pass

    def commit_and_save(self):
        pass
