from typing import List, Union, Any
import netmiko
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from utils import create_logger
from netdevice import Device
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, \
    SwitchConfigurationException

logger = create_logger('netmiko_driver')

# Fixme: add exceptions on cmd errors, we should raise "SwitchConfigurationException"
# but I to get it from netmiko?


class NetmikoSbi:
    _netmiko_session = None
    device: Device

    def __init__(self, device: Device):
        self.device = device
        self.create_session()

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def create_session(self):
        try:
            self._netmiko_session = netmiko.ConnectHandler(
                device_type=self.device.model,
                username=self.device.user,
                password=self.device.passwd.get_secret_value(),
                ip=str(self.device.address),
                auth_timeout=90,
                timeout=210,
                keepalive=30
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

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def send_command(self, commands: List[str], enable=True) -> List:
        logger.debug("send command: {}".format(commands))
        try:
            if enable:
                self._netmiko_session.enable()
            output = []
            for command in commands:
                logger.debug("sending command {}".format(command))
                res = self._netmiko_session.send_command(command, read_timeout=45)
                logger.debug("received output {}".format(res))
                output.append(res)
            logger.debug(output)
            return output
        except netmiko.exceptions.NetmikoTimeoutException:
            logger.error("TimeoutException")
            raise SwitchNotConnectedException()
        except netmiko.exceptions.ReadTimeout:
            logger.error("ReadTimeout")
            raise SwitchNotConnectedException()
        except netmiko.exceptions.AuthenticationException:
            logger.error("AuthenticationException")
            raise SwitchNotAuthenticatedException()

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
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
