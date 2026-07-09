import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix
from src.microseg.bridge_cg import CGBridge
from src.routing.baselines import Baselines
from src.routing.action_mask import ActionMask
from src.routing.reward import load_reward_hyperparams

def run_extreme():
    print("=== CHUẨN BỊ MÔI TRƯỜNG: EXTREME_SCENARIO (THẢM HỌA ĐA HƯỚNG) ===")
    config_dir = "config"
    topo_path = "data/topologies/internetmci.graphml"

    overlay = OverlayManager(config_dir, topo_path)
    C = overlay.get_c()
    pdp = PDP(config_dir)
    zm = ZoneMatrix(config_dir)
    bridge = CGBridge(zm, k=1.0)
    reward_params = load_reward_hyperparams(os.path.join(config_dir, "hyperparams.yaml"))

    # 1. Reset everything to baseline
    pdp.use_avod_context = False
    pdp.use_adaptive_theta = False
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]["cvss"] = 0.0
    for node in C.nodes():
        node_str = str(node)
        pdp.identity.set_score(node_str, 1.0)
        pdp.context.set_patch_factor(node_str, 1.0)
        pdp.behavior.set_score(node_str, 0.95)
    
    # 2. Thiết lập Bãi mìn (EXTREME_SCENARIO)

    # --- ĐẠI DỊCH COMPROMISE (Trust Attacks) ---
    pdp.behavior.set_score("18", 0.1) # Trust rất thấp (bị block)
    pdp.behavior.set_score("16", 0.1) # Trust rất thấp (bị block)
    pdp.behavior.set_score("2", 0.2)  # Trust rất thấp (bị block)
    
    pdp.behavior.set_score("13", 0.7) # Đáng ngờ (phạt reward)
    pdp.behavior.set_score("12", 0.8) # Đáng ngờ (phạt reward)

    # --- NGHẼN MẠNG LÕI (The Swamp) ---
    # Làm cho các tuyến đường hợp lệ trở nên vô cùng tồi tệ
    overlay.update_edge_qos("12", "0", "delay_ms", 100.0)
    overlay.update_edge_qos("12", "0", "bandwidth_mbps", 20.0)
    
    overlay.update_edge_qos("0", "6", "delay_ms", 200.0)
    overlay.update_edge_qos("0", "6", "bandwidth_mbps", 10.0)
    
    overlay.update_edge_qos("6", "5", "delay_ms", 150.0)
    overlay.update_edge_qos("6", "5", "bandwidth_mbps", 15.0)
    
    overlay.update_edge_qos("5", "4", "delay_ms", 100.0)
    overlay.update_edge_qos("5", "4", "bandwidth_mbps", 25.0)

    # --- MỒI NHỬ TỐC ĐỘ CAO (The Decoy Traps) ---
    # Mở một đường cao tốc xuyên qua bãi mìn, nhưng vi phạm Zone và Trust
    # Bẫy Zone: 8 -> 6 (FIN -> DMZ)
    overlay.update_edge_qos("0", "8", "delay_ms", 2.0)
    overlay.update_edge_qos("0", "8", "bandwidth_mbps", 1000.0)
    overlay.update_edge_qos("8", "6", "delay_ms", 2.0)
    overlay.update_edge_qos("8", "6", "bandwidth_mbps", 1000.0)
    
    # Bẫy Trust: Xuyên qua node 2 bị compromise
    overlay.update_edge_qos("5", "2", "delay_ms", 2.0)
    overlay.update_edge_qos("5", "2", "bandwidth_mbps", 1000.0)
    overlay.update_edge_qos("2", "1", "delay_ms", 2.0)
    overlay.update_edge_qos("2", "1", "bandwidth_mbps", 1000.0)
    overlay.update_edge_qos("1", "4", "delay_ms", 2.0)
    overlay.update_edge_qos("1", "4", "bandwidth_mbps", 1000.0)

    bridge.regenerate_g(C)

    # 3. Chạy 5 Baselines
    s, d = "17", "4"
    zone_s, zone_d = C.get_zone(s), C.get_zone(d)
    theta_path = pdp.get_theta_path(zone_s, zone_d, C)

    print(f"\nFlow: {s}({zone_s}) -> {d}({zone_d}) | Theta_path = {theta_path:.2f}")
    
    masks = ActionMask.build_node_masks(C, pdp, s, d, struct_mask=None)
    E_f = ActionMask.get_feasible_edges(C, masks, zm)

    results = []

    # 1. SP
    path_sp = Baselines.sp_routing(s, d, C)
    results.append(("SP-Routing", path_sp))

    # 2. QoS
    path_qos = Baselines.qos_routing(s, d, C)
    results.append(("QoS-Routing", path_qos))

    # 3. Seg
    path_seg = Baselines.seg_routing(s, d, C, zm)
    results.append(("Seg-Routing", path_seg))

    # 4. ZT
    path_zt = Baselines.zt_routing(s, d, C, pdp)
    results.append(("ZT-Routing", path_zt))

    # 5. ZT-SR-VI
    path_zt_sr = Baselines.zt_sr_drl(s, d, C, pdp, zm, bridge, None)
    results.append(("ZT-SR-VI", path_zt_sr))

    print("\n=== KẾT QUẢ ROUTING ===")
    out_data = []
    for name, path in results:
        if not path:
            out_data.append({
                "Baseline": name,
                "Status": "BLOCKED",
                "Path": "-",
                "Delay (ms)": "INF",
                "BW (Mbps)": "0",
                "Trust OK?": "-",
                "Zone OK?": "-"
            })
            continue

        delay = sum(C[path[i]][path[i+1]].get('delay_ms',0) for i in range(len(path)-1))
        bw = min((C[path[i]][path[i+1]].get('bandwidth_mbps',float('inf')) for i in range(len(path)-1)), default=0)
        
        trust_ok = True
        for node in path:
            if pdp.get_trust_score(node, C.get_zone(node), C) < theta_path:
                trust_ok = False
                break
        
        zone_ok = True
        for i in range(len(path)-1):
            if not zm.is_allowed(C.get_zone(path[i]), C.get_zone(path[i+1])):
                zone_ok = False
                break

        status = "ACTIVE"
        if not trust_ok or not zone_ok:
            status = "ACTIVE ⚠️ (VIOLATION)"

        out_data.append({
            "Baseline": name,
            "Status": status,
            "Path": "->".join(path),
            "Delay (ms)": f"{delay:.2f}",
            "BW (Mbps)": f"{bw:.2f}",
            "Trust OK?": "✅" if trust_ok else "❌",
            "Zone OK?": "✅" if zone_ok else "❌"
        })

    df = pd.DataFrame(out_data)
    print(df.to_string(index=False))

    print("\nNhận xét: ZT-SR-VI buộc phải chọn con đường 'đau khổ' nhất để sinh tồn giữa bãi mìn!")

if __name__ == "__main__":
    run_extreme()
