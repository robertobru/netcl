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

    def retrieve_runtime_ports(self)  -> None:
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
                if r[2][-1] == 'G': # checking if speed is in Gigabit or Megabit
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
                            trunk_vlans = trunk_vlans + [int(index) for index in range(trunk_vlans[-1] +1, int(v))]
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
        pass

    def _del_vlan(self, vlan_ids: List[int]):
        pass

    def _add_vlan_to_port(self, vlan_id: int, port: PhyPort, pvid: bool = False) -> bool:
        pass

    def _del_vlan_to_port(self, vlan_ids: List[int], port: PhyPort) -> bool:
        pass

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
