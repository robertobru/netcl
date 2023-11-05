from typing import List, Union, Any
import netmiko
from tenacity import retry, stop_after_attempt
from utils import create_logger
from netdevice import Device
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, \
    SwitchConfigurationException

logger = create_logger('netmiko_driver')


class NetmikoSbi:
    _netmiko_session = None
    device: Device

    def __init__(self, device: Device):
        self.device = device
        self.create_session()

    @retry(stop=stop_after_attempt(3))
    def create_session(self):
        try:
            self._netmiko_session = netmiko.ConnectHandler(
                device_type=self.device.model,
                username=self.device.user,
                password=self.device.passwd.get_secret_value(),
                ip=str(self.device.address),

            )
        except netmiko.exceptions.NetmikoTimeoutException:
            logger.error('NetmikoTimeoutException in authentication')
            raise SwitchNotConnectedException()
        except netmiko.exceptions.AuthenticationException:
            logger.error('SwitchNotAuthenticatedException in authentication')
            raise SwitchNotAuthenticatedException()
        except netmiko.exceptions.ReadTimeout:
            logger.error('ReadTimeout in authentication')
            raise SwitchNotConnectedException()

    @retry(stop=stop_after_attempt(3))
    def send_command(self, commands: List[str], enable=True) -> List:
        logger.debug("send command: {}".format(commands))
        try:
            if enable:
                self._netmiko_session.enable()
            output = []
            for command in commands:
                output.append(self._netmiko_session.send_command(command, read_timeout=45))
            return output
        except netmiko.exceptions.NetmikoTimeoutException:
            raise SwitchNotConnectedException()
        except netmiko.exceptions.ReadTimeout:
            raise SwitchNotConnectedException()
        except netmiko.exceptions.AuthenticationException:
            raise SwitchNotAuthenticatedException()

    @retry(stop=stop_after_attempt(3))
    def get_info(self, command: str, use_textfsm: bool = True, enable=False) -> Union[dict[str, Any], str, list]:
        logger.debug("getting info command: {}".format(command))
        try:
            if enable:
                self._netmiko_session.enable()
            return self._netmiko_session.send_command(command, use_textfsm=use_textfsm, read_timeout=45)
        except netmiko.exceptions.NetmikoTimeoutException:
            logger.error('NetmikoTimeoutException in get_info with command: {}'.format(command))
            raise SwitchNotConnectedException()
        except netmiko.exceptions.AuthenticationException:
            logger.error('AuthenticationException in get_info with command: {}'.format(command))
            raise SwitchNotAuthenticatedException()
        except netmiko.exceptions.ReadTimeout:
            logger.error('ReadTimeout in get_info with command: {}'.format(command))
            raise SwitchNotConnectedException()
