import networkx as nx
from pathlib import Path
from audit_system.models.dataset import BehaviorData
import random

class DatasetMapper:
    @staticmethod
    def load_internetmci() -> nx.Graph:
        graphml_path = Path("d:/SD_WAN_Secure_Routing/zt_sr_sdwan/data/topologies/internetmci.graphml")
        if graphml_path.exists():
            G = nx.read_graphml(str(graphml_path))
        else:
            G = nx.complete_graph(19)
        
        zones = ["Core", "DMZ", "FIN", "HR", "IT"]
        for i, node in enumerate(G.nodes()):
            if 'zone' not in G.nodes[node]:
                G.nodes[node]['zone'] = zones[i % len(zones)]
        return G

    @staticmethod
    def generate_controlled_behavior(nodes: list[str]) -> list[BehaviorData]:
        behaviors = []
        for node in nodes:
            score = random.gauss(0.9, 0.05)
            score = max(0.0, min(1.0, score))
            behaviors.append(BehaviorData(
                node_id=str(node),
                timestamp=0.0,
                behavior_score=score,
                anomaly_type=None,
                source="synthetic_controlled"
            ))
        return behaviors
