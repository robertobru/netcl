import queue
import threading
import time
import traceback
from typing import Dict

import networkx as nx

from .nbi_msg_models import WorkerMsg
from netdevice import Device
from .network import Network
from .network_base import logger


class NetworkWorker:
    queue: queue.Queue[WorkerMsg]
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

    def send_message(self, worker_msg: WorkerMsg):
        worker_msg.to_db()
        self.queue.put(worker_msg)

    def next_msg(self):
        # Fixme: wait for switches to be ready
        counter = 0
        while self.net.switches.check_switch_ready():
            logger.info("switches are noy yet ready. Awaiting 30 seconds.")
            time.sleep(30)
            counter += 1
            if counter == 20:
                raise ValueError("swithes are not ready. Timeout expiring")

        while True:
            logger.info('network worker awaiting for new job')
            s_input = self.queue.get()
            logger.info('network worker received new job {}'.format(s_input.operation))
            if s_input.operation == 'stop':
                self.destroy()
                logger.info('removing the network worker thread')
                break
            try:
                result = False
                match s_input.operation:
                    case 'set_config':
                        self.net.set_config(s_input)
                        result = True
                    case 'add_switch':
                        self.net.onboard_switch(Device.model_validate(s_input.model_dump()))
                        result = self.net.assert_add_switch(Device.model_validate(s_input.model_dump()))
                    case 'del_switch':
                        self.net.delete_switch(s_input.switch_name)
                        result = self.net.assert_del_switch(Device.model_validate(s_input.model_dump()))
                    case 'del_net_vlan':
                        self.net.delete_net_vlan(s_input)
                        result = self.net.assert_net_vlan(s_input)
                    case 'add_net_vlan':
                        self.net.create_net_vlan(s_input)
                        result = self.net.assert_net_vlan(s_input)
                    case 'mod_net_vlan':
                        self.net.modify_net_vlan(s_input)
                        result = self.net.assert_net_vlan(s_input)
                    case 'add_port_vlan':
                        self.net.add_port_vlan(s_input)
                        result = self.net.assert_port_vlan(s_input)
                    case 'del_port_vlan':
                        self.net.del_port_vlan(s_input)
                        result = self.net.assert_port_vlan(s_input)
                    case 'mod_port_vlan':
                        self.net.mod_port_vlan(s_input)
                        result = self.net.assert_port_vlan(s_input)
                    case 'add_pnf':
                        self.net.add_pnf(s_input)
                        result = self.net.assert_pnf(s_input)
                    case 'del_pnf':
                        self.net.del_pnf(s_input)
                        result = self.net.assert_pnf(s_input)
                    case 'bind_groups':
                        self.net.bind_groups(s_input)
                        result = self.net.assert_bind_groups(s_input)
                    case 'unbind_groups':
                        self.net.unbind_groups(s_input)
                        result = self.net.assert_unbind_groups(s_input)

                    case _:
                        raise ValueError('msg operation {} not supported'.format(s_input.operation))
                if result:
                    s_input.update_status('Success')
                else:
                    raise ValueError('msg operation {} verification failed'.format(s_input.operation))
            except Exception as e:
                s_input.update_status('Failed')
                logger.error(traceback.format_tb(e.__traceback__))
                logger.error(str(e))
            finally:
                # ToDo: block until message
                self.queue.task_done()

    def get_topology(self) -> Dict:
        return self.net.get_topology_dict()

    def get_vrf_topology(self, vrf_name: str):
        return nx.convert.to_dict_of_dicts(self.net.get_l3_overlay_topology(vrf_name))

    def get_vlan_topology(self, vlan_id: int):
        return nx.convert.to_dict_of_dicts(self.net.get_vlan_overlay(vlan_id))

    def destroy(self):
        pass
