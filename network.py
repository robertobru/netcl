import networkx as nx
from switch import Switch
from netdevice import Device
from typing import List, Union, Tuple, Literal
from utils import persistency, create_logger
from models import WorkerMsg, NetVlanMsg, SwitchRequestVlanL3Port, PortToNetVlansMsg, VlanTerminations, \
     VlanInterfaceTermination, PhyPort
import queue
import threading
import traceback
from typing import Dict

_db = persistency.DB()
logger = create_logger('network')


def compare_graph_edges(e1_src: str, e1_dst: str, e1_data: Dict[str, str], e2_src: str, e2_dst: str,
                        e2_data: Dict[str, str]) -> bool:
    return 'ports' in e1_data \
           and 'ports' in e2_data \
           and ((e1_src == e2_src and e1_dst == e2_dst) or (e1_src == e2_dst and e1_dst == e2_src)) \
           and e1_data['ports'] == e2_data['ports']


class Network:
    switches: List[Switch] = []
    graph: nx.MultiGraph = None
    groups: dict[str, str] = {}
    vlan_terminations: dict[int, VlanTerminations]

    def __init__(self):
        db_switches = _db.find_DB('switches', {})
        threads = []
        for sw in db_switches:
            switch_obj, switch_thread = Switch.from_db(device_name=sw['name'])
            self.switches.append(switch_obj)
            threads.append(switch_thread)

        groups_data = _db.findone_DB('groups', {'type': 'groups'})
        if groups_data is None:
            logger.warning('no groups found on the database')
            self.groups = {}
        else:
            self.groups = groups_data['groups']
        self.vlan_terminations = dict()

        for t in threads:
            t.join()
            logger.info('init for switch thread {} terminated'.format(t.name))
        self.build_graph()
        self.build_vlan_data()

    # ##################### Vlan Termination Methos ##########################################

    def _set_vlan_interface_termination(self, switch: Switch, vid: int) -> None:
        for _v_itf in switch.vlan_l3_ports:
            # logger.debug("now on {}".format(_v_itf))
            if vid == _v_itf.vlan:
                logger.debug('found Vlan Interface for Vlan {} on switch {}'.format(vid, switch.name))
                if vid not in self.vlan_terminations.keys():
                    self.vlan_terminations[vid] = VlanTerminations()
                # if self.vlan_terminations[vid].vlan_interface:
                #    raise ValueError("multiple vlan interfaces found for vlan {}".format(vid))
                self.vlan_terminations[vid].vlan_interface = VlanInterfaceTermination(
                    name=_v_itf.index, switch_name=switch.name)

    def _set_vlan_server_termination(self, _s: Switch, vid: int, managed_switch_names: List[str]) -> None:
        for _port in _s.phy_ports:
            if _port.status == 'UP' and _port.neighbor:
                # check if the VLAN is used in trunk or access to connect servers
                if (vid in _port.trunk_vlans and _port.mode in ['TRUNK', 'HYBRID']) or \
                        (vid == _port.access_vlan and _port.mode in ['ACCESS', 'HYBRID']):
                    if _port.neighbor.neighbor not in managed_switch_names:
                        logger.debug('found Vlan {} termination on switch {} port {} towards server {}'
                                     .format(vid, _s.name, _port.name, _port.neighbor.neighbor))
                        if vid not in self.vlan_terminations.keys():
                            self.vlan_terminations[vid] = VlanTerminations()

                        if _s.name not in self.vlan_terminations[vid].server_ports.keys():
                            self.vlan_terminations[vid].server_ports[_s.name] = [_port.name]
                        else:
                            self.vlan_terminations[vid].server_ports[_s.name].append(_port.name)

    def _add_vlan_server_termination(self, _s: Switch, _p: PhyPort, vid: int) -> None:
        if vid not in self.vlan_terminations.keys():
            self.vlan_terminations[vid] = VlanTerminations()
        if _s.name not in self.vlan_terminations[vid].keys():
            self.vlan_terminations[vid].server_ports[_s.name] = [_p.name]
        if _p.name not in self.vlan_terminations[vid].server_ports[_s.name]:
            self.vlan_terminations[vid].server_ports[_s.name].append(_p.name)

    def _del_vlan_server_termination(self, _s: Switch, _p: PhyPort, vid: int):
        if _p.name in self.vlan_terminations[vid].server_ports[_s.name]:
            self.vlan_terminations[vid].server_ports[_s.name].remove(_p.name)
        if len(self.vlan_terminations[vid].server_ports[_s.name]) == 0:
            self.vlan_terminations[vid].server_ports.pop(_s.name)
        if len(self.vlan_terminations[vid].server_ports.keys()) == 0 and not self.vlan_terminations[vid].vlan_interface:
            self.vlan_terminations.pop(vid)

    def vlan_check_backbone_needed(
            self,
            vid: int,
            switch_name: str = None,
            operation: Literal['add', 'del', 'as_is'] = 'as_is'
    ) -> bool:

        if vid not in self.vlan_terminations.keys():
            return False
        switch_names = self.vlan_terminations[vid].get_switch_names()
        if operation == 'add':
            return len(switch_names.union(set(switch_name))) > 1
        elif operation == 'del':
            return len(switch_names.difference(set(switch_name))) < 1
        else:  # operation ==  as_is
            return len(switch_names) > 1

    def vlan_check_backbone_connectivity(self, vlan_id: int) -> Tuple[List[Tuple], bool]:
        backbone = self.get_backbone_topology()
        link_missing = []
        for edge in backbone.edges(data=True):
            if vlan_id not in edge[2]['vlans']:
                link_missing.append(edge)
        return link_missing, len(link_missing) > 0

    def from_topology_link_to_switch_port(self, edge: Tuple) -> Tuple[Switch, PhyPort]:
        switch = next(item for item in self.switches if item.name == edge[0])
        port = next(item for item in switch.phy_ports if item.name == edge[2][switch.name])
        return switch, port

    def build_vlan_data(self):
        managed_switch_names = [item.name for item in self.switches]
        for _s in self.switches:
            for vid in _s.vlans:
                self._set_vlan_interface_termination(_s, vid)
                self._set_vlan_server_termination(_s, vid, managed_switch_names)
                if vid in self.vlan_terminations.keys():
                    self.vlan_terminations[vid].topology = self.get_vlan_overlay(vid, only_managed_nodes=True)
        logger.info(self.vlan_terminations)
        all_vlans = set()
        for _s in self.switches:
            all_vlans.update(_s.vlans)
        logger.info("used vlans {}".format(set(self.vlan_terminations.keys())))
        logger.info(" all vlans {}".format(all_vlans))
        logger.info("configured but unused vlans {}".format(all_vlans - set(self.vlan_terminations.keys())))

    # ########################################################################################################

    def onboard_switch(self, node: Device):
        new_switch = Switch.create(node)
        new_switch.to_db()
        if new_switch.state != 'ready':
            logger.warn('switch {} is in {} state'.format(new_switch.name, new_switch.state))
        self.switches.append(new_switch)
        self.build_graph()

    def delete_switch(self, switch_name: str):
        switch_to_destroy = next(item for item in self.switches if item.name == switch_name)
        self.switches = [item for item in self.switches if item.name != switch_name]
        switch_to_destroy.destroy()
        self.build_graph()

    def get_topology_link(self, node1: str, node2: str, port1: str, port2: str) -> Union[Tuple[str, str, Dict], None]:
        return next((e for e in self.graph.edges(data=True)
                     if compare_graph_edges(*e, node1, node2, {node1: port1, node2: port2})), None)

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
                        edge[2]['vlans'] = list[set(p.trunk_vlans + [p.access_vlan]) | set(edge[2]['vlans'])]
                    else:
                        logger.debug("found edge between switch {} and {}".format(s.name, s.get_neighbors(p.index)))
                        self.graph.add_edge(s.name, neigh_info.neighbor,
                                            ports={s.name: p.name, neigh_info.neighbor: neigh_info.remote_interface},
                                            vlans=p.trunk_vlans + [p.access_vlan],
                                            missing_vlan_errors={s.name: [], neigh_info.neighbor: []},
                                            weight=1000000 / p.speed if p.speed else 1000
                                            )
                        if not p.speed:
                            logger.warning("link {}-{} ports={} has not a valid speed!".format(
                                s.name,
                                neigh_info.neighbor,
                                {s.name: p.name, neigh_info.neighbor: neigh_info.remote_interface})
                            )

    def get_topology_dict(self, managed=False) -> Dict:
        if managed:
            return nx.convert.to_dict_of_dicts(self.graph.subgraph([s.name for s in self.switches]))
        else:
            return nx.convert.to_dict_of_dicts(self.graph)

    def get_backbone_topology(self) -> nx.MultiGraph:
        # return the topology among managed switches
        managed_switches = [item.name for item in self.switches]
        return self.graph.subgraph(managed_switches)

    def get_vlan_overlay(self, vlan_id: int, only_managed_nodes: bool = False) -> nx.MultiGraph:
        managed_nodes = [item.name for item in self.switches]
        vlan_graph = nx.MultiGraph()
        for switch in self.switches:
            if vlan_id in switch.vlans:
                logger.debug('add switch {} to the topology of vlan {}'.format(switch.name, vlan_id))
                vlan_interface = next((item for item in switch.vlan_l3_ports if item.vlan == vlan_id), None)
                vlan_graph.add_node(switch.name, vlan_interface=vlan_interface, vlan_configured=True)

        for e in self.graph.edges(data=True):
            if only_managed_nodes:
                if e[0] in managed_nodes and e[1] in managed_nodes and vlan_id in e[2]['vlans']:
                    vlan_graph.add_edge(e[0], e[1], ports=e[2]['ports'], weight=e[2]['weight'])
            else:
                if vlan_id in e[2]['vlans']:
                    vlan_graph.add_edge(e[0], e[1], ports=e[2]['ports'], weight=e[2]['weight'])
        return vlan_graph

    def get_l3_overlay_topology(self, vrf_name: str) -> nx.MultiGraph:
        vrf_graph = nx.MultiGraph()
        selected_vrf = None
        vrf_switch = None
        for switch in self.switches:
            for vrf in switch.vrfs:

                if vrf.name == vrf_name:
                    logger.debug('vrf {} is on switch {}'.format(vrf_name, switch.name))
                    selected_vrf = vrf
                    vrf_switch = switch
                    break
        if not selected_vrf:
            return vrf_graph

        vrf_vlans = [item.vlan for item in selected_vrf.ports]
        vrf_graph.add_node(vrf_switch.name, vrf=vrf_name, vlans=vrf_vlans)
        for vlan_id in vrf_vlans:
            vlan_overlay = self.get_vlan_overlay(vlan_id)
            vrf_graph.add_nodes_from(vlan_overlay.nodes)
            for edge in vlan_overlay.edges(data=True):
                existing_edge = next((e for e in vrf_graph.edges(data=True) if e[0] == edge[0] and e[1] == edge[1] and
                                      e[2]['ports'] == edge[2]['ports']), None)
                if not existing_edge:
                    vrf_graph.add_edge(edge[0], edge[1], ports=edge[2]['ports'], vlans=set.intersection(
                        set(vrf_vlans), set(edge[2]['vlans']) if 'vlans' in edge[2] else set()))

        return vrf_graph

    def find_available_vrf(self, group_name: str) -> str:
        for s in self.switches:
            for v in s.vrfs:
                if v.name not in self.groups.values() and v.name[:4] == 'proj' and len(v.ports) < 2:
                    logger.info("selected VRF {}".format(v.name))
                    self.groups[group_name] = v.name
                    return v.name
        raise ValueError('no VRFs available')

    def create_net_vlan(self, msg: NetVlanMsg):
        # Vlan interfaces should be unique over all the network
        for s in self.switches:
            for vlan_itf in s.vlan_l3_ports:
                if vlan_itf.vlan == msg.vid:
                    logger.error("found already existing vlan interface in create_net_vlan")
                    raise ValueError("Vlan interface for vlan id {} already existing into switch {}".format(
                        msg.vid, s.name))
        # check if it is a new group, in the case it will need a new vrf
        if msg.group not in self.groups.keys():
            logger.info("group {} is not mapped to any switch VRFs, trying to select an available VRF"
                        .format(msg.group))
            selected_vrf_name = self.find_available_vrf(msg.group)
        else:
            logger.info("group {} is mapped to VRF {}")
            selected_vrf_name = self.groups[msg.group]
        # selecting switch and vrf and then applying
        selected_switch = self.get_switch_by_vrf(selected_vrf_name)
        selected_vrf = next(item for item in selected_switch.vrfs if item.name == selected_vrf_name)
        res = selected_switch.add_vlan_to_vrf(
            selected_vrf, SwitchRequestVlanL3Port.from_netvlanmsg(msg, vrf_name=selected_vrf_name))
        if res:
            self.group_table_to_db()
            selected_switch.update_info()  # FixMe: put it in a thread?
            selected_switch.to_db()
        else:
            raise ValueError('create_net_vlan failed due to switch-level problems')
        return res

    def delete_net_vlan(self, msg: NetVlanMsg):
        if 4000 < msg.vid < 4020:
            raise ValueError('Vlan id {} is reserved for firewall connectivity')
        if msg.group not in self.groups.keys():
            raise ValueError('Group {} not existing'.format(msg.group))
        logger.info("group {} is mapped to VRF {}")

        selected_vrf_name = self.groups[msg.group]
        selected_switch = self.get_switch_by_vrf(selected_vrf_name)
        res = selected_switch.del_vlan_to_vrf(selected_vrf_name, msg.vid)
        # res = selected_switch.del_vlan_itf(msg.vid)

        # check if VRF is now empty
        vrf = next(item for item in selected_switch.vrfs if item.name == selected_vrf_name)
        if len(vrf.ports) < 3:  # Note: the switch info has not yet been updated
            logger.info("group {} is empty (no vlan interfaces), freeing vrf {}".format(msg.group, selected_vrf_name))
            self.groups.pop(msg.group)
            self.group_table_to_db()
        # the configuration is changed on the device, retrieve the new config from the switch
        selected_switch.update_info()
        selected_switch.to_db()
        return res

    def modify_net_vlan(self, msg: NetVlanMsg):
        if self.delete_net_vlan(msg):
            return self.create_net_vlan(msg)
        return False

    def _get_port_switch_objs(self, msg: PortToNetVlansMsg) -> Tuple[Switch, PhyPort]:
        switch = next(item for item in self.switches if item.name == msg.switch)
        port = next(item for item in switch.phy_ports if item.name == msg.port or item.index == msg.port)
        return switch, port

    def add_port_vlan(self, msg: PortToNetVlansMsg):
        # note: this methods add incrementally trunk vlans on the specified port. Already exhisting Vlans will be
        # mantained.

        switch, port = self._get_port_switch_objs(msg)
        if len(msg.vids) < 1:
            raise ValueError("no vlan ids in message add_port")
        # check and apply link mode
        if port.mode != 'TRUNK':
            logger.warning("[{}] port {} of switch {} in {} mode. Setting TRUNK mode".format(
                msg.operation_id, port.name, switch.name, port.mode))
            switch.set_port_mode(port.name, 'TRUNK')
        # create vlan on the switch
        missing_vlan_on_switch = [item for item in msg.vids if item not in switch.vlans]
        if len(missing_vlan_on_switch) > 0:
            logger.info("[{}] Adding VLANs {} to switch {}".format(
                msg.operation_id, missing_vlan_on_switch, switch.name))
            switch.add_vlan(missing_vlan_on_switch)

            switch.update_info()
            switch.to_db()

        logger.info("[{}] Setting TRUNK VLANs {} on port {} of switch {}".format(
            msg.operation_id, msg.vids, port.name, switch.name
        ))
        for vlan_id in msg.vids:
            if vlan_id not in port.trunk_vlans:
                switch.add_vlan_to_port(vlan_id, port.name)
            else:
                logger.warning("[{}] VLAN {} already present in port {} of switch {}".format(
                    msg.operation_id, vlan_id, port.name, switch.name))
                
        switch.update_info()
        switch.to_db()

        # check if vlan connectivity among switches should be provided
        for vlan_id in msg.vids:
            if self.vlan_check_backbone_needed(vlan_id, switch.name, operation='add'):
                logger.info("[{}] backbone connectivity needed for VLAN {}".format(msg.operation_id, vlan_id))
                unconfigured_links, need_change = self.vlan_check_backbone_connectivity(vlan_id)
                if need_change:
                    for edge in unconfigured_links:
                        logger.info("[{}] adding VLAN {} to backbone link {}".format(msg.operation_id, vlan_id, edge))
                        backbone_switch, backbone_port = self.from_topology_link_to_switch_port(edge)
                        backbone_switch.add_vlan_to_port(vlan_id, backbone_port.name)

        switch.update_info()
        switch.to_db()

    def del_port_vlan(self, msg: PortToNetVlansMsg):
        # note: this methods delete incrementally trunk vlans on the specified port. Other Vlans will be mantained.

        switch, port = self._get_port_switch_objs(msg)
        if len(msg.vids) < 1:
            raise ValueError("no vlan ids in message add_port")

        logger.info("[{}] deleting TRUNK VLANs {} on port {} of switch {}".format(
            msg.operation_id, msg.vids, port.name, switch.name
        ))
        vlans_to_be_removed_from_trunk = [item for item in msg.vids if item in port.trunk_vlans]
        switch.del_vlan_to_port(vlans_to_be_removed_from_trunk, port.name)

        # check if vlan connectivity among switches should be removed
        for vlan_id in msg.vids:
            # is the port the only termination of this vlan in this switch?
            if len(self.vlan_terminations[vlan_id].server_ports[switch.name]) > 1:
                # no backbone modifications are needed, because the switch should be mantained in the Vlan
                continue
            else:
                # the vlan has no further termination in the switch, testing if backbone connectivity should be removed
                if not self.vlan_check_backbone_needed(vlan_id, switch.name, operation='del'):
                    logger.info("[{}] backbone connectivity not needed anymore for VLAN {}".format(
                        msg.operation_id, vlan_id))
                    backbone = self.get_backbone_topology()
                    for edge in backbone.edges(data=True):
                        bb_switch, bb_port = self.from_topology_link_to_switch_port(edge)
                        bb_switch.del_vlan_to_port([vlan_id], port.name)
                        if len(self.vlan_terminations[vlan_id].server_ports[bb_switch.name]) < 1 and \
                                self.vlan_terminations[vlan_id].vlan_interface and \
                                self.vlan_terminations[vlan_id].vlan_interface.switch_name != bb_switch.name:
                            bb_switch.del_vlan([vlan_id])

    def mod_port_vlan(self, msg: PortToNetVlansMsg):
        pass

    def get_switch_by_vrf(self, vrf_name):
        for s in self.switches:
            for v in s.vrfs:
                if v.name == vrf_name:
                    return s
        return None

    def get_switch_by_vlan_interface(self, vlan_id: int):
        for s in self.switches:
            for vlan_itf in s.vlan_l3_ports:
                if vlan_itf.vlan == vlan_id:
                    return s
        return None

    def group_table_to_db(self):
        _data = {'type': 'groups', 'groups': self.groups}
        if _db.exists_DB("groups", {'type': 'groups'}):
            _db.update_DB('groups', data=_data, filter={'type': 'groups'})
        else:
            _db.insert_DB('groups', data=_data)


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
                        self.net.onboard_switch(Device.model_validate(s_input.model_dump()))
                    case 'del_switch':
                        self.net.delete_switch(s_input.switch_name)
                    case 'del_net_vlan':
                        self.net.delete_net_vlan(s_input)
                    case 'add_net_vlan':
                        self.net.create_net_vlan(s_input)
                    case 'mod_net_vlan':
                        self.net.modify_net_vlan(s_input)
                    case 'add_port_vlan':
                        self.net.add_port_vlan(s_input)
                    case 'del_port_vlan':
                        self.net.del_port_vlan(s_input)
                    case 'mod_port_vlan':
                        self.net.mod_port_vlan(s_input)
                    case _:
                        raise ValueError('msg operation not found')
                s_input.update_status('Success')
            except Exception as e:
                s_input.update_status('Failed')
                logger.error(traceback.format_tb(e.__traceback__))
                logger.error(str(e))
            finally:
                self.queue.task_done()

    def get_topology(self) -> Dict:
        return self.net.get_topology_dict()

    def get_vrf_topology(self, vrf_name: str):
        return nx.convert.to_dict_of_dicts(self.net.get_l3_overlay_topology(vrf_name))
    
    def get_vlan_topology(self, vlan_id: int):
        return nx.convert.to_dict_of_dicts(self.net.get_vlan_overlay(vlan_id))

    def destroy(self):
        pass


net_worker = NetworkWorker()
