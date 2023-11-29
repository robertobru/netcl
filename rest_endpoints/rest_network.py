from fastapi import APIRouter, status, HTTPException
from rest_endpoints.rest_models import RestAnswer202 , NetworkVrf, NetVlan, PortToNetVlans, NetVlanMsg, \
    PortToNetVlansMsg
from typing import List, Dict, Union
from utils import persistency, create_logger
from network import net_worker
import traceback

_db = persistency.DB()
logger = create_logger('rest-network')

net_api_router = APIRouter(
    prefix="/v1/api/network",
    tags=["Network Management"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@net_api_router.get("/vrf")
async def get_vrf(name: str | None = None) -> Union[NetworkVrf, List[NetworkVrf]]:
    if name:
        for s in net_worker.net.switches:
            vrf = next((item for item in s.vrfs if item.name == name))
            if vrf:
                vrf_model = vrf.model_dump()
                vrf_model['device'] = s.name
                return NetworkVrf.model_validate(vrf_model)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    else:
        vrfs = []
        for s in net_worker.net.switches:
            for v in s.vrfs:
                vrf_item = v.model_dump()
                vrf_item['device'] = s.name
                vrfs.append(NetworkVrf.model_validate(vrf_item))
        return vrfs


@net_api_router.get("/topology/")
async def get_topology() -> Dict:
    try:
        net_worker.net.build_graph()  # to be removed, here only for debug
        return net_worker.get_topology()
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving Switch list"}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@net_api_router.get("/topology/vrf/{vrf_name}", status_code=status.HTTP_200_OK)
async def get_vrf_topology(vrf_name: str) -> Dict:
    try:
        # net_worker.net.get_l3_overlay_topology(vrf_name)
        return net_worker.get_vrf_topology(vrf_name)
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving vrf with name {}".format(vrf_name)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)


@net_api_router.get("/topology/vlan/{vlan_id}", status_code=status.HTTP_200_OK)
async def get_vlan_topology(vlan_id: int) -> Dict:
    try:
        # net_worker.net.get_l3_overlay_topology(vrf_name)
        return net_worker.get_vlan_topology(vlan_id)
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'switch',
                'description': "Error retrieving the topology for vlan {}".format(vlan_id)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@net_api_router.post("/vlan", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def create_net_vlan(msg: NetVlan) -> RestAnswer202:
    worker_msg = NetVlanMsg.model_validate(msg.model_dump().update({'operation': 'add_net_vlan'}))
    if net_worker.net.get_switch_by_vlan_interface(msg.vid):
        data = {'status': 'error', 'resource': 'vlan',
                'description': "vlan {} already existing".format(msg.vid)}
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=data)
    try:
        net_worker.send_message(worker_msg)
        return worker_msg.produce_rest_answer_202()
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@net_api_router.delete("/vlan", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def del_net_vlan(msg: NetVlan) -> RestAnswer202:
    worker_msg = NetVlanMsg.model_validate(msg.model_dump().update({'operation': 'del_net_vlan'}))
    if not net_worker.net.get_switch_by_vlan_interface(msg.vid):
        data = {'status': 'error', 'resource': 'vlan',
                'description': "vlan {} not existing".format(msg.vid)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)
    try:
        net_worker.send_message(worker_msg)
        return worker_msg.produce_rest_answer_202()
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@net_api_router.put("/vlan", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def mod_net_vlan(msg: NetVlan) -> RestAnswer202:
    worker_msg = NetVlanMsg.model_validate(msg.model_dump().update({'operation': 'mod_net_vlan'}))
    if not net_worker.net.get_switch_by_vlan_interface(msg.vid):
        data = {'status': 'error', 'resource': 'vlan',
                'description': "vlan {} not existing".format(msg.vid)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)
    try:
        net_worker.send_message(worker_msg)
        return worker_msg.produce_rest_answer_202()
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@net_api_router.get("/vlan/{vid}", response_model=NetVlan, status_code=status.HTTP_200_OK)
async def get_net_vlan(vid: int) -> NetVlan:
    switch = net_worker.net.get_switch_by_vlan_interface(vid)
    if not switch:
        data = {'status': 'error', 'resource': 'vlan',
                'description': "vlan {} not existing".format(vid)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)
    try:
        vlan_intf = next(item for item in switch.vlan_l3_ports if item.vlan == vid)
        return NetVlan.model_validate({
            'vid': vid,
            'cidr': vlan_intf.cidr,
            'gateway': vlan_intf.ipaddress,
            'group': vlan_intf.vrf,
            'description': vlan_intf.description
        })
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@net_api_router.post("/vlan/port", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def create_port_vlan_assignment(msg: PortToNetVlans) -> RestAnswer202:
    pass


@net_api_router.delete("/vlan/port", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def delete_port_vlan_assignment(msg: PortToNetVlans) -> RestAnswer202:
    pass


@net_api_router.put("/vlan/port", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def modify_port_vlan_assignment(msg: PortToNetVlans) -> RestAnswer202:
    pass


@net_api_router.get("/vlan/port/{}/{}", response_model=PortToNetVlans, status_code=status.HTTP_200_OK)
async def delete_port_vlan_assignment(switch_name: str, port_name: str) -> PortToNetVlans:
    pass
