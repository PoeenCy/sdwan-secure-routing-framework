import os
import yaml
import networkx as nx
from src.models.graph_c import GraphC
from src.models.events import CUpdated

class OverlayManager:
    def __init__(self, config_dir: str, topology_path: str):
        self.config_dir = config_dir
        self.topology_path = topology_path
        self.listeners = []
        self.C = None
        self.zone_mapping = {}
        
        self.load_config()
        self.initialize_graph()

    def load_config(self):
        mapping_path = os.path.join(self.config_dir, "zone_mapping.yaml")
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            self.zone_mapping = data.get('zones', {})

    def initialize_graph(self):
        # Load topology from graphml
        raw_graph = nx.read_graphml(self.topology_path)
        
        # Convert to our GraphC structure (directed graph)
        # Note: raw_graph can be undirected or directed. We make sure it is a DiGraph.
        self.C = GraphC(raw_graph.to_directed())
        
        # Assign zones
        self.C.set_node_zones(self.zone_mapping)
        
        # Assign synthetic QoS values
        self.C.assign_synthetic_qos()

    def get_c(self) -> GraphC:
        return self.C

    def register_listener(self, listener):
        self.listeners.append(listener)

    def notify_listeners(self, event):
        for listener in self.listeners:
            listener(event)

    def update_edge_qos(self, u: str, v: str, attr: str, value: float):
        u_str, v_str = str(u), str(v)
        if self.C.has_edge(u_str, v_str):
            old_val = self.C[u_str][v_str].get(attr)
            self.C[u_str][v_str][attr] = value
            # Emit CUpdated event
            event = CUpdated((u_str, v_str), attr=attr, old_value=old_val, new_value=value)
            self.notify_listeners(event)
        else:
            print(f"Warning: Edge ({u_str}, {v_str}) does not exist in graph C.")

    def cut_edge(self, u: str, v: str):
        """Disables an edge by setting its bandwidth to 0 and delay to infinity."""
        u_str, v_str = str(u), str(v)
        if self.C.has_edge(u_str, v_str):
            # In our simulation, we keep the edge in NetworkX but set properties to represent a cut.
            # delay = infinity, bandwidth = 0.
            # This allows it to stay in the graph structure but be skipped by active routing filters.
            old_bw = self.C[u_str][v_str].get('bandwidth_mbps', 0.0)
            self.C[u_str][v_str]['bandwidth_mbps'] = 0.0
            self.C[u_str][v_str]['delay_ms'] = float('inf')
            self.C[u_str][v_str]['loss_rate'] = 1.0
            
            event = CUpdated((u_str, v_str), is_cut=True)
            self.notify_listeners(event)
        else:
            print(f"Warning: Edge ({u_str}, {v_str}) does not exist in graph C.")
            
    def restore_edge(self, u: str, v: str, delay_ms: float = 20.0, bandwidth_mbps: float = 100.0, loss_rate: float = 0.001):
        """Restores a cut edge to active state."""
        u_str, v_str = str(u), str(v)
        if self.C.has_edge(u_str, v_str):
            self.C[u_str][v_str]['bandwidth_mbps'] = bandwidth_mbps
            self.C[u_str][v_str]['delay_ms'] = delay_ms
            self.C[u_str][v_str]['loss_rate'] = loss_rate
            
            event = CUpdated((u_str, v_str), attr='status', old_value='cut', new_value='restored')
            self.notify_listeners(event)
