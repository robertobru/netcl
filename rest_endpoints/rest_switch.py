from fastapi import APIRouter, status, HTTPException
from models import SwitchMsg, DelSwitchMsg, RestAnswer202, SwitchDataModel
from switch import Switch
from typing import List, Dict, Literal
from netdevice import Device
from utils import persistency, create_logger
from pydantic import BaseModel
from network import net_worker
import traceback

_db = persistency.DB()
logger = create_logger('rest-switch')

device_api_router = APIRouter(
    prefix="/v1/api/device",
    tags=["Device Management"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


class SwitchListItem(BaseModel):
    name: str
    model: str
    state: Literal["init", "reinit", "ready", "config_error", "auth_error", "net_error", "executing"]


@device_api_router.get("/{switch_name}", response_model=SwitchDataModel)
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
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving Switch {}".format(switch_name)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@device_api_router.get("/", response_model=List[SwitchListItem])
async def get_switch_list() -> List[SwitchListItem]:
    try:
        dbswitches = _db.find_DB("switches", {})
        switch_list = [SwitchListItem.model_validate(item) for item in dbswitches]
        return switch_list
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving Switch list"}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@device_api_router.post('/', response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def onboard_switch(msg: Device) -> RestAnswer202:
    try:
        logger.info('received add switch msg: {}'.format(msg.model_dump()))
        worker_msg = SwitchMsg(**msg.model_dump(), operation='add_switch')
        net_worker.send_message(worker_msg)
        # reply with submitted code
        return worker_msg.produce_rest_answer_202()

    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error onboarding Switch {}".format(msg.name)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@device_api_router.delete("/{switch_name}", response_model=RestAnswer202, status_code=status.HTTP_200_OK)
async def del_switch(switch_name: str) -> RestAnswer202:
    try:
        switch = Switch.from_db(switch_name)
        if not switch:
            data = {'status': 'error', 'resource': 'switch',
                    'description': "Switch {} not found".format(switch_name)}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)

        worker_msg = DelSwitchMsg.model_validate({'operation': 'del_switch', 'switch': switch})
        net_worker.send_message(worker_msg)
        return worker_msg.produce_rest_answer_202()
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error removing Switch {}".format(switch_name)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)
