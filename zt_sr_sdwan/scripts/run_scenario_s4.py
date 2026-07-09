import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.orchestrator.controller import SDWANController

def run_s4():
    print("=" * 60)
    print("RUNNING SCENARIO S4: SLA QoS Delay Violation Re-route")
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

    print("\n--- Requesting VoIP Flow from IT '14' to FIN '7' (SLA = 150ms) ---")
    flow = controller.on_flow_request('14', '7', 'VoIP')
    print(f"Initial Flow: {flow}")
    assert flow.status == "ACTIVE"

    # Calculate initial path delay
    C = overlay.get_c()
    path = flow.path
    initial_delay = sum(C[path[i]][path[i+1]]['delay_ms'] for i in range(len(path) - 1))
    print(f"Initial Path Delay: {initial_delay:.2f} ms")

    # Increase delay of one of the edges on the path to violate VoIP SLA (150ms)
    u, v = path[0], path[1]
    print(f"\n--- Simulating delay spike on edge ({u}, {v}) to 200 ms ---")
    overlay.update_edge_qos(u, v, 'delay_ms', 200.0)

    print("\nResulting Flow Status:")
    print(flow)
    assert flow.status in ["REROUTED", "TERMINATED"], f"Scenario S4 failed: Flow status is {flow.status}"
    if flow.status == "REROUTED":
        new_delay = sum(C[flow.path[i]][flow.path[i+1]]['delay_ms'] for i in range(len(flow.path) - 1))
        print(f"Success! Flow rerouted to a path with delay: {new_delay:.2f} ms")
    else:
        print("Success! Flow terminated because no other path met the VoIP SLA.")
    print("SCENARIO S4 PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_s4()
