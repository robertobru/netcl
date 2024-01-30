from typing import List, Union, Any
import paramiko
import json
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from utils import create_logger
from netdevice import Device
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, \
    SwitchConfigurationException

logger = create_logger('netmiko_driver')


class ParamikoSbi:
    _ssh_session = None
    device: Device

    def __init__(self, device: Device):
        self.device = device
        self.create_session()

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def create_session(self):
        self._ssh_session = paramiko.client.SSHClient()
        self._ssh_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self._ssh_session.connect(str(self.device.address), username=self.device.user,
                                      password=self.device.passwd.get_secret_value())
            logger.debug('connected')
        except paramiko.ssh_exception.NoValidConnectionsError:
            logger.error('NetmikoTimeoutException in authentication')
            raise SwitchNotConnectedException()
        except paramiko.ssh_exception.AuthenticationException:
            logger.error('SwitchNotAuthenticatedException in authentication')
            raise SwitchNotAuthenticatedException()
        except paramiko.ssh_exception.SSHException:
            logger.error('ReadTimeout in authentication')
            raise SwitchNotConnectedException()

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def send_command(self, commands: List[str], json_parse: bool =False) -> List:
        logger.debug("send command: {}".format(commands))
        try:
            output = []
            for command in commands:
                logger.debug("sending command {}".format(command))
                _stdin, _stdout, _stderr = self._ssh_session.exec_command(command)
                r_stdout = _stdout.read().decode()
                r_stderr = _stderr.read().decode()
                logger.debug("received  _stdin {}, _stdout {}, _stderr {}".format(
                    _stdin, r_stdout, r_stderr))
                output.append({
                    '_stdin': _stdin,
                    '_stdout': r_stdout if not json_parse else json.loads(r_stdout),
                    '_stderr': r_stderr}
                )

            return output
        except paramiko.ssh_exception.NoValidConnectionsError:
            logger.error("TimeoutException")
            raise SwitchNotConnectedException()
        except paramiko.ssh_exception.SSHException:
            logger.error("AuthenticationException")
            raise SwitchNotAuthenticatedException()

