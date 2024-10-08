from firewall.firewall_base import Firewall
from models import *
from network.nbi_msg_models import NetVlanMsg, PortToNetVlansMsg
from network_base import _db, logger
from network_graph import NetworkGraph
from network_models import *
from nbi_msg_models import AddPnfRequestMsg, DelPnfRequestMsg, AddRouteRequestMsg, DelRouteRequestMsg
from networker import NetworkWorker


class Network(NetworkGraph):
    # groups, pnfs, and vlan_terminations represent the intents of network impairments
    # they should be reinforced into switches and firewalls
    groups: NetworkGroups = NetworkGroups()
    pnfs: NetworkPnfs = NetworkPnfs()
    vlan_terminations: VlanTerminationList = VlanTerminationList()

    # TODO: ask synch for groups to the metalcl
    # registration of metalcl
    # config set by metalcl
    # pnf
    # rotte statiche

    def __init__(self):
        super().__init__()
        self.build_vlan_data()

    def _check_vlan_backbone_needed(self, vid: int, switch_name: str = None,
                                    operation: BackboneVlanOps = BackboneVlanOps.as_is) -> bool:
        # check if the vlan can be configured only one switch, or if it should be carried by the backbone network
        vlan_termination_item = self.vlan_terminations.get_by_vid(vid)
        if not vlan_termination_item:
            return False

        if operation == BackboneVlanOps.add:
            return len(vlan_termination_item.get_switch_names().union(set(switch_name))) > 1
        elif operation == BackboneVlanOps.delete:
            return len(vlan_termination_item.get_switch_names().difference(set(switch_name))) < 1
        else:  # operation ==  as_is
            return len(vlan_termination_item.get_switch_names()) > 1

    def _get_backbone_links_for_vlan_connectivity(self, vlan_id: int) -> Tuple[List[Tuple], bool]:
        # this function selects the backbone links where the vlan is missing for full backbone connectivity
        backbone = self.get_backbone_topology()
        link_missing = []
        for edge in backbone.edges(data=True):
            if vlan_id not in edge[2]['vlans']:
                link_missing.append(edge)
        return link_missing, len(link_missing) > 0

    def build_vlan_data(self):
        managed_switch_names = [item.name for item in self.switches]
        for _s in self.switches:
            for vid in _s.vlans:
                self.vlan_terminations.set_vlan_interface(switch=_s, vid=vid)
                self.vlan_terminations.set_vlan_server(switch=_s, vid=vid, managed_switch_names=managed_switch_names)
                self.vlan_terminations.get_by_vid(vid).topology = self.get_vlan_overlay(vid, only_managed_nodes=True)

        all_vlans = set()
        for _s in self.switches:
            all_vlans.update(_s.vlans)
        logger.info("used vlans {}".format(self.vlan_terminations.get_all_vids()))
        logger.info(" all vlans {}".format(all_vlans))
        logger.info("configured but unused vlans {}".format(all_vlans - set(self.vlan_terminations.get_all_vids())))

    def onboard_switch(self, node: Device):
        new_switch = Switch.create(node)
        new_switch.to_db()
        if new_switch.state != 'ready':
            logger.warn('switch {} is in {} state'.format(new_switch.name, new_switch.state))
        self.switches.append(new_switch)
        self.build_graph()

    def onboard_firewall(self, node: Device):
        if self.firewall:
            raise ValueError("Firewall already declared. Please remove the current firewall before adding a new one")
        new_firewall = Firewall.create(node)
        new_firewall.to_db()
        if new_firewall.state != 'ready':
            logger.warn('switch {} is in {} state'.format(new_firewall.name, new_firewall.state))
        self.firewall = new_firewall
        self.build_graph()

    def delete_switch(self, switch_name: str):
        self.switches.delete(switch_name)
        self.build_graph()

    def delete_firewall(self):
        self.firewall.destroy()
        self.firewall = None
        self.build_graph()

    def configure_new_vrf(self, expected_vrf: VrfRequest, vid: int, subnet: IPv4Network, group_name: str):
        self.groups.add(name=group_name, vrf_name=expected_vrf.name)
        # Step 1: crete the vrf
        self.create_vrf(expected_vrf.name)

        # Step 2: add the vlan termination in the switch connecting the firewall
        self.add_port_vlan(
            PortToNetVlansMsg(
                fqdn=self.firewall.name,
                interface=self.config.firewall_uplink_vlan_port,
                switch=self.config.firewall_uplink_neighbor.neighbor,
                port=self.config.firewall_uplink_neighbor.remote_interface,
                vids=[vid]
            )
        )
        # Step 3: create the vlan interface on the vrf switch, and attach it to the VRF
        vlan_itf_switch_request = SwitchRequestVlanL3Port(
            vlan=vid,
            ipaddress=str(subnet[1]),
            cidr=str(subnet[1]),
            vrf=expected_vrf.name,
            description='uplink for {}'.format(group_name)
        )
        # Step 4: reread the configuration to retrieve the vrf to be used
        self.vrf_switch.retrieve_info()
        real_vrf = self.vrf_switch.get_vrf_by_name(expected_vrf.name)
        self.vrf_switch.add_vlan_to_vrf(real_vrf, vlan_itf_switch_request)
        # Step 5: create the vlan interface on the firewall
        vlan_itf_firewall_request = FirewallRequestL3Port(
            vlan=vid,
            intf=self.config.firewall_uplink_vlan_port,
            ipaddress=str(subnet[2]),
            cidr=str(subnet[1]),
            vrf='default',  # no vrf support at firewall
            description='uplink for {}'.format(group_name)
        )
        default_fw_vrf = next(item for item in self.firewall.vrfs if item.name == 'default')
        self.firewall.add_l3port_to_vrf(default_fw_vrf, vlan_itf_firewall_request)
        self.firewall._add_l3port_to_group(vlan_itf_firewall_request, self.config.firewall_port_group)

        # Step 6: if the switch hosting the vrf, and the one connecting the firewall are different, we need
        #         backbone connectivity
        if self.vrf_switch.name != self.config.firewall_uplink_neighbor.neighbor:
            self._set_vlan_backbone_connectivity(vid)

        # Step 7: add BGP peering between the VRF and the firewall

        self.vrf_switch.set_vrf_routing(real_vrf, expected_vrf)
        fw_bgp_neighbor_request = BGPNeighbor(
            ip=vlan_itf_switch_request.ipaddress,
            remote_as=expected_vrf.protocols.bgp.as_number,
            description=group_name,
            ip_source=vlan_itf_firewall_request.ipaddress
        )
        self.firewall.add_bgp_peering(fw_bgp_neighbor_request)

    def find_available_vrf(self, group_name: str) -> str:
        for v in self.vrf_switch.vrfs:
            if v.name not in self.groups.get_names_of_reserved_vrfs() and v.name[:4] == 'proj' and len(v.ports) < 2:
                logger.info("VRF {} selected for group {}".format(v.name, group_name))
                self.groups.add(group_name, vrf_name=v.name)
                return v.name

        if self._check_fw_vrf_management():
            # Step 0: reserve vid and subnet for the uplink and crete and expected VRF object
            vid, subnet = self.status.reserve_uplink()
            expected_vrf = VrfRequest(
                name=group_name,
                description="vrf for {}".format(group_name),
                protocols=RoutingProtocols(
                    bgp=BGPRoutingProtocol(
                        as_number=self.config.as_number,
                        router_id=str(subnet[1]),
                        neighbors=[BGPNeighbor(
                            ip=IPvAnyAddress(str(subnet[1])),
                            remote_as=self.config.as_number,
                            description="uplink fot vrf {}".format(group_name)
                        )],
                        address_families=[BGPAddressFamily(
                            protocol="ipv4",
                            protocol_type="unicast",
                            redistribute=[BGPRedistribute.static, BGPRedistribute.connected]
                        )]
                    )
                )
            )
            self.configure_new_vrf(expected_vrf, vid, subnet, group_name)
        else:
            raise ValueError('no VRFs available')

    def create_net_vlan(self, msg: NetVlanMsg):
        # Vlan interfaces should be unique over all the network
        if self.get_switch_by_vlan_interface(msg.vid):
            logger.error("found already existing vlan interface in create_net_vlan")
            raise ValueError("Vlan interface for vlan id {} already existing".format(msg.vid))
        # check if it is a new group, in the case it will need a new vrf
        if self.groups.exist(msg.group):
            logger.info("group {} is mapped to VRF {}")
            selected_vrf_name = self.groups[msg.group]
        else:
            logger.info("group {} is not mapped to any switch VRFs, trying to select an available VRF"
                    .format(msg.group))
            selected_vrf_name = self.find_available_vrf(msg.group)
        # selecting switch and vrf and then applying
        selected_vrf = self.vrf_switch.get_vrf_by_name(selected_vrf_name)
        res = self.vrf_switch.add_vlan_to_vrf(
            selected_vrf, SwitchRequestVlanL3Port.from_netvlanmsg(msg, vrf_name=selected_vrf_name))
        if res:
            self.vrf_switch.update_info()  # FixMe: put it in a thread?
        else:
            raise ValueError('create_net_vlan failed')
        return res

    def delete_net_vlan(self, msg: NetVlanMsg):
        group = self.groups.get(msg.group)
        if not group:
            raise ValueError('Group {} not existing'.format(msg.group))
        logger.info("group {} is mapped to VRF {}")
        switch, vrf = self.switches.get_attribute_by_selector('vrf', 'name', group.vrf_name)

        res = switch.del_vlan_itf(msg.vid)
        # check if VRF is now empty
        if len(vrf.ports) < 3:  # Note: the switch info has not yet been updated
            logger.info("group {} is empty (no vlan interfaces), freeing vrf {}".format(msg.group, vrf.name))
            self.groups.pop(msg.group)
        # the configuration is changed on the device, retrieve the new config from the switch
        switch.update_info()
        return res

    def modify_net_vlan(self, msg: NetVlanMsg):
        if self.delete_net_vlan(msg):
            return self.create_net_vlan(msg)
        return False

    def assert_net_vlan(self, msg: NetVlanMsg) -> bool:
        if msg.operation == "add_net_vlan":
            group = self.groups.get(msg.group)
            if not group:
                logger.warn("group {} not existing".format(msg.group))
                return False

            switch, vrf = self.switches.get_attribute_by_selector('vrf', 'name', group.vrf_name)
            if not switch or not vrf:
                logger.warn("vrf {} not found".format(group.vrf_name))
                return False

            l3intf = next((item for item in vrf.ports if item.vlan == int(msg.vid)), None)
            if not l3intf:
                logger.warn("interface with vlan {} on vrf {} not found".format(msg.vid, group.vrf_name))
                return False

            if l3intf.ipaddress == msg.ipaddress and l3intf.cidr == msg.cidr:
                return True
            else:
                logger.warn("interface with vlan {} on vrf {} does not have ip address {}".format(
                    msg.vid, group.vrf_name, msg.ipaddress))
                return False
        elif msg.operation == "del_net_vlan":
            group = self.groups.get(msg.group)
            if not group:
                logger.info("group {} has been successfully deleted".format(msg.group))
                # check if any vrf has a vlan interface with that vid
                vlan_itf = next((item for item in self.vrf_switch.vlan_l3_ports if item.vlan == int(msg.vid)), None)
                if vlan_itf:
                    logger.error('a vlan interface with vlan id {} is still existing')
                    return False
                return True
            else:
                switch, vrf = self.switches.get_attribute_by_selector('vrf', 'name', group.vrf_name)
                if not switch or not vrf:
                    logger.warn("vrf {} not found".format(group.vrf_name))
                    return False
                vlan_itf = next((item for item in vrf.ports if item.vlan == int(msg.vid)), None)
                if vlan_itf:
                    logger.error('a vlan interface with vlan id {} is still existing in vrf {}'.format(
                        msg.vid, group.vrf_name))
                    return False
                return True

    def add_port_vlan(self, msg: PortToNetVlansMsg):
            # note: this method adds incrementally trunk vlans on the specified port.
            # Already existing Vlans will be mantained.

            if len(msg.vids) < 1:
                raise ValueError("no vlan ids in message add_port")

            node, port = self._get_port_node_objs(msg)

            # check and apply link mode
            if isinstance(node, Switch):
                node.set_port_mode(port.name, LinkModes.trunk)

            # create vlan on the switch
            node.add_vlan(msg.vids)

            logger.info("[{}] Setting TRUNK VLANs {} on port {} of switch {}".format(
                msg.operation_id, msg.vids, port.name, node.name
            ))

            for vlan_id in msg.vids:
                node.add_vlan_to_port(vlan_id, port.name)

            # check if vlan connectivity among switches should be provided
            for vlan_id in msg.vids:
                if self._check_vlan_backbone_needed(vlan_id, node.name, operation=BackboneVlanOps.add):
                    logger.info("[{}] backbone connectivity needed for VLAN {}".format(
                        msg.operation_id, vlan_id))
                    self._set_vlan_backbone_connectivity(vlan_id)

    def _set_vlan_backbone_connectivity(self, vlan_id: int):
        unconfigured_links, need_change = self._get_backbone_links_for_vlan_connectivity(vlan_id)
        if need_change:
            for edge in unconfigured_links:
                logger.info("adding VLAN {} to backbone link {}".format(vlan_id, edge))
                backbone_switch, backbone_port = self._from_topology_link_to_switch_port(edge)
                backbone_switch.add_vlan_to_port(vlan_id, backbone_port.name)

    def del_port_vlan(self, msg: PortToNetVlansMsg):
        # note: this method incrementally deletes trunk vlans on the specified port.
        # Other Vlans will be maintained.

        switch, port = self._get_port_node_objs(msg)
        if len(msg.vids) < 1:
            raise ValueError("no vlan ids in message add_port")

        logger.info("[{}] deleting TRUNK VLANs {} on port {} of switch {}".format(
            msg.operation_id, msg.vids, port.name, switch.name
        ))
        vlans_to_be_removed_from_trunk = [item for item in msg.vids if item in port.trunk_vlans]
        switch.del_vlan_to_port(vlans_to_be_removed_from_trunk, port.name)

        # check if vlan connectivity among switches should be removed
        for vlan_id in msg.vids:
            vlan_term = self.vlan_terminations.get_by_vid(vlan_id)
            # is the port the only termination of this vlan in this switch?
            if len(vlan_term.get_tagged_ports_in_switch(switch.name)) > 1:
                # no backbone modifications are needed, because the switch should be mantained in the Vlan
                continue
            else:
                # the vlan has no further termination in the switch, testing if backbone connectivity should be removed
                if not self._check_vlan_backbone_needed(vlan_id, switch.name, operation=BackboneVlanOps.delete):
                    logger.info("[{}] backbone connectivity not needed anymore for VLAN {}".format(
                        msg.operation_id, vlan_id))
                    backbone = self.get_backbone_topology()
                    for edge in backbone.edges(data=True):
                        bb_switch, bb_port = self._from_topology_link_to_switch_port(edge)
                        bb_switch.del_vlan_to_port([vlan_id], port.name)

                        if vlan_term.check_vlan_need_on_switch(bb_switch.name):
                            bb_switch.del_vlan([vlan_id])

    def mod_port_vlan(self, msg: PortToNetVlansMsg):
        pass

    def assert_port_vlan(self, msg: PortToNetVlansMsg) -> bool:
        if msg.operation == 'add_port_vlan':
            switch, port = self._get_port_node_objs(msg)
            missing_vlans = []
            for vlan_id in msg.vids:
                if vlan_id not in port.trunk_vlans or vlan_id != port.access_vlan:
                    missing_vlans.append(vlan_id)
            if len(missing_vlans) > 0:
                logger.error("Vlans {} missing on port {} of switch {}".format(
                    missing_vlans, port.name, switch.name))
                # TODO: add check on backbone
                return False
            return True

        elif msg.operation == 'del_port_vlan':
            switch, port = self._get_port_node_objs(msg)
            not_deleted_vlans = []
            for vlan_id in msg.vids:
                if vlan_id in port.trunk_vlans or vlan_id == port.access_vlan:
                    not_deleted_vlans.append(vlan_id)
                if len(not_deleted_vlans) > 0:
                    logger.error("Vlans {} still configured on port {} of switch {}".format(
                        not_deleted_vlans, port.name, switch.name))
                    # TODO: add check on backbone
                    return False
                return True
        else:
            logger.warn("Config assert not yet supported for msg type {}".format(msg.operation))
            return True

    def add_pnf(self, msg: AddPnfRequestMsg):
        self.create_vrf(vrf_name=msg.name)
        # update info? otherwise the vrf will not exist in the switch obj
        self.vrf_switch.update_info()
        if not msg.vid:
            msg.vid = self.status.get_and_reserve_pnf_vlan()
        else:
            self.status.reserve_vlan(msg.vid)
        if not msg.ip_address:
            msg.ip_address = self.status.get_and_reserve_pnf_ip_address()
        else:
            msg.ip_address = self.status.reserve_ip_address(msg.ip_address)

        msg = SwitchRequestVlanL3Port(
            vlan=msg.vid,
            ipaddress=IPvAnyInterface(msg.gateway),
            cidr=IPvAnyNetwork(msg.ip_address),
            vrf=msg.name,
            description= 'vrf for pnf {}'.format(msg.name)
        )
        vrf = self.vrf_switch.get_vrf_by_name(msg.name)
        self.vrf_switch.add_vlan_to_vrf(vrf, msg)
        #FixMe abilitare bgp!!!
        self.bind_vrf(msg.name, self.config.pnf_merging_vrf_name)
        port_msg = PortToNetVlansMsg(
            fqdn=msg.name,
            interface='',
            node=msg.switch_name,
            port=msg.switch_port,
            vids=msg.vids
        )
        self.add_port_vlan(port_msg)


    def del_pnf(self, msg: DelPnfRequestMsg):
        pass

    def bind_vrf(self, vrf1_name: str, vrf2_name: str):
        self.vrf_switch.bind_vrf(vrf1_name, vrf2_name)

    def unbind_vrf(self, vrf1_name: str, vrf2_name: str):
        self.vrf_switch.unbind_vrf(vrf1_name, vrf2_name)

    def add_route_to_vrf(self, msg: AddRouteRequestMsg):
        group = self.groups.get(msg.group)
        if not group:
            raise ValueError("group {} not found".format(msg.group))
        vrf = self.vrf_switch.get_vrf_by_name(group.vrf_name)
        if not vrf:
            raise ValueError("vrf {} not found".format(group.vrf_name))
        self.vrf_switch.add_route(vrf, msg.to_IpV4Route())

    def del_route_to_vrf(self, msg: DelRouteRequestMsg):
        group = self.groups.get(msg.group)
        if not group:
            raise ValueError("group {} not found".format(msg.group))
        vrf = self.vrf_switch.get_vrf_by_name(group.vrf_name)
        if not vrf:
            raise ValueError("vrf {} not found".format(group.vrf_name))
        self.vrf_switch.del_route(vrf, msg.to_IpV4Route())


    def get_vrf_bindings(self, vrf_name: str):
        vrf =  next((item for item in self.vrf_switch.vrfs if item.name == vrf_name), None)
        if vrf is None:
            raise ValueError("vrf {} not found".format(vrf_name))
        # Check: not sure if the list contains route descriptors or vrf names
        return vrf.rd_import

    def group_table_to_db(self):
        _data = {'type': 'groups', 'groups': self.groups}
        if _db.exists_DB("groups", {'type': 'groups'}):
            _db.update_DB('groups', data=_data, filter={'type': 'groups'})
        else:
            _db.insert_DB('groups', data=_data)


net_worker = NetworkWorker()
