from switch import Switch
from netdevice import Device

switch2 = Switch.from_db("hp5920")
# for port in switch2.phy_ports:
# switch2.retrieve_neighbors()

switch2._sbi_driver.send_cmd("",  {})

print(switch2.get_neighbors())
# switch2.to_db()

# switch.add_vlan(13)
# switch.retrieve_info()
#print(switch.get_neighbors())
#print(switch.get_vlan_interfaces(vrf_name='proj2'))
