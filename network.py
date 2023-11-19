import networkx as nx
from switch import Switch
from netdevice import Device
from typing import List, Union, Tuple
from utils import persistency, create_logger
from pydantic import BaseModel
import queue
import threading
import traceback
from typing import Literal, Any, Dict

_db = persistency.DB()
logger = create_logger('network')


class Network:
    switches: List[Switch] = []
    graph: nx.MultiGraph = None

    def __init__(self):
        db_switches = _db.find_DB('switches', {})
        for sw in db_switches:
            self.switches.append(Switch.from_db(device_name=sw['name']))
        self.build_graph()

    def onboard_switch(self, node: Device):
        new_switch = Switch.create(node)
        new_switch.to_db()
        if new_switch.state != 'ready':
            logger.warn('switch {} is in {} state'.format(new_switch.name, new_switch.state))
        self.switches.append(new_switch)
        self.build_graph()

    def delete_switch(self, switch: Switch):
        self.switches = [item for item in self.switches if item.name != switch.name]
        switch.destroy()
        self.build_graph()

    def get_topology_link(self, node1: str, node2: str, port1: str, port2: str) -> Union[Tuple[str, str, Dict], None]:
        return next((e for e in self.graph.edges(data=True) if 'ports' in e[2]
                     and ((e[0] == node1 and e[1] == node2) or (e[0] == node2 and e[1] == node1))
                     and e[2]['ports'] == {node1: port1, node2: port2}
                     ), None)

    def build_graph(self) -> None:
        self.graph = nx.MultiGraph()
        for s in self.switches:
            logger.debug("adding node {} to the graph".format(s.name))
            self.graph.add_node(s.name, vlans=s.vlans, managed=True)

        for s in self.switches:
            for p in s.phy_ports:
                logger.debug("checking port {}".format(p.index))
                neigh_info = s.get_neighbors(p.index)
                if neigh_info:
                    edge = self.get_topology_link(neigh_info.neighbor, s.name, neigh_info.remote_interface, p.name)
                    if self.graph.has_edge(s.name, neigh_info.neighbor):
                        logger.debug("found another link between {} and {}... checking".format(
                            s.name, neigh_info.neighbor))
                    if edge:
                        logger.debug("edge between switch {} and {} already existing: {}".format(
                            s.name, s.get_neighbors(p.index), edge))
                        # checking vlans on the two switches
                        vlans_only_in_p = set(p.trunk_vlans + [p.access_vlan]) - set(edge[2]['vlans'])
                        vlans_only_in_neigh = set(edge[2]['vlans']) - set(p.trunk_vlans + [p.access_vlan])
                        if vlans_only_in_p:
                            edge[2]['missing_vlan_errors'][neigh_info.neighbor] = vlans_only_in_p
                        if vlans_only_in_neigh:
                            edge[2]['missing_vlan_errors'][s.name] = vlans_only_in_neigh
                        edge[2]['vlans'] = set(p.trunk_vlans + [p.access_vlan]) | set(edge[2]['vlans'])
                    else:
                        logger.debug("found edge between switch {} and {}".format(s.name, s.get_neighbors(p.index)))
                        self.graph.add_edge(s.name, neigh_info.neighbor,
                                            ports={s.name: p.name, neigh_info.neighbor: neigh_info.remote_interface},
                                            vlans=p.trunk_vlans + [p.access_vlan],
                                            missing_vlan_errors={s.name: [], neigh_info.neighbor: []},
                                            weight=1000000 / p.speed if p.speed else 1000
                                            )

    def get_topology_dict(self, managed=False) -> Dict:
        if managed:
            return nx.convert.to_dict_of_dicts(self.graph.subgraph([s.name for s in self.switches]))
        else:
            return nx.convert.to_dict_of_dicts(self.graph)

    def get_shortest_path(self, src_switch: str, dst_switch: str) -> List[Tuple[str, str, Dict]]:
        try:
            path = nx.shortest_path(self.graph, source=src_switch, target=dst_switch, weight='weight')
            # checking if switches in the path are not in error state
            for switch_name in path:
                switch = next(item for item in self.switches if item.name == switch_name)
                if switch.state in ['config_error', 'net_error', 'auth_error']:
                    raise ValueError("switch {} is not available since it is in {}".format(switch.name, switch.state))

            # path contains a list of switch name to be crossed. Multiple links might exist between switches
            selected_path = []
            for (s, d) in path:
                links = self.graph.edges[s][d]
                selected_link = None
                for e in links:
                    if not selected_link or e[3]['weight'] < selected_link[3]['weight']:
                        selected_link = e
                selected_path.append(selected_link)
            return selected_path
        except Exception:
            return []

    def get_vlan_overlay(self, vlan_id: int) -> nx.MultiGraph:
        vlan_graph = nx.MultiGraph()
        for switch in self.switches:
            if vlan_id in switch.vlans:
                vlan_interface = next((item for item in switch.vlan_l3_ports if item.vlan == vlan_id), None)
                vlan_graph.add_node(switch.name, vlan_interface=vlan_interface, vlan_configured=True)
        for edge in self.graph.edges:
            if vlan_id in edge['vlans']:
                vlan_graph.add_edge(edge[0], edge[1], edge[2])
        return vlan_graph

    def get_l3_overlay_topology(self, vrf_name: str):
        pass

class WorkerMessage(BaseModel):
    operation: Literal['add_switch', 'del_switch']
    request_msg: Any


class NetworkWorker:
    queue: queue.Queue[WorkerMessage]
    net: Network

    def __init__(self):
        logger.info("initializing the network")
        self.net = Network()
        logger.info("initializing the network worker")
        self.queue = queue.Queue()
        thread = threading.Thread(target=self.next_msg, name="network_thread")
        # thread.daemon = True
        thread.start()
        logger.info("initialization complete")

    def send_message(self, operation, request_msg):
        self.queue.put(WorkerMessage(operation=operation, request_msg=request_msg))

    def next_msg(self):
        while True:
            logger.info('network worker awaiting for new job')
            s_input = self.queue.get()
            logger.info('network worker received new job {}'.format(s_input.operation))
            if s_input.operation == 'stop':
                self.destroy()
                logger.info('removing the network worker thread')
                break
            try:
                match s_input.operation:
                    case 'add_switch':
                        self.net.onboard_switch(s_input.request_msg)
                    case 'del_switch':
                        self.net.delete_switch(s_input.request_msg)
                    case _:
                        raise ValueError('msg operation not found')
                # self.process_session(s_input.request_msg, s_input.operation)
            except Exception as e:
                logger.error(traceback.format_tb(e.__traceback__))
                logger.error(str(e))
            # if callback then send failure
            #    pass
            finally:
                self.queue.task_done()

    def process_session(self, msg, operation):
        pass

    def get_topology(self) -> Dict:
        return self.net.get_topology_dict()

    def destroy(self):
        pass


net_worker = NetworkWorker()
