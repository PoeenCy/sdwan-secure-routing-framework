import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.orchestrator.controller import SDWANController

def run_s2():
    print("=" * 60)
    print("RUNNING SCENARIO S2: Behavior Drop & Trust Event Re-route")
    print("=" * 60)
    
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))

    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm)
    agent = HeuristicAgent()
    controller = SDWANController(overlay, pdp, zm, bridge, agent)

    # Initialize nodes as safe
    pdp.use_avod_context = False
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]['cvss'] = 0.0
        
    for node in overlay.get_c().nodes():
        node_str = str(node)
        pdp.identity.set_score(node_str, 1.0)
        pdp.context.set_patch_factor(node_str, 1.0)
        pdp.behavior.set_score(node_str, 0.95)

    print("\n--- Starting Flow VoIP from IT '14' to FIN '7' ---")
    flow = controller.on_flow_request('14', '7', 'VoIP')
    print(f"Initial Flow: {flow}")
    assert flow.status == "ACTIVE"

    # Identify intermediate node
    path = flow.path
    assert len(path) > 2, "Path is too short to test intermediate node compromise."
    compromised_node = path[1]  # The first hop after source
    print(f"\n--- Simulating behavior compromise at node '{compromised_node}' (Behavior drops to 0.3) ---")
    
    # Trigger trust update
    controller.trigger_trust_update(compromised_node, 'B', 0.3)

    print("\nResulting Flow Status:")
    print(flow)
    assert flow.status in ["REROUTED", "TERMINATED"], f"Scenario S2 failed: Flow status is {flow.status}"
    if flow.status == "REROUTED":
        print(f"Success! Flow was successfully rerouted to a secure path: {flow.path}")
    else:
        print("Success! Flow was terminated because no other secure path exists.")
    print("SCENARIO S2 PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_s2()
