import networkx as nx

from ryu.base import app_manager
from ryu.cfg import CONF, StrOpt
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_0
from ryu.topology import event as topo_event

from spec import Spec


class TopoSpec(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopoSpec, self).__init__(*args, **kwargs)
        app_manager.require_app("ryu.topology.switches")
        CONF.register_opt(StrOpt("spec_path", default="spec/mininet.yml"))

        self.graph = nx.Graph()
        self.spec = Spec.from_yaml(CONF.spec_path)
        self._thread = hub.spawn_after(3, self._compare_spec)

    @set_ev_cls(topo_event.EventSwitchEnter, MAIN_DISPATCHER)
    def switch_enter_handler(self, ev):
        self.logger.debug("Switch %s added", ev.switch.dp.id)
        self.graph.add_node(ev.switch.dp.id)
        self._topology_updated()

    @set_ev_cls(topo_event.EventSwitchLeave, MAIN_DISPATCHER)
    def switch_leave_handler(self, ev):
        self.logger.debug("Switch %s added", ev.switch.dp.id)
        if ev.switch.dp.id in self.graph:
            self.graph.remove_node(ev.switch.dp.id)
        self._topology_updated()

    @set_ev_cls(topo_event.EventLinkAdd, MAIN_DISPATCHER)
    def link_add_handler(self, ev):
        link = ev.link
        self.logger.debug("Link %s-%s added", link.src.dpid, link.dst.dpid)
        self.graph.add_edge(link.src.dpid, link.dst.dpid)
        self._topology_updated()

    @set_ev_cls(topo_event.EventLinkDelete, MAIN_DISPATCHER)
    def link_delete_handler(self, ev):
        link = ev.link
        self.logger.debug("Link %s-%s removed", link.src.dpid, link.dst.dpid)
        if link.src.dpid in self.graph:
            if link.dst.dpid in self.graph[link.src.dpid]:
                self.graph.remove_edge(link.src.dpid, link.dst.dpid)
        self._topology_updated()

    @set_ev_cls(topo_event.EventHostAdd, MAIN_DISPATCHER)
    def host_add_handler(self, ev):
        self.logger.debug("Host %s added", ev.host.mac)
        self.graph.add_node(ev.host.mac)
        self.graph.add_edge(ev.host.mac, ev.host.port.dpid)
        self._topology_updated()

    def _compare_spec(self):
        # Take a snapshot of the current topology
        with hub.Semaphore():
            graph = self.graph.copy()

        self.logger.info("---------------------------------------------------")

        types = nx.get_node_attributes(self.spec.graph, "typ")
        names = nx.get_node_attributes(self.spec.graph, "name")

        node_errors = []
        for node in set(self.spec.graph) - set(graph):
            if types[node] == "switch":
                node_errors.append("Switch {0} not present"
                                   .format(names[node]))
            elif types[node] == "host":
                node_errors.append("Host {0} not present"
                                   .format(names[node]))

        edge_errors = []
        for edge in self.spec.graph.edges():
            if not graph.has_edge(*edge):
                edge_errors.append("Link {0} - {1} not present"
                                   .format(names[edge[0]], names[edge[1]]))

        if not node_errors and not edge_errors:
            self.logger.info("Topology conforms to spec")
        else:
            self.logger.error("Topology does not conform to spec")

            self.logger.error("Switches/Hosts:")
            for error in node_errors:
                self.logger.error("\t{0}".format(error))
            self.logger.error("\t{0} checked, {1} failures".format(
                nx.number_of_nodes(self.spec.graph), len(node_errors)))

            self.logger.error("Links:")
            for error in edge_errors:
                self.logger.error("    {0}".format(error))
            self.logger.error("\t{0} checked, {1} failures".format(
                nx.number_of_edges(self.spec.graph), len(edge_errors)))

    def _topology_updated(self):
        self.logger.debug("Topology change detected: waiting to converge")
        with hub.Semaphore():
            self._thread.cancel()
            self._thread = hub.spawn_after(3, self._compare_spec)
