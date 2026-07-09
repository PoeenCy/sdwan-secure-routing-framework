import networkx as nx
import numpy as np

class GraphC(nx.DiGraph):
    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.node_zones = {}  # Cache node to zone mapping

    def set_node_zones(self, zone_mapping: dict):
        """
        Set zone for nodes.
        zone_mapping: dict of {zone_name: [node_ids]}
        """
        self.node_zones = {}
        for zone, nodes in zone_mapping.items():
            for node in nodes:
                # Force node ID to string to match graphml nodes
                self.node_zones[str(node)] = zone
                if self.has_node(str(node)):
                    self.nodes[str(node)]['zone'] = zone
                elif self.has_node(node):
                    self.nodes[node]['zone'] = zone
                    self.node_zones[node] = zone

    def get_zone(self, node) -> str:
        """Returns the zone of a node."""
        node_str = str(node)
        if node_str in self.node_zones:
            return self.node_zones[node_str]
        return self.nodes.get(node_str, {}).get('zone', 'Unknown')

    def assign_synthetic_qos(self, seed: int = 42):
        """Assign reproducible synthetic QoS parameters to each edge."""
        rng = np.random.default_rng(seed)
        for u, v in self.edges():
            # delay between 5ms and 40ms
            delay = float(rng.uniform(5, 40))
            # bandwidth between 50 and 500 Mbps
            bandwidth = float(rng.choice([50, 100, 150, 200, 300, 500]))
            # loss rate between 0.0001 and 0.005
            loss_rate = float(rng.uniform(0.0001, 0.005))
            
            self[u][v].update({
                'delay_ms': delay,
                'bandwidth_mbps': bandwidth,
                'loss_rate': loss_rate
            })
