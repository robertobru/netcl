from typing import Literal, Union, List, Optional
import requests
import xmltodict
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from netdevice import Device
from utils import create_logger
# from requests.packages.urllib3.exceptions import InsecureRequestWarning
from switch.switch_base import SwitchNotConnectedException, SwitchNotAuthenticatedException, \
    SwitchConfigurationException

logger = create_logger('xml_driver')
XmlNodeRequestType = Literal['get', 'action', 'set-create', 'set-delete', 'set-modify']
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

class MlnxOsXgRequestNode(BaseModel):
    name: Literal['get', 'action', 'set-create', 'set-delete', 'set-modify']
    type: str = 'string'
    value: str


class MlnxOsXgRequestNodeItem(BaseModel):
    node: MlnxOsXgRequestNode


class MlnxOsXgResponseNode(BaseModel):
    name: str
    type: str
    value: Union[str, None]


class MlnxOsXgResponseNodeItem(BaseModel):
    node: Union[MlnxOsXgResponseNode, List[MlnxOsXgResponseNode]]


class MlnxOsXgRequest(BaseModel):
    action_name: Literal["/do_rest"] = Field("/do_rest", alias='action-name')
    nodes: List[MlnxOsXgRequestNodeItem]

    def dump(self):
        return {
            'xg-request': {
                'action-request': self.model_dump(by_alias=True)
            }
        }

    @classmethod
    def create_single_node_request(cls, msg: str, name_msg='get', type_msg='string'):
        return cls.model_validate(
            {
                'nodes': [MlnxOsXgRequestNodeItem.model_validate(
                    {'node': {'name': name_msg, 'type': type_msg, 'value': msg}}
                )]
            }
        )

    @classmethod
    def create_multinode_node_request(cls, nodes: List[MlnxOsXgRequestNode]):
        node_items = [MlnxOsXgRequestNodeItem.model_validate({'node': item}) for item in nodes]
        return cls.model_validate({'nodes': node_items})


class MlnxOsReturnStatus(BaseModel):
    returnCode: int = Field(..., alias='return-code')
    returnMsg: Optional[str] = Field(..., alias='return-msg')


class MlnxOsActionResponse(BaseModel):
    returnStatus: MlnxOsReturnStatus = Field(..., alias='return-status')
    nodes: MlnxOsXgResponseNodeItem

    def get_status(self) -> int:
        return self.returnCode


class MlnxOsXgStatus(BaseModel):
    statusCode: int = Field(..., alias='status-code')
    statusMsg: Optional[str] = Field(..., alias='status-msg')


class XgResponse(BaseModel):
    xgStatus: Optional[MlnxOsXgStatus] = Field(None, alias='xg-status')
    actionResponse: Optional[MlnxOsActionResponse] = Field(None, alias='action-response')

    @classmethod
    def parse(cls, msg: str):
        logger.debug(xmltodict.parse(msg, force_list='node')['xg-response'])
        return cls.model_validate(
            xmltodict.parse(msg, force_list='node')['xg-response'])


class XmlRestSbi:
    device: Device
    _rest_session: requests.Session = None

    def __init__(self, device: Device):
        self.device = device
        self.create_session()

    def create_session(self):

        logger.debug("Creating REST session")
        self._rest_session = requests.Session()
        self.authenticate()
#fai un test
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def authenticate(self):
        data = {'f_user_id': self.device.user, 'f_password': self.device.passwd.get_secret_value()}
        try:
            self._rest_session.get(
                'https://{}/admin/launch?script=rh&template=login&action=login'.format(self.device.address),
                data=data,
                verify=False,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException

        self.post(
            MlnxOsXgRequest.model_validate(
                {
                    'nodes': [MlnxOsXgRequestNodeItem.model_validate(
                        {'node': {'name': 'get', 'type': 'string', 'value': '/mlnxos/api_version'}}
                    )]
                }
            )
        )
#due parametri, usare anche la post
    # comando /ip/address
    # data {data}
    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def post(self, msg: MlnxOsXgRequest) -> XgResponse:
        xmlstr = xmltodict.unparse(msg.dump())
        # print(xmlstr)
        headers = {'Content-Type': 'text/xml'}
        try:
            output = self._rest_session.post(
                'https://{}/xtree'.format(self.device.address),
                data=xmlstr,
                verify=False,
                headers=headers,
                timeout=(30, 60)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException()
        logger.debug('REST status {}\n{}'.format(output.status_code, output.text))
        if output.status_code != 200:
            raise SwitchNotAuthenticatedException()
        # print(output.text)
        res = XgResponse.parse(output.text)
        if res.xgStatus and (res.xgStatus.statusCode != 0 or res.xgStatus.statusMsg):
            if res.xgStatus.statusMsg == 'Not Authenticated':
                raise SwitchNotAuthenticatedException()
            else:
                raise SwitchConfigurationException("error no. {} - Message: {}".format(
                    res.xgStatus.statusCode, res.xgStatus.statusMsg))

        return res

    @retry(retry=retry_if_exception_type(SwitchNotConnectedException), stop=stop_after_attempt(3), reraise=True)
    def multi_post(self, msg: List[MlnxOsXgRequestNode]) -> List[MlnxOsXgResponseNode]:
        xmlstr = xmltodict.unparse(MlnxOsXgRequest.create_multinode_node_request(msg).dump())
        headers = {'Content-Type': 'text/xml'}
        try:
            output = self._rest_session.post(
                'https://{}/xtree'.format(self.device.address),
                data=xmlstr,
                verify=False,
                headers=headers,
                timeout=(45, 120)
            )
        except requests.exceptions.ConnectionError:
            raise SwitchNotConnectedException()
        logger.debug('REST status {}\n{}'.format(output.status_code, output.text))
        if output.status_code != 200:
            raise SwitchNotAuthenticatedException()
        res = XgResponse.parse(output.text)
        logger.debug(res)
        if res.xgStatus and (res.xgStatus.statusCode != 0 or res.xgStatus.statusMsg):
            if res.xgStatus.statusMsg == 'Not Authenticated':
                raise SwitchNotAuthenticatedException()
            else:
                raise SwitchConfigurationException("error no. {} - Message: {}".format(
                    res.xgStatus.statusCode, res.xgStatus.statusMsg))

        return [item for item in res.actionResponse.nodes.node]


def create_multinode_request(
        string_template: str,
        identifiers: List[Union[int, str]],
        request_type: XmlNodeRequestType = 'get',
        data_type='string'
) -> List[MlnxOsXgRequestNode]:
    return [
        MlnxOsXgRequestNode(name=request_type, value=string_template.format(item), type=data_type)
        for item in identifiers
    ]
