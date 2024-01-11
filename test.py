from pydantic import *
import json
import requests
from requests.auth import HTTPBasicAuth
import paramiko
import switch.switch_base
import switch.microtik
import models

"""client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.18.4', port=22, username='admin', password='Pap3rin0!')
stdin, stdout, stderr = client.exec_command('export')
for line in stdout:
    print(line.strip('\n'))
client.close()
msg = {"_proplist": ["address", "interface"]}
"""
"""
data = requests.get(
    url="http://192.168.18.4/rest/interface/ethernet",
    # headers={'Content-Type': 'text/json'},
    auth=HTTPBasicAuth('admin', 'Pap3rin0!'),
    #data=json.dumps(msg)
)
print(data.status_code, data.text)


data = requests.post(
    url="http://192.168.18.4/rest/interface/ethernet/monitor",
    headers={'Content-Type': 'application/json'},
    auth=HTTPBasicAuth('admin', 'Pap3rin0!'),
    data='{ "once": "1", "numbers": "*1,*2,*3,*4"}'
)
print(data.status_code, data.text)

data = requests.get(
    url="http://192.168.18.4/rest/interface/bridge/vlan?bridge=tnt",
    headers={'Content-Type': 'application/json'},
    auth=HTTPBasicAuth('admin', 'Pap3rin0!'),
    # data='{ "once": "1", "numbers": "*1,*2,*3,*4"}'
)
print(data.status_code, data.text)

data = requests.get(
    url="http://192.168.18.4/rest/interface/bridge/port?bridge=tnt",
    headers={'Content-Type': 'application/json'},
    auth=HTTPBasicAuth('admin', 'Pap3rin0!'),
    # data='{ "once": "1", "numbers": "*1,*2,*3,*4"}'
)
print(data.status_code, data.text)

ports = json.loads(data.text)
#port1 = next(item['.id'] for item in ports if item['interface'] == 'sfp-sfpplus1')
#print(port1)
data = requests.put(
    # url="http://192.168.18.4/rest/interface/bridge/port/{}".format(port1),
    url="http://192.168.18.4/rest/interface/bridge/port/*1D",
    headers={'Content-Type': 'application/json'},
    auth=HTTPBasicAuth('admin', 'Pap3rin0!'),
    data=json.dumps({"frame-types": "admit-only-vlan-tagged", "bridge": "tnt", "interface": "sfp-sfpplus1"})
)
print(data.status_code, data.text)

input_data = models.Device.model_validate(
    {
        'name': 'microtik',
        'model': 'microtik',
        'user': 'admin',
        'passwd': 'Pap3rin0!',
        'address': '192.168.18.4'
    }
)
switch = switch.switch_base.Switch.create(input_data)
"""

switch, thread = switch.switch_base.Switch.from_db('microtik')
thread.join()
switch.update_info()
"""switch.add_vlan([11, 12])
switch.update_info()
switch.del_vlan([14, 15])
switch.update_info()"""
# switch.add_vlan_to_port(11, "sfp-sfpplus1", 'TRUNK')
# switch.del_vlan_to_port([11], "sfp-sfpplus1")

# switch.add_vlan_to_vrf()
l3port = models.SwitchRequestVlanL3Port(vlan=11, ipaddress='10.11.0.1', cidr='10.11.0.0/16', vrf='mobile_testbed')
switch.del_vlan_to_vrf(switch.vrfs[0].name, l3port.vlan)
switch.add_vlan_to_vrf(switch.vrfs[0], l3port)
switch.update_info()
switch.to_db()

