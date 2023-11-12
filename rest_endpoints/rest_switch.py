from fastapi import APIRouter, status, HTTPException
from switch import SwitchDataModel, Switch
from typing import List, Dict, Literal
from netdevice import Device
from utils import persistency, create_logger
from pydantic import BaseModel, AnyHttpUrl
from threading import Thread
from network import net_worker
import traceback

_db = persistency.DB()
logger = create_logger('rest-switch')


class RestAnswer202(BaseModel):
    id: str
    description: str ='operation submitted'
    status: str ='submitted'


class CallbackModel(BaseModel):
    id: str
    operation: str
    status: str
    detailed_status: str


class CallbackRequest(BaseModel):
    callback: AnyHttpUrl = None

netmgt_router = APIRouter(
    prefix="/v1/api/network_management",
    tags=["Network Management"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


class SwitchListItem(BaseModel):
    name: str
    model: str
    state: Literal["init", "ready", "config_error", "auth_error", "net_error", "executing"]


@netmgt_router.get("/{switch_name}", response_model=SwitchDataModel)
async def get_switch(switch_name: str) -> Dict:
    try:
        switch = Switch.from_db(switch_name)
        if not switch:
            data = {'status': 'error', 'resource': 'switch',
                'description': "Switch {} not found".format(switch_name)}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)
        else:
            return switch.model_dump()
    except Exception:
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving Switch {}".format(switch_name)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@netmgt_router.get("/", response_model=List[SwitchListItem])
async def get_switch_list() -> List[SwitchListItem]:
    try:
        dbswitches = _db.find_DB("switches", {})
        switch_list = [SwitchListItem.model_validate(item) for item in dbswitches]
        return switch_list
    except Exception:
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving Switch list"}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@netmgt_router.post('/', response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def onboard_switch(msg: Device) -> RestAnswer202:
    try:
        logger.info('received add switch msg: {}'.format(msg.model_dump()))
        net_worker.send_message('add_switch', msg)
        # reply with submitted code
        return RestAnswer202(id=msg.name, resource="switch", operation="onboard", status="submitted")

    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error onboarding Switch {}".format(msg.name)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@netmgt_router.delete("/{switch_name}", response_model=RestAnswer202, status_code=status.HTTP_200_OK)
async def del_switch(switch_name: str) -> Dict:
    try:
        switch = Switch.from_db(switch_name)
        if not switch:
            data = {'status': 'error', 'resource': 'switch',
                    'description': "Switch {} not found".format(switch_name)}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)
        else:
            net_worker.send_message('del_switch', switch)
            return RestAnswer202(id=switch.name, resource="switch", operation="onboard", status="submitted")
    except Exception:
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving Switch {}".format(switch_name)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@netmgt_router.get("/topology/")
async def get_topology() -> Dict:
    try:
        return net_worker.get_topology()
    except Exception:
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving Switch list"}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)
