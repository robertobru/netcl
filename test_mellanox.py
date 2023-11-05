"""import requests
import xml.etree.ElementTree as ET
import xmltodict


s = requests.Session()
#res = s.get('https://r1-mellanox1.maas/xtree', verify=False)
#print(res.text)
data = {'f_user_id': 'xmladmin', 'f_password': 'xmladmin'}
res = s.get('https://r1-mellanox1.maas/admin/launch?script=rh&template=login&action=login', data=data, verify=False)
print(res.cookies)
print('-------------------------')
print(res.text)
data = '''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<xg-request>
<action-request>
<action-name>/do_rest</action-name>
<nodes>
<node>
<name>get</name>
<type>string</type>
<value>/mlnxos/api_version</value>
</node>
</nodes>
</action-request>
</xg-request>
'''
#print('????????????????????', ET.tostring(data, encoding='utf8'), '%%%%%%%%%%%%%%%%%')
parsed_data = xmltodict.parse(data)
reparsed_data = xmltodict.unparse(parsed_data)
print('????????????????????', parsed_data, '%%%%%%%%%%%%%%%%%')

headers = {'Content-Type': 'text/xml'}
res = s.post('https://r1-mellanox1.maas/xtree', data=reparsed_data, verify=False, headers=headers)
print(xmltodict.parse(res.text))"""

from switch import Switch
from netdevice import Device

device_data = Device.model_validate(
    {
        "name": "test",
        "model": "mellanox",
        "user": "admin",
        "passwd": "admin",
        "address": "r2mellanox-1.maas"
    }
)
switch = Switch.create(device_data)
switch.del_vlan([2,3])

# switch.retrieve_info()
