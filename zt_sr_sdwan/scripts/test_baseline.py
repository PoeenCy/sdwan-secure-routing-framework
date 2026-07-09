import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.routing.baselines import Baselines
from src.routing.action_mask import ActionMask
from src.routing.feasible_paths import FeasiblePaths

def main():
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))

    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm, k=0.1)
    agent = HeuristicAgent()

    pdp.use_avod_context = False
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]['cvss'] = 0.0
    for node in overlay.get_c().nodes():
        n_str = str(node)
        pdp.identity.set_score(n_str, 1.0)
        pdp.context.set_patch_factor(n_str, 1.0)
        pdp.behavior.set_score(n_str, 0.95)

    bridge.regenerate_g(overlay.get_c())
    C = overlay.get_c()

    # Step 1: Check node masks
    struct_mask = bridge.get_struct_mask()
    node_masks = ActionMask.build_node_masks(C, pdp, '14', '7', struct_mask)
    print("Node Masks:")
    for n, val in node_masks.items():
        print(f"Node {n}: Mask={val} (Trust={pdp.get_trust_score(n, C.get_zone(n)) >= pdp.get_theta_path('IT', 'FIN')}, Struct={struct_mask.get(n)})")

    # Step 2: Check feasible edges
    E_f = ActionMask.get_feasible_edges(C, node_masks, zm)
    print(f"Feasible Edges: {E_f}")

    # Step 3: Check paths
    paths = FeasiblePaths.find_paths('14', '7', E_f)
    print(f"Paths: {paths}")

if __name__ == "__main__":
    main()
