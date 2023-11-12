import networkx as nx
from switch import Switch
from netdevice import Device
from typing import List
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
    graph: nx.Graph = None

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

    def build_graph(self) -> None:
        graph = nx.Graph()
        for s in self.switches:
            logger.debug("adding node {} to the graph".format(s.name))
            graph.add_node(s.name)

        for s in self.switches:
            for p in s.phy_ports:
                logger.debug("checking port {}".format(p.index))
                neigh_info = s.get_neighbors(p.index)
                if neigh_info:
                    logger.debug("found edge between switch {} and {}".format(s.name, s.get_neighbors(p.index)))
                    graph.add_edge(s.name, neigh_info.neighbor,
                                   ports={s.name: p.name, neigh_info.neighbor: neigh_info.remote_interface})

        self.graph = graph

    def get_topology_dict(self) -> Dict:
        return nx.convert.to_dict_of_dicts(self.graph)

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
