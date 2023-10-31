from typing import List, Union, Any
import netmiko
from netdevice import Device
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, \
    SwitchConfigurationException

"""
def check_session(f):
    def wrapper(*args):
        if not args[0]._netmiko_session or not args[0]._netmiko_session.is_alive():
            args[0].create_session()
        return f(*args)

    return wrapper
"""


class NetmikoSbi:
    _netmiko_session = None
    device: Device

    def __init__(self, device: Device):
        self.device = device
        self.create_session()

    def create_session(self):
        try:
            self._netmiko_session = netmiko.ConnectHandler(
                device_type=self.device.model,
                username=self.device.user,
                password=self.device.passwd.get_secret_value(),
                ip=str(self.device.address)
            )
        except netmiko.exceptions.NetmikoTimeoutException:
            raise SwitchNotConnectedException()
        except netmiko.exceptions.AuthenticationException:
            raise SwitchNotAuthenticatedException()
        except netmiko.exceptions.ReadTimeout:
            raise SwitchNotConnectedException()

    # @check_session
    def send_command(self, commands: List[str], enable=True) -> List:
        try:
            if enable:
                self._netmiko_session.enable()
            output = []
            for command in commands:
                output.append(self._netmiko_session.send_command(command))
            return output
        except netmiko.exceptions.NetmikoTimeoutException:
            raise SwitchNotConnectedException()
        except netmiko.exceptions.ReadTimeout:
            raise SwitchNotConnectedException()
        except netmiko.exceptions.AuthenticationException:
            raise SwitchNotAuthenticatedException()

    # @check_session
    def get_info(self, command: str, use_textfsm: bool = True, enable=False) -> Union[dict[str, Any], str, list]:
        try:
            if enable:
                self._netmiko_session.enable()
            return self._netmiko_session.send_command(command, use_textfsm=use_textfsm)
        except netmiko.exceptions.NetmikoTimeoutException:
            raise SwitchNotConnectedException()
        except netmiko.exceptions.AuthenticationException:
            raise SwitchNotAuthenticatedException()
        except netmiko.exceptions.ReadTimeout:
            raise SwitchNotConnectedException()
