from switch import Switch
from netdevice import Device

device_data = Device.model_validate(
    {
        "name": "test",
        "model": "hp_comware",
        "user": "admin",
        "passwd": "pap3rin0",
        "address": "hp5920-1.maas"
    }
)
switch = Switch.create(device_data)

# switch.add_vlan(13)
# switch.retrieve_info()
#print(switch.get_neighbors())
#print(switch.get_vlan_interfaces(vrf_name='proj2'))
