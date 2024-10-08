from fastapi import APIRouter, status, HTTPException
from network.nbi_msg_models import WorkerMsg
from typing import List, Dict, Union
from utils import persistency, create_logger
from network import net_worker
import traceback

_db = persistency.DB()
logger = create_logger('rest-operation')


operation_router = APIRouter(
    prefix="/v1/api/operation",
    tags=["Status of Operations"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@operation_router.get("/{}")
async def get_operation_status(operation_id: str) -> WorkerMsg:
    try:
        res = _db.findone_DB('operations', {'operation_id': operation_id})
        if not res:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return WorkerMsg(**res)
    except Exception:
        logger.error(traceback.format_exc())
        data = {
            'status': 'error',
            'resource': 'operation',
            'description': "Error retrieving operation",
            'detail': ' '.join(traceback.format_exc())
        }
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)
