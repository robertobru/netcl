# import socket
import json


''' Returns internal ip address of the server which uvicorn is running on, in the case if needed just uncomment it.'''
# def get_host_ip_and_port():
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     try:
#         s.connect(("192.168.18.2", 80))
#         ip_address = s.getsockname()[0]
#     except Exception as e:
#         print("Error:", e)
#         ip_address = None
#     finally:
#         s.close()
#     return ip_address


def server_implementation():
    '''
Returns the server implementation to other codes
ip_address is the internal ip address that uvicorn is running.
floating_ip_address is the external ip address of the server, in the case that there is no firewall or NAT both
ip_address and floating_ip_address are the same.
port_number is the port which uvicorn is running on.
    '''
    with open('config.json') as f:
        config = json.load(f)

    uvicorn_config = config.get("uvicorn", {})
    ip_address = uvicorn_config.get("host")
    floating_ip_address = uvicorn_config.get("floating_ip")
    port_number = uvicorn_config.get("port")
    return ip_address, floating_ip_address, port_number


addresses = server_implementation()
server_ip_address = addresses[0]
server_floating_address = addresses[1]
server_port_number = addresses[2]

