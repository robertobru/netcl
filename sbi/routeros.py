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
                auth=HTTPBasicAuth(self.device.user, self.device.passwd),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.error('code {}, {}'.format(responce.status_code, responce.content))

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def post(self, url, msg: dict) -> json:
        data = json.dumps(msg)
        try:
            responce = self._rest_session.post(
                'http://{}/rest/{}/{}'.format(self.device.address, url, data),
                auth=HTTPBasicAuth(self.device.user, self.device.passwd),
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException
        logger.debug('REST status {}\n{}'.format(responce.status_code, responce.text))
        if responce.status_code != 200:
            raise SwitchNotAuthenticatedException()

    # due parametri, usare anche la post
    # comando /ip/address
    # data {data}
    # @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    # def post(self, msg: MlnxOsXgRequest) -> XgResponse:
    #     xmlstr = xmltodict.unparse(msg.dump())
    #     # print(xmlstr)
    #     headers = {'Content-Type': 'text/xml'}
    #     try:
    #         output = self._rest_session.post(
    #             'https://{}/xtree'.format(self.device.address),
    #             data=xmlstr,
    #             verify=False,
    #             headers=headers,
    #             timeout=(30, 60)
    #         )
    #     except requests.exceptions.ConnectionError:
    #         raise SwitchNotConnectedException()
    #     logger.debug('REST status {}\n{}'.format(output.status_code, output.text))
    #     if output.status_code != 200:
    #         raise SwitchNotAuthenticatedException()
    #     # print(output.text)
    #     res = XgResponse.parse(output.text)
    #     if res.xgStatus and (res.xgStatus.statusCode != 0 or res.xgStatus.statusMsg):
    #         if res.xgStatus.statusMsg == 'Not Authenticated':
    #             raise SwitchNotAuthenticatedException()
    #         else:
    #             raise SwitchConfigurationException("error no. {} - Message: {}".format(
    #                 res.xgStatus.statusCode, res.xgStatus.statusMsg))
    #
    #     return res
    #
    # @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    # def multi_post(self, msg: List[MlnxOsXgRequestNode]) -> List[MlnxOsXgResponseNode]:
    #     xmlstr = xmltodict.unparse(MlnxOsXgRequest.create_multinode_node_request(msg).dump())
    #     headers = {'Content-Type': 'text/xml'}
    #     try:
    #         output = self._rest_session.post(
    #             'https://{}/xtree'.format(self.device.address),
    #             data=xmlstr,
    #             verify=False,
    #             headers=headers,
    #             timeout=(45, 120)
    #         )
    #     except requests.exceptions.ConnectionError:
    #         raise SwitchNotConnectedException()
    #     logger.debug('REST status {}\n{}'.format(output.status_code, output.text))
    #     if output.status_code != 200:
    #         raise SwitchNotAuthenticatedException()
    #     res = XgResponse.parse(output.text)
    #     logger.debug(res)
    #     if res.xgStatus and (res.xgStatus.statusCode != 0 or res.xgStatus.statusMsg):
    #         if res.xgStatus.statusMsg == 'Not Authenticated':
    #             raise SwitchNotAuthenticatedException()
    #         else:
    #             raise SwitchConfigurationException("error no. {} - Message: {}".format(
    #                 res.xgStatus.statusCode, res.xgStatus.statusMsg))
    #
    #     return [item for item in res.actionResponse.nodes.node]
