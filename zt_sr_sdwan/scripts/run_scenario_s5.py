import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.orchestrator.controller import SDWANController

def run_s5():
    print("=" * 60)
    print("RUNNING SCENARIO S5: BN Outlier & Bounded Step 5c Mitigations")
    print("=" * 60)
    
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))

    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    # Set k=0.1 to make sure the highest BN nodes are identified as outliers
    bridge = CGBridge(zm, k=0.1)
    agent = HeuristicAgent()
    controller = SDWANController(overlay, pdp, zm, bridge, agent)

    C = overlay.get_c()
    
    print("\nInitial G robust parameters:")
    print(f"Mean BN: {bridge.mu_bn:.6f}, Std BN: {bridge.sigma_bn:.6f}, Threshold BN: {bridge.theta_bn:.6f}")

    # Find nodes above threshold
    outliers = [n for n in C.nodes() if bridge.bn_scores.get(str(n), 0.0) > bridge.theta_bn]
    print(f"Identified BN Outliers: {outliers}")

    print("\n--- Performing Step 5c Bounded Mitigation ---")
    cut_edges = bridge.perform_step_5c_mitigation(C, overlay)
    
    print(f"\nEdges cut during Step 5c: {cut_edges}")
    
    # Verify that no cut edge belongs to the business whitelist (Core or IT)
    for u, v in cut_edges:
        u_zone = C.get_zone(u)
        v_zone = C.get_zone(v)
        is_mandatory = (u_zone in ['Core', 'IT'] or v_zone in ['Core', 'IT'])
        assert not is_mandatory, f"Violation: Mandatory edge ({u}:{u_zone}, {v}:{v_zone}) was cut!"
        
    print("\nValidation Success: No mandatory (Core/IT) edges were cut by Step 5c mitigation.")
    print("SCENARIO S5 PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_s5()
