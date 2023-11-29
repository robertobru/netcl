from switch import Switch
from netdevice import Device


routerOS = Device(
    name='milli',
    model='microtik',
    user='admin',
    passwd='Pap3rin0!',
    address='192.168.18.4')

#switch2 = Switch.from_db("hp5920")
#switchOS = Switch.create(routerOS)
switch2 = Switch.from_db("milli")
# for port in switch2.phy_ports:
# switch2.retrieve_neighbors()

#print(switch2.get_neighbors())
# switch2.to_db()

# switch.add_vlan(13)
# switch.retrieve_info()
#print(switch.get_neighbors())
#print(switch.get_vlan_interfaces(vrf_name='proj2'))
