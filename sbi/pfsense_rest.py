import requests
# from requests.auth import HTTPBasicAuth
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from netdevice import Device
from utils import create_logger
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, SwitchConfigurationException
from pydantic import ValidationError


logger = create_logger('pfsense_rest_sbi')
POSTHEADERS = {'Content-Type': 'application/json'}


class PfSenseRestSbi:
    device: Device
    _rest_session: requests.Session = None

    def __init__(self, device: Device):
        self.device = device
        self.create_session()
        self.base_url = "http://{}/api/v1/".format(device.address)

    def create_session(self):
        self._rest_session = requests.Session()
        self.authenticate()

    def get_headers(self):
        return {
            'Authorization': f'{self.device.client_id} {self.device.key}',
            'Content-Type': 'application/json'
        }

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def authenticate(self):
        pass

    # GET
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def get(self, command, parsing_class=None) -> dict:

        logger.debug('{}{}'.format(self.base_url, command))
        try:
            res = self._rest_session.get(
                '{}{}'.format(self.base_url, command),
                headers=self.get_headers(),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        # logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code == 401:
            raise SwitchNotAuthenticatedException()

        if parsing_class:
            try:
                return parsing_class.model_validate(res.json()['data'])
            except ValidationError as e:
                print(f"Failed to parsing data with model {parsing_class}:", e)
                raise SwitchConfigurationException
        else:
            return res.json()['data']

    # PUT
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def put(self, command, data) -> dict:
        logger.debug("data: {}".format(data))
        try:
            res = self._rest_session.put(
                '{}{}'.format(self.base_url, command),
                json=data,
                headers=self.get_headers(),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code not in [200, 201, 202]:
            raise SwitchNotAuthenticatedException()
        # res = json.dumps(res.text)
        return True

    # POST
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def post(self, command: str, data: dict) -> bool:
        logger.debug("data: {}".format(data))
        try:
            res = self._rest_session.post(
                '{}{}'.format(self.base_url, command),
                json=data,
                headers=self.get_headers(),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code not in [200, 201, 202]:
            raise SwitchNotAuthenticatedException()
        # res = json.dumps(res.text)
        return True

    # DELETE
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def delete(self, url):
        headers = {
            'Authorization': f'{self.device.client_id} {self.device.key}',
            'Content-Type': 'application/json'
        }
        try:
            res = self._rest_session.delete(
                '{}{}'.format(self.base_url, url),
                headers=headers,
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {} {}'.format(res.status_code, res.text))
        if res.status_code not in [200, 202, 204]:
            raise SwitchNotAuthenticatedException()
        # res = json.dumps(res.text)
        return res.status_code
