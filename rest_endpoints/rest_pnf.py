from fastapi import APIRouter, status, HTTPException
from network.nbi_msg_models import RestAnswer202, AddPnfRequest, AddPnfRequestMsg, DelPnfRequestMsg
from network.network_models import PnfElement, NetworkPnfs
from typing import List, Dict, Union
from utils import persistency, create_logger
from network.network import net_worker
import traceback

_db = persistency.DB()
logger = create_logger('rest-pnf')

pnf_api_router = APIRouter(
    prefix="/v1/api/pnf",
    tags=["Physical Network Function Management"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@pnf_api_router.get("/")
async def get_pnf(name: str | None = None) -> Union[PnfElement, NetworkPnfs]:
    if name:
        pnf = net_worker.net.pnfs.get(name=name)
        if pnf:
            return pnf
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    else:
        return net_worker.net.pnfs


@pnf_api_router.post("/pnf", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def create_pnf(msg: AddPnfRequest) -> RestAnswer202:
    if net_worker.net.pnfs.get(name=msg.name):
        data = {'status': 'error', 'resource': 'pnf',
                'description': "A Pnf with name {} already exists".format(msg.name)}
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=data)

    worker_msg = AddPnfRequestMsg(**msg.model_dump(), operation='add_pnf')
    try:
        net_worker.send_message(worker_msg)
        return worker_msg.produce_rest_answer_202()
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@pnf_api_router.delete("pnf/{name}", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def del_pnf(name: str) -> RestAnswer202:
    pnf = net_worker.net.pnfs.get(name=name)
    if not pnf:
        data = {'status': 'error', 'resource': 'pnf',
                'description': "A Pnf with name {} does not exist".format(name)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)
    worker_msg = DelPnfRequestMsg(pnf_name=name, operation='del_net_vlan')
    try:
        net_worker.send_message(worker_msg)
        return worker_msg.produce_rest_answer_202()
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

