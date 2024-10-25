from typing import Dict, Tuple, Union, Optional

import networkx as nx
import networkx.classes.multigraph
from pydantic import ConfigDict, PrivateAttr, Field, RootModel
from models import PhyPort
from network.network_base import NetworkBase, logger
from switch import Switch


def compare_graph_edges(e1_src: str, e1_dst: str, e1_data: Dict[str, str], e2_src: str, e2_dst: str,
                        e2_data: Dict[str, str]) -> bool:
    return 'ports' in e1_data \
           and 'ports' in e2_data \
           and ((e1_src == e2_src and e1_dst == e2_dst) or (e1_src == e2_dst and e1_dst == e2_src)) \
           and e1_data['ports'] == e2_data['ports']


class GraphModel(RootModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    root: nx.classes.multigraph.MultiGraph = nx.MultiGraph()


class NetworkGraph(NetworkBase):

    graph: GraphModel = GraphModel()
    #Optional[nx.MultiGraph] = None  # possible FIXME: LLDP neighbor with SR-IOV enabled??

    def __init__(self):
        super().__init__()
        # self.graph = GraphModel()
        self.build_graph()

    def _from_topology_link_to_switch_port(self, edge: Tuple) -> Tuple[Switch, PhyPort]:
        switch = self.switches.get_switch_by_attribute('name', edge[0])
        port = next(item for item in switch.phy_ports if item.name == edge[2][switch.name])
        return switch, port

    def build_graph(self) -> None:
        for s in self.switches:
            self.graph.add_node(s.name, vlans=s.vlans, managed=True)

        for s in self.switches:
            for p in s.phy_ports:
                logger.debug("checking port {}".format(p.index))
                neigh_info = s.get_neighbors(p.index)
                if neigh_info:
                    edge = self._get_topology_link(neigh_info.neighbor, s.name, neigh_info.remote_interface, p.name)
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
                        self.graph.add_edge(
                            s.name,
                            neigh_info.neighbor,
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
        return self.graph.subgraph(self.switches.get_switch_names())

    def _get_topology_link(self, node1: str, node2: str, port1: str, port2: str) -> Union[Tuple[str, str, Dict], None]:
        return next((e for e in self.graph.edges(data=True)
                     if compare_graph_edges(*e, node1, node2, {node1: port1, node2: port2})), None)

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
