import os
import sys

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.routing.action_mask import ActionMask
from src.orchestrator.controller import SDWANController

def run_s1():
    print("=" * 60)
    print("RUNNING SCENARIO S1: Valid HR -> FIN Flow on Safe Network")
    print("=" * 60)
    
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))

    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm)
    agent = HeuristicAgent()
    controller = SDWANController(overlay, pdp, zm, bridge, agent)

    # Setup all nodes to have high trust scores initially
    pdp.use_avod_context = False
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]['cvss'] = 0.0
        
    for node in overlay.get_c().nodes():
        node_str = str(node)
        pdp.identity.set_score(node_str, 1.0)
        pdp.context.set_patch_factor(node_str, 1.0)
        pdp.behavior.set_score(node_str, 0.95)

    print("\n--- Requesting Flow VoIP from IT Node '14' to FIN Node '7' ---")
    
    import networkx as nx
    
    # Trace info
    C = overlay.get_c()
    print("Nodes and Zones:")
    for n in C.nodes():
        print(f"Node {n}: Zone {C.get_zone(n)}, Trust={pdp.get_trust_score(n, C.get_zone(n)):.4f}")
        
    struct_mask = bridge.get_struct_mask()
    print(f"\nStructural thresholds: theta_BN={bridge.theta_bn:.6f}, theta_MOD={bridge.theta_mod:.6f}")
    print("\nNode structural details:")
    for n in C.nodes():
        node_str = str(n)
        print(f"Node {n}: BN={bridge.bn_scores.get(node_str, 0.0):.6f}, MOD={bridge.mod_scores.get(node_str, 0.0):.1f}")
        
    node_masks = ActionMask.build_node_masks(C, pdp, '14', '7', struct_mask)
    print("\nNode Masks:")
    for n, m in node_masks.items():
        print(f"Node {n}: Mask={m} (Trust={pdp.get_trust_score(n, C.get_zone(n)):.4f}, Struct={struct_mask.get(n, True)})")

    E_f = ActionMask.get_feasible_edges(C, node_masks, zm)
    print(f"\nFeasible Edges (E_f): {E_f}")

    # Check physical paths in C (ignoring Z-score/trust)
    try:
        raw_paths = list(nx.all_simple_paths(C, '14', '7', cutoff=8))
        print(f"\nRaw Physical Paths in C (length cutoff=8): {raw_paths}")
    except Exception as e:
        print(f"Error finding physical paths: {e}")

    flow = controller.on_flow_request('14', '7', 'VoIP')
    
    print("\nResult:")
    print(flow)
    assert flow.status == "ACTIVE", f"Scenario S1 failed: Flow status is {flow.status}"
    print("\nSCENARIO S1 PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_s1()
