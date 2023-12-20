import requests
from requests.auth import HTTPBasicAuth
import json
import urllib3
import netmiko
from netmiko import ConnectHandler
import libcurl

urllib3.disable_warnings()

ipaddress = '192.168.18.4'
username = 'admin'
password = 'Pap3rin0!'
s = requests.Session()
# sample GET requests:
url = 'http://' + ipaddress + '/rest'
responce = s.get(url, auth=HTTPBasicAuth(username, password))


router_mikrotik = {
    'device_type': 'mikrotik_routeros',
    'host':   '192.168.18.4',
    'username': 'admin',
    'password': 'Pap3rin0!',
    'port': 22          # optional, defaults to 22

}

net_connect = ConnectHandler(**router_mikrotik)

output = net_connect.send_command('/export', cmd_verify=True)
print(output)


# response = requests.get(url + '/interface', auth=HTTPBasicAuth(username, password))
# for interface in response.json():
#     print(interface["name"])

'''
url - End-point URL, URL from where information is needed e.g. 
    https://router/rest/interface: This will get all the interface of the router
    https://router/rest/ip/address: This will get all the IP addresses of the router
username - Username of the router 
password - Password of the router 
Verify=False - To be used in case the SSL on the router is self-generated and not "known" CA 
'''

# sample PUT requests:
# info = json.dumps({"name": "bridge1", "vlan-filtering": "no"})
# response = requests.put(url + '/interface/bridge', auth=HTTPBasicAuth(username, password), data=info)


# info = json.dumps({"bridge": "bridge1", "interface": "sfp-sfpplus13"})
# response = requests.put(url + '/interface/bridge/port', auth=HTTPBasicAuth(username, password), data=info)

# info = json.dumps({"pvid": "300"})
# responce= requests.patch(url + '/interface/bridge/port/*1', auth=HTTPBasicAuth(username, password), data=info)
'''

requests.put(url, auth=HTTPBasicAuth(username,password), verify=False, data=DATA)
url - End-point URL, URL where information you need to input e.g. 
    https://router/rest/interface/vlan: Add a VLAN interface
    https://router/rest/ip/address: Add IP Address
username - Username of the router 
password - Password of the router 
Verify=False - To be used in case the SSL on the router is self-generated and not "known" CA 
DATA - Data to be added to the router. This data needs to be in JSON format, so need to convert python object to JSON object e.g.:
    data=json.dumps({"name" : "VLAN100", "vlan-id" : "100", "interface" : "ether1"})
   (Here we are sending data to the router to add VLAN ID 100 with name VLAN100 on interface ether1)
    data=json.dumps({"address" : "192.168.1.1/24" , "interface" : "VLAN100"})
   (Here we are sending data to the router to add IP address 192.168.1.1/24 on interface VLAN100
   Note: you need to use the correct endpoint
'''

# sample PATCH requests:
'''
requests.patch(url, auth=HTTPBasicAuth(username,password), verify=False, data=DATA)
url - End-point URL, URL where information you need to patch, this will include the object ID also. Object ID can be retrieved from GET requests e.g. 
    https://router/rest/interface/vlan/*10: Patch a VLAN interface with object ID '*10'
    https://router/rest/ip/address/*D: Patch IP address with object ID '*D'
username - Username of the router 
password - Password of the router 
Verify=False - To be used in case the SSL on the router is self-generated and not "known" CA 
DATA - Data to be updated on the router. This data needs to be in JSON format, so need to convert python object to JSON object e.g.:
    data=json.dumps({"name" : "Customer-100"})
   (Here we are sending data to the router to update the name of the VLAN to Customer-100)
    data=json.dumps({"address" : "192.168.1.1/30"})
   (Here we are sending data to the router to update IP address 192.168.1.1/30 on interface 
   Note: you need to use the correct endpoint
'''

# sample DELETE requests:
'''
requests.delete(url, auth=HTTPBasicAuth(username,password), verify=False)
url - End-point URL, URL where object you need to delete, this will include the object ID also. Object ID can be retrieved from GET requests e.g. 
    https://router/rest/interface/vlan/*10: Deletes the VLAN interface with object ID '*10'
    https://router/rest/ip/address/*D: Deletes IP address with object ID '*D'
username - Username of the router 
password - Password of the router 
Verify=False - To be used in case the SSL on the router is self-generated and not "known" CA 
   Note: When deleting the request will not send any JSON data back for confirmation like in other requests, to check if the request is successful the request's HTTP status-code should come back as 204 
'''
