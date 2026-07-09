import os
import sys
import csv
from tabulate import tabulate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.heuristic_agent import HeuristicAgent
from src.routing.baselines import Baselines
from src.metrics.robustness_g import RobustnessG

def calculate_path_metrics(path, C, bridge, pdp):
    if not path:
        return {
            'status': 'DENIED/BLOCKED',
            'delay': float('inf'),
            'bandwidth': 0.0,
            'hops': 0,
            'min_trust': 0.0,
            'avg_bn': 0.0
        }
    
    delay = 0.0
    bw = float('inf')
    sum_bn = 0.0
    min_trust = 1.0

    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        delay += C[u][v].get('delay_ms', 0.0)
        bw = min(bw, C[u][v].get('bandwidth_mbps', 0.0))

    for node in path:
        node_str = str(node)
        zone = C.get_zone(node_str)
        sum_bn += bridge.bn_scores.get(node_str, 0.0)
        min_trust = min(min_trust, pdp.get_trust_score(node_str, zone))

    return {
        'status': 'ACTIVE',
        'delay': delay,
        'bandwidth': bw,
        'hops': len(path) - 1,
        'min_trust': min_trust,
        'avg_bn': sum_bn / len(path)
    }

def main():
    print("=" * 70)
    print("RUNNING BENCHMARK EVALUATIONS FOR 5 BASELINES")
    print("=" * 70)

    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    topo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies", "internetmci.graphml"))

    # We will test under 4 network states:
    # 1. NORMAL (Clean network, high trust)
    # 2. TRUST_COMPROMISED (Intermediate node 12 trust drops to 0.3)
    # 3. DELAY_SPIKE (Delay on edge 14->12 increases to 200ms)
    # 4. STRUCTURE_MITIGATED (Outliers isolated via Step 5c)

    results = []

    # Run for each state
    states = ['NORMAL', 'BW_CONGESTION', 'TRUST_DEGRADED', 'DELAY_SPIKE', 'STRUCTURE_MITIGATED']
    baselines = ['SP-Routing', 'QoS-Routing', 'Seg-Routing', 'ZT-Routing', 'ZT-SR-VI']

    # Initialize a clean environment for each evaluation to avoid pollution
    for state in states:
        print(f"\nEvaluating State: {state}")
        overlay = OverlayManager(config_dir, topo_path)
        pdp = PDP(config_dir)
        zm = ZoneMatrix(config_dir)
        bridge = CGBridge(zm, k=1.0)  # Using k=1.0 as specified in Design Lock v1
        agent = HeuristicAgent()
        
        # Configure the environment according to the state
        # 1. Default clean posture:
        pdp.use_avod_context = False
        # Fixed zone-based theta for reproducibility: theta(IT->FIN) = max(0.80, 0.90) = 0.90
        pdp.use_adaptive_theta = False
        for zone in pdp.context.profiles:
            pdp.context.profiles[zone]['cvss'] = 0.0
        for node in overlay.get_c().nodes():
            n_str = str(node)
            pdp.identity.set_score(n_str, 1.0)
            pdp.context.set_patch_factor(n_str, 1.0)
            pdp.behavior.set_score(n_str, 0.95)

        # Regenerate G initially
        bridge.regenerate_g(overlay.get_c())

        if state == 'BW_CONGESTION':
            # Degrade bw on 14->12: forces QoS-Routing to pick alternate path
            overlay.update_edge_qos('14', '12', 'bandwidth_mbps', 10.0)
        elif state == 'TRUST_DEGRADED':
            # Compromise node 12 (behavior=0.3, trust=0.79 < fixed theta=0.90)
            pdp.behavior.set_score('12', 0.3)
        elif state == 'DELAY_SPIKE':
            # Spike delay on 14->12 edge
            overlay.update_edge_qos('14', '12', 'delay_ms', 200.0)
        elif state == 'STRUCTURE_MITIGATED':
            # Cut edge 14->12 to simulate structural mitigation
            overlay.update_edge_qos('14', '12', 'bandwidth_mbps', 0.0)
            # Need to regenerate G after C changes
            bridge.regenerate_g(overlay.get_c())

        C = overlay.get_c()
        
        # Evaluate each baseline for flow IT Node '14' -> FIN Node '7'
        for bl in baselines:
            path = None
            if bl == 'SP-Routing':
                path = Baselines.sp_routing('14', '7', C)
            elif bl == 'QoS-Routing':
                path = Baselines.qos_routing('14', '7', C)
            elif bl == 'Seg-Routing':
                path = Baselines.seg_routing('14', '7', C, zm)
            elif bl == 'ZT-Routing':
                path = Baselines.zt_routing('14', '7', C, pdp)
            elif bl == 'ZT-SR-VI':
                path = Baselines.zt_sr_drl('14', '7', C, pdp, zm, bridge, agent)

            metrics = calculate_path_metrics(path, C, bridge, pdp)
            
            # Global MSPL
            metrics_g = RobustnessG.calculate_all(bridge.G)
            mspl = metrics_g.get('MSPL', float('inf'))
            nsp = metrics_g.get('NSP', 0)
            ab = metrics_g.get('AB', 0.0)
            cmc = metrics_g.get('CMC', 0)

            results.append({
                'State': state,
                'Baseline': bl,
                'Status': metrics['status'],
                'Path': str(path),
                'Delay (ms)': f"{metrics['delay']:.2f}" if metrics['delay'] != float('inf') else 'inf',
                'Bandwidth (Mbps)': f"{metrics['bandwidth']:.1f}" if metrics['bandwidth'] != float('inf') else '0.0',
                'Hops': metrics['hops'],
                'Min Trust': f"{metrics['min_trust']:.4f}",
                'Avg BN on path': f"{metrics['avg_bn']:.6f}",
                'Global MSPL': 'inf' if mspl == float('inf') else str(mspl),
                'NSP (G)': nsp,
                'AB (G)': f"{ab:.6f}",
                'CMC (G)': cmc,
            })

    # Export to CSV
    res_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    os.makedirs(res_dir, exist_ok=True)
    csv_path = os.path.join(res_dir, "benchmark_results.csv")
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults successfully exported to: {csv_path}")

    # Display results as table
    headers = [
        'State',
        'Baseline',
        'Status',
        'Delay (ms)',
        'Hops',
        'Min Trust',
        'Avg BN on path',
        'Global MSPL',
        'NSP (G)',
        'AB (G)',
        'CMC (G)',
    ]
    table_data = [[r[h] for h in headers] for r in results]
    
    print("\n=== KET QUA SO SANH 5 BASELINE ===")
    # Check if tabulate is installed, otherwise print raw dicts
    try:
        print(tabulate(table_data, headers=headers, tablefmt="github"))
    except ImportError:
        # Fallback raw printing
        for r in results:
            print(f"State: {r['State']} | Baseline: {r['Baseline']} | Status: {r['Status']} | Delay: {r['Delay (ms)']} | Min Trust: {r['Min Trust']} | Avg BN on path: {r['Avg BN on path']}")
            
    print("\nBENCHMARK COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
