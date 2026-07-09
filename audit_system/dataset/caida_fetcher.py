import csv
from pathlib import Path
from typing import List
from audit_system.models.dataset import TrafficData
import logging
import networkx as nx

logger = logging.getLogger(__name__)

class CAIDAFetcher:
    def __init__(self, use_mock: bool = False):
        self.data_path = Path("d:/SD_WAN_Secure_Routing/zt_sr_sdwan/data/traffic/caida.csv")

    def fetch_traffic_data(self, topology_edges: list, G: nx.Graph) -> List[TrafficData]:
        traffic_list = []
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Missing traffic dataset at {self.data_path}. Please run scripts/download_datasets.py first.")
            
        import pandas as pd
        df = pd.read_csv(self.data_path)
        
        # Sort by bandwidth to create QoS Tiers
        df = df.sort_values(by='bandwidth', ascending=False).reset_index(drop=True)
        total_rows = len(df)
        
        if total_rows < 3:
            raise ValueError("Traffic dataset is too small for QoS Tiering.")
            
        t1_split = int(total_rows * 0.3)
        t2_split = int(total_rows * 0.7)
        
        tier1 = df.iloc[:t1_split].to_dict('records')     # High BW
        tier2 = df.iloc[t1_split:t2_split].to_dict('records') # Med BW
        tier3 = df.iloc[t2_split:].to_dict('records')     # Low BW
        
        import random
        random.shuffle(tier1)
        random.shuffle(tier2)
        random.shuffle(tier3)
        
        def get_tier(u, v):
            # C.get_zone logic is usually external, but we can look at node attributes if available
            # If not, we fallback to node names or attributes in G
            z_u = G.nodes[u].get('zone', 'Unknown')
            z_v = G.nodes[v].get('zone', 'Unknown')
            
            if z_u == 'Core' and z_v == 'Core':
                return tier1
            elif 'Core' in [z_u, z_v] and any(z in [z_u, z_v] for z in ['DMZ', 'FIN']):
                return tier2
            else:
                return tier3

        for i, edge in enumerate(topology_edges):
            u, v = edge
            tier_bucket = get_tier(u, v)
            
            # Pop a row from the appropriate bucket, or fallback if empty
            if len(tier_bucket) > 0:
                row = tier_bucket.pop(0)
            elif len(tier2) > 0:
                row = tier2.pop(0)
            elif len(tier3) > 0:
                row = tier3.pop(0)
            else:
                row = tier1.pop(0) if len(tier1) > 0 else df.iloc[0].to_dict()
                
            traffic_list.append(TrafficData(
                edge_id=(str(u), str(v)),
                latency_ms=float(row['latency']),
                bandwidth_mbps=float(row['bandwidth']),
                packet_loss_rate=float(row['packet_loss']),
                jitter_ms=float(row['jitter']),
                source="CAIDA Real Data CSV"
            ))
            
        return traffic_list
