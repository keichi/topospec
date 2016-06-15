import networkx as nx

import yaml


class SpecFormatError(Exception):
    pass


class Spec(object):
    def __init__(self, d):
        super(Spec, self).__init__()
        self.graph = nx.Graph()
        self._load_switches(d)
        self._load_hosts(d)
        self._load_links(d)
        self.graph = nx.freeze(self.graph)
        self._check_sanity()

    def _load_switches(self, d):
        switches = d.get("switches", [])
        if not isinstance(switches, list):
            raise SpecFormatError("switches is not a list")
        for switch in switches:
            if "name" not in switch:
                raise SpecFormatError("switch does not have a name")
            if "dpid" not in switch:
                raise SpecFormatError("switch does not have a dpid")
            if switch["name"] in self.graph:
                raise SpecFormatError("duplicate switch {0}"
                                      .format(switch["name"]))

            self.graph.add_node(switch["dpid"], typ="switch",
                                name=switch["name"])

    def _load_hosts(self, d):
        hosts = d.get("hosts", [])
        if not isinstance(hosts, list):
            raise SpecFormatError("hosts is not a list")
        for host in hosts:
            if "name" not in host:
                raise SpecFormatError("host does not have a name")
            if "mac" not in host:
                raise SpecFormatError("host does not have a MAC address")
            if host["name"] in self.graph:
                raise SpecFormatError("duplicate host {0}"
                                      .format(host["name"]))

            self.graph.add_node(host["mac"], typ="host", name=host.get("name"),
                                ip=host.get("ip"))

    def _load_links(self, d):
        links = d.get("links", [])
        if not isinstance(links, list) and not isinstance(links, dict):
            raise SpecFormatError("links is not a list nor a dictionary")
        self._traverse_load_links(links)

    def _traverse_load_links(self, d):
        if isinstance(d, dict):
            for group in d.values():
                self._traverse_load_links(group)
        elif isinstance(d, list):
            for link in d:
                if "from" not in link:
                    raise SpecFormatError("link does not have a 'from'")
                if "to" not in link:
                    raise SpecFormatError("link does not have a 'to'")

                from_node = self._resolve_name_or_node(link["from"])
                if not from_node:
                    raise SpecFormatError("'from' node {0} does not exist"
                                          .format(link["from"]))
                to_node = self._resolve_name_or_node(link["to"])
                if not to_node:
                    raise SpecFormatError("'to' node {0} does not exist"
                                          .format(link["to"]))

                self.graph.add_edge(from_node, to_node)

    def _resolve_name_or_node(self, name_or_node):
        if name_or_node in self.graph:
            return name_or_node
        for (node, data) in self.graph.nodes(data=True):
            if data.get("name") == name_or_node:
                return node
        return None

    def _check_sanity(self):
        if not nx.is_connected(self.graph):
            raise SpecFormatError("Topology is not connected")

    @classmethod
    def from_yaml(cls, filename):
        with open(filename, "r") as f:
            d = yaml.load(f)
            return cls(d)

if __name__ == "__main__":
    spec = Spec.from_yaml("spec.yml")
