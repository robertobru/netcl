from switch import Switch
from threading import Thread
from netdevice import Device

#switch2 = Switch.from_db("hp5920")
# for port in switch2.phy_ports:
# switch2.retrieve_neighbors()

#print(switch2.get_neighbors())
# switch2.to_db()

switchOD, thread = Switch.from_db("milli")

thread.join()




# switch.add_vlan(13)
# switch.retrieve_info()
#print(switch.get_neighbors())
#print(switch.get_vlan_interfaces(vrf_name='proj2'))
