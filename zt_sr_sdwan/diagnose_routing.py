import sys
from pathlib import Path
import random
sys.path.insert(0, 'd:/SD_WAN_Secure_Routing')
from audit_system.orchestrator.controller import Orchestrator
from audit_system.deployment.baseline_runner import BaselineRunner
from src.routing.baselines import Baselines
from src.models.graph_c import GraphC
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.drl_agent import train_or_load_agent
from src.routing.drl_env import ZTEnv

o = Orchestrator(Path('d:/SD_WAN_Secure_Routing/.kiro/specs/zt-sr-audit-refactor'), Path('d:/SD_WAN_Secure_Routing/zt_sr_sdwan'), Path('d:/SD_WAN_Secure_Routing/zt_sr_sdwan/results'))
dataset = o.execute_phase_2_dataset()

config_dir = Path('d:/SD_WAN_Secure_Routing/zt_sr_sdwan/config')
pdp = PDP(str(config_dir))
zone_matrix = ZoneMatrix(str(config_dir))
bridge = CGBridge(zone_matrix)

C = GraphC(dataset.topology)
C.set_node_zones({n: dataset.topology.nodes[n].get('zone', 'Core') for n in C.nodes()})

for node_id in C.nodes():
    if random.random() < 0.2:
        C.nodes[node_id]['cvss'] = random.uniform(7.0, 9.8)
    else:
        C.nodes[node_id]['cvss'] = 0.0

import networkx as nx
s, d = None, None
nodes = list(C.nodes())
random.seed(42)
random.shuffle(nodes)
for i in range(len(nodes)):
    for j in range(i+1, len(nodes)):
        if nx.has_path(C, nodes[i], nodes[j]):
            path = Baselines.seg_routing(nodes[i], nodes[j], C, zone_matrix)
            if path is not None:
                s, d = nodes[i], nodes[j]
                break
    if s is not None:
        break

print(f"Selected Source: {s}, Dest: {d}")

# Why does ZT-Routing fail?
print("--- ZT-Routing Diagnostics ---")
zone_s = C.get_zone(s)
zone_d = C.get_zone(d)
theta_path = pdp.get_theta_path(zone_s, zone_d, C)
print(f"Theta Path: {theta_path}")

valid_nodes = 0
for n in C.nodes():
    t_n = pdp.get_trust_score(str(n), C.get_zone(str(n)), C)
    if t_n >= theta_path:
        valid_nodes += 1

print(f"Total nodes: {len(C.nodes())}, Valid nodes passing Theta: {valid_nodes}")

path_zt = Baselines.zt_routing(s, d, C, pdp)
print(f"ZT-Routing Path: {path_zt}")

# Why does ZT-SR-DRL fail?
print("--- ZT-SR-DRL Diagnostics ---")
from src.routing.action_mask import ActionMask
struct_mask = bridge.get_struct_mask()
node_masks = ActionMask.build_node_masks(C, pdp, str(s), str(d), struct_mask)
E_f = ActionMask.get_feasible_edges(C, node_masks, zone_matrix)
print(f"Feasible Edges (E_f): {len(E_f)} out of {len(C.edges())}")

env = ZTEnv(C, pdp, str(s), str(d), E_f)
print(f"Valid successors from source ({s}): {env._get_valid_actions()}")

agent = train_or_load_agent(env, force_retrain=False)
obs, _ = env.reset()
action, _ = agent.predict(obs)
print(f"Agent First Action from {s}: {action}")
