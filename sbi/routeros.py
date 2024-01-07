import requests
from requests.auth import HTTPBasicAuth
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from netdevice import Device
from utils import create_logger
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException


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
            res = self._rest_session.get(
                'http://{}'.format(self.device.address),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('code {}, {}'.format(res.status_code, res.content))

    # GET
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def get(self, command) -> dict:
        try:
            res = self._rest_session.get(
                'http://{}/rest{}'.format(self.device.address, command),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                headers={'Content-Type': 'application/json'},
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code != 200:
            raise SwitchNotAuthenticatedException()
        # res = json.dumps(res.text)
        return res.json()

    # PUT
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def put(self, command, data) -> dict:
        try:
            res = self._rest_session.put(
                'http://{}/rest/{}'.format(self.device.address, command),
                json=data,
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                headers={'Content-Type': 'application/json'},
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code != 200:
            raise SwitchNotAuthenticatedException()
        return res.json()

    # PATCH
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def patch(self, command, data) -> dict:
        try:
            res = self._rest_session.patch(
                'http://{}/rest/{}'.format(self.device.address, command),
                json=data,
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                headers={'Content-Type': 'application/json'},
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code != 200:
            raise SwitchNotAuthenticatedException()
        return res.json()

    # POST
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def post(self, command, data) -> dict:
        try:
            res = self._rest_session.post(
                'http://{}/rest/{}'.format(self.device.address, command),
                json=data,
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                headers={'Content-Type': 'application/json'},
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code != 200:
            raise SwitchNotAuthenticatedException()
        return res.json()

    # DELETE
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def delete(self, url, ids):
        try:
            res = self._rest_session.delete(
                'http://{}/rest{}/{}'.format(self.device.address, url, ids),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd.get_secret_value()),
                headers={'Content-Type': 'application/json'},
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code != 200:
            raise SwitchNotAuthenticatedException()
