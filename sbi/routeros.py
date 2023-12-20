import json
import time
import requests
from requests.auth import HTTPBasicAuth
from netdevice import Device
from utils import create_logger
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from netdevice import Device
from utils import create_logger
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, \
    SwitchConfigurationException
from typing import List, Literal


logger = create_logger('routeros')


class RosRestSbi:
    device: Device
    _rest_session: requests.Session = None

    def __init__(self, device: Device):
        self.device = device
        self.create_session()

    def create_session(self):

        logger.debug("Creating REST session")
        self._rest_session = requests.Session()
        self.authenticate()

    # fai un test
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def authenticate(self):
        try:
            responce = self._rest_session.get(
                'http://{}'.format(self.device.address),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('code {}, {}'.format(responce.status_code, responce.content))

    # GET
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def get(self, command) -> json:
        try:
            responce = self._rest_session.get(
                'http://{}/rest{}'.format(self.device.address, command),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(responce.status_code, responce.text))
        if responce.status_code != 200:
            raise SwitchNotAuthenticatedException()
        res = json.dumps(responce.text)
        return res

    # POST
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def post(self, command) -> json:
        #data = json.dumps(msg)
        try:
            responce = self._rest_session.post(
                'http://{}/rest/{}'.format(self.device.address, command),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(responce.status_code, responce.text))
        if responce.status_code != 200:
            raise SwitchNotAuthenticatedException()
        res = json.dumps(responce.text)
        return res

    # DELETE
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def delete(self, url, ids):
        try:
            responce = self._rest_session.delete(
                'http://{}/rest{}/{}'.format(self.device.address, url, ids),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(responce.status_code, responce.text))
        if responce.status_code != 200:
            raise SwitchNotAuthenticatedException()

