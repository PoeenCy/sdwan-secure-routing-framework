import sys
import copy
import random
import os
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path

# Setup paths
sys.path.insert(0, 'd:/SD_WAN_Secure_Routing')
from audit_system.orchestrator.controller import Orchestrator
from src.models.graph_c import GraphC
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.baselines import Baselines
from src.routing.action_mask import ActionMask

out_dir = Path('d:/SD_WAN_Secure_Routing/zt_sr_sdwan/results/visualizations')
out_dir.mkdir(parents=True, exist_ok=True)

o = Orchestrator(Path('d:/SD_WAN_Secure_Routing/.kiro/specs/zt-sr-audit-refactor'), Path('d:/SD_WAN_Secure_Routing/zt_sr_sdwan'), Path('d:/SD_WAN_Secure_Routing/zt_sr_sdwan/results'))
dataset = o.execute_phase_2_dataset()

config_dir = Path('d:/SD_WAN_Secure_Routing/zt_sr_sdwan/config')
pdp = PDP(str(config_dir))
zone_matrix = ZoneMatrix(str(config_dir))
bridge = CGBridge(zone_matrix)

C = GraphC(dataset.topology)
C.set_node_zones({n: dataset.topology.nodes[n].get('zone', 'Core') for n in C.nodes()})

for t in dataset.traffic:
    u, v = t.edge_id
    if C.has_edge(str(u), str(v)):
        C[str(u)][str(v)]['delay_ms'] = t.latency_ms
        C[str(u)][str(v)]['bandwidth_mbps'] = t.bandwidth_mbps

# Clear CVSS first
for node_id in C.nodes():
    C.nodes[node_id]['cvss'] = 0.0

# Find s and d deterministically
s, d = None, None
nodes = list(C.nodes())
random.seed(42)
random.shuffle(nodes)
for i in range(len(nodes)):
    for j in range(i+1, len(nodes)):
        paths = list(nx.all_simple_paths(C, nodes[i], nodes[j], cutoff=5))
        if len(paths) >= 2:
            path = Baselines.seg_routing(nodes[i], nodes[j], C, zone_matrix)
            if path is not None:
                s, d = nodes[i], nodes[j]
                break
    if s is not None:
        break

if s is None:
    s, d = nodes[0], nodes[1]

pos = nx.spring_layout(C, seed=42)

def draw_graph(G, path=None, title="", filename="", node_masks=None):
    plt.figure(figsize=(10, 8))
    node_colors = []
    
    # Use standard node list from original C to keep positions consistent
    nodelist = list(C.nodes())
    
    for n in nodelist:
        if not G.has_node(n):
            node_colors.append('whitesmoke') # Removed node
        elif G.nodes[n].get('cvss', 0.0) >= 7.0:
            node_colors.append('red') # Infected
        elif n == s:
            node_colors.append('lightgreen') # Source
        elif n == d:
            node_colors.append('lightgreen') # Dest
        else:
            node_colors.append('skyblue')
            
    nx.draw_networkx_nodes(G, pos, nodelist=nodelist, node_color=node_colors, node_size=800, alpha=0.9)
    
    # Draw edges
    edges = list(G.edges())
    nx.draw_networkx_edges(G, pos, edgelist=edges, edge_color='gray', arrows=True, arrowsize=15, alpha=0.5)
    
    # Labels
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
    
    if path:
        path_edges = list(zip(path, path[1:]))
        nx.draw_networkx_edges(G, pos, edgelist=path_edges, edge_color='orange', width=4, arrows=True, arrowsize=20)
        # Highlight path nodes
        path_colors = []
        for n in path:
            if G.nodes[n].get('cvss', 0.0) >= 7.0:
                path_colors.append('red')
            else:
                path_colors.append('yellow')
        nx.draw_networkx_nodes(G, pos, nodelist=path, node_color=path_colors, node_size=900)
        
    plt.title(title, fontsize=16)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(out_dir / filename, dpi=150)
    plt.close()

# 1. Normal State
sp_path = Baselines.sp_routing(s, d, C)
draw_graph(C, path=sp_path, title=f"Bước 1: Mạng bình thường (SP-Routing chọn đường: {sp_path})", filename="step1_normal.png")

# 2. Compromised State
C_scen = copy.deepcopy(C)
infected_node = None
if sp_path and len(sp_path) >= 3:
    infected_node = sp_path[1]
    C_scen.nodes[infected_node]['cvss'] = 9.8
    print(f"Infected Node: {infected_node}")

draw_graph(C_scen, path=sp_path, title=f"Bước 2: Nút {infected_node} bị tấn công mã độc (Đỏ)\nSP-Routing vẫn mù quáng đâm vào Nút Đỏ", filename="step2_compromised.png")

# 3. Action Masking
struct_mask = bridge.get_struct_mask()
node_masks = ActionMask.build_node_masks(C_scen, pdp, str(s), str(d), struct_mask)
E_f = ActionMask.get_feasible_edges(C_scen, node_masks, zone_matrix)

C_masked = nx.DiGraph()
for node in C_scen.nodes():
    if node_masks.get(str(node), False):
        C_masked.add_node(node, **C_scen.nodes[node])

for u, v in E_f:
    # E_f has strings, C has int/str mix based on generation
    # But C nodes here are strings!
    if C_masked.has_node(u) and C_masked.has_node(v):
        C_masked.add_edge(u, v)

draw_graph(C_masked, path=None, title="Bước 3: Lớp 1 - Action Masking\n(Cách ly Nút Đỏ & Cắt các đường vi phạm Zone/Trust)", filename="step3_masked.png")

# 4. ZT-SR-DRL
zt_path = Baselines.zt_sr_drl(s, d, C_scen, pdp, zone_matrix, bridge, None)
draw_graph(C_scen, path=zt_path, title=f"Bước 4: ZT-SR-DRL (Lớp 2)\nTìm ra đường vòng an toàn: {zt_path}", filename="step4_drl.png")

print("Visualization saved to:", out_dir)
