import networkx as nx
from switch import Switch
from netdevice import Device
from typing import List
from utils import persistency, create_logger
from pydantic import BaseModel
import queue
import threading
import traceback
from typing import Literal, Any

_db = persistency.DB()
logger = create_logger('network')


class Network:
    switches: List[Switch] = []

    def __init__(self):
        db_switches = _db.find_DB('switches', {})
        for sw in db_switches:
            self.switches.append(Switch.from_db(device_name=sw['name']))

    def onboard_switch(self, node: Device):
        new_switch = Switch.create(node)
        new_switch.to_db()
        if new_switch.state != 'ready':
            logger.warn('switch {} is in {} state'.format(new_switch.name, new_switch.state))
        self.switches.append(new_switch)
        # FIXME: it is a topological change

    def delete_switch(self, name):
        switch_to_del = filter(lambda x: x.name == name, self.switches)
        if not switch_to_del:
            switch_to_del = Switch.from_db(device_name=name)
            if not switch_to_del:
                raise ValueError('switch to delete not found')
        switch_to_del.destroy()
        self.switches = [item for item in self.switches if item.name != name]


    def get_graph(self):
        graph = nx.Graph()
        for s in self.switches:
            graph.add_node(s.name)

        for s in self.switches:
            for p in s.phy_ports:
                if s.get_neighbors(p.name):
                    graph.add_edge(s.name, s.get_neighbors(p.name)[0])

        return graph


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

    def destroy(self):
        pass


net_worker = NetworkWorker()
