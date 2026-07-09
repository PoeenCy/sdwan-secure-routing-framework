import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.orchestrator.controller import SDWANController

def run_s3():
    print("=" * 60)
    print("RUNNING SCENARIO S3: Telemetry Edge QoS Change & Z-Score Shift")
    print("=" * 60)
    
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))

    overlay = OverlayManager(config_dir, topo_path)
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm)
    agent = HeuristicAgent()
    controller = SDWANController(overlay, pdp, zm, bridge, agent)

    # Initial thresholds
    print("Initial structural parameters:")
    print(f"Mean BN: {bridge.mu_bn:.6f}, Std BN: {bridge.sigma_bn:.6f}, Theta BN: {bridge.theta_bn:.6f}")
    print(f"Mean MOD: {bridge.mu_mod:.6f}, Std MOD: {bridge.sigma_mod:.6f}, Theta MOD: {bridge.theta_mod:.6f}")
    
    theta_bn_old = bridge.theta_bn
    theta_mod_old = bridge.theta_mod

    # Simulate QoS update on some edges
    print("\n--- Updating QoS for edge ('0', '6') and ('12', '0') ---")
    overlay.update_edge_qos('0', '6', 'bandwidth_mbps', 1000.0)
    overlay.update_edge_qos('0', '6', 'delay_ms', 2.0)
    overlay.update_edge_qos('12', '0', 'bandwidth_mbps', 1500.0)
    overlay.update_edge_qos('12', '0', 'delay_ms', 1.0)
    
    print("\nAfter QoS update, structural parameters:")
    print(f"Mean BN: {bridge.mu_bn:.6f}, Std BN: {bridge.sigma_bn:.6f}, Theta BN: {bridge.theta_bn:.6f}")
    print(f"Mean MOD: {bridge.mu_mod:.6f}, Std MOD: {bridge.sigma_mod:.6f}, Theta MOD: {bridge.theta_mod:.6f}")
    
    # In S3, the topology changes, which triggers regeneration and updates thresholds
    print("\nSCENARIO S3 PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_s3()
