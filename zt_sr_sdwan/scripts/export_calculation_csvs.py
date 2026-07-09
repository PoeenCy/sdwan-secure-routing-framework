import csv
import math
import os
import sys
from pathlib import Path

import networkx as nx

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.metrics.robustness_g import RobustnessG
from src.models.graph_g import GraphG
from src.microseg.bridge_cg import CGBridge
from src.microseg.zone_matrix import ZoneMatrix
from src.routing.action_mask import ActionMask
from src.routing.baselines import Baselines
from src.routing.reward import (
    compute_delta_mspl,
    compute_nsp_delta,
    compute_reward,
    load_reward_hyperparams,
)
from src.topology.overlay_manager import OverlayManager
from src.trust.pdp import PDP


SOURCE = "14"
TARGET = "7"
STATES = ["NORMAL", "BW_CONGESTION", "TRUST_DEGRADED", "DELAY_SPIKE", "STRUCTURE_MITIGATED"]
BASELINES = ["SP-Routing", "QoS-Routing", "Seg-Routing", "ZT-Routing", "ZT-SR-VI"]


def write_csv(path: Path, rows: list, fieldnames: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value, digits=6):
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return value


def path_text(path):
    if not path:
        return ""
    return "->".join(str(n) for n in path)


def edge_qos(data):
    bw = float(data.get("bandwidth_mbps", 0.0) or 0.0)
    delay = float(data.get("delay_ms", 0.0) or 0.0)
    qos_weight = delay + (1000.0 / bw) if bw > 0.0 else float("inf")
    return delay, bw, qos_weight


# State descriptions for benchmark scenarios
STATE_DESCRIPTIONS = {
    "NORMAL": "Clean baseline: all nodes trusted, full bandwidth, no disruption.",
    "BW_CONGESTION": "Edge 14->12 bandwidth degraded to 10 Mbps; QoS-Routing picks alternate path.",
    "TRUST_DEGRADED": "Node 12 behavior-compromised (trust=0.79 < theta=0.90); ZT-Routing avoids it, ZT-SR-VI blocked.",
    "DELAY_SPIKE": "Edge 14->12 delay spiked to 200 ms; SP/QoS/ZT detour, Seg/ZT-SR-VI stay on original (zone-constrained).",
    "STRUCTURE_MITIGATED": "Edge 14->12 cut (bandwidth=0) to simulate structural mitigation; Seg and ZT-SR-VI blocked.",
}


def prepare_environment(state, config_dir, topo_path):
    overlay = OverlayManager(str(config_dir), str(topo_path))
    C = overlay.get_c()
    pdp = PDP(str(config_dir))
    zm = ZoneMatrix(str(config_dir))
    bridge = CGBridge(zm, k=1.0)

    pdp.use_avod_context = False
    # Use fixed zone-based theta (not adaptive) so each state is reproducible
    # and trust filtering is predictable: theta(IT->FIN) = max(0.80, 0.90) = 0.90
    pdp.use_adaptive_theta = False
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]["cvss"] = 0.0
    for node in C.nodes():
        node_str = str(node)
        pdp.identity.set_score(node_str, 1.0)
        pdp.context.set_patch_factor(node_str, 1.0)
        pdp.behavior.set_score(node_str, 0.95)

    bridge.regenerate_g(C)
    cut_edges = []

    if state == "BW_CONGESTION":
        # Reduce bw of 14->12 to force QoS-Routing to prefer alternate path
        # QoS weight: 32.33 + 1000/10 = 132.33 for this edge (was 37.33)
        # Path [2] QoS total (171.95) < Path [1] QoS total (209.98) -> QoS picks [2]
        overlay.update_edge_qos("14", "12", "bandwidth_mbps", 10.0)
    elif state == "TRUST_DEGRADED":
        # Node 12 behavior compromised: trust = 0.4*1.0 + 0.3*0.3 + 0.3*1.0 = 0.79
        # Fixed theta = 0.90 for IT->FIN flow -> ZT-Routing avoids node 12
        # ZT-SR-VI (zone+trust) also blocked because zone filter removes 8->6 (FIN->DMZ)
        pdp.behavior.set_score("12", 0.3)
    elif state == "DELAY_SPIKE":
        # Edge 14->12 delay spike: SP/QoS/ZT detour via 14-8-6-5-2-0-7
        # Seg/ZT-SR-VI stay on 14-12-0-7 (zone filter blocks FIN->DMZ edge 8->6)
        overlay.update_edge_qos("14", "12", "delay_ms", 200.0)
    elif state == "STRUCTURE_MITIGATED":
        # Cut edge 14->12 entirely (bandwidth=0) to simulate structural mitigation
        # SP/QoS/ZT detour via 14-8-6-5-2-0-7
        # Seg/ZT-SR-VI blocked: no zone-compliant path exists without 14->12
        overlay.update_edge_qos("14", "12", "bandwidth_mbps", 0.0)
        bridge.regenerate_g(C)

    RobustnessG.calculate_all(bridge.G)
    return overlay, C, pdp, zm, bridge, cut_edges


def calculate_path_metrics(path, C, bridge, pdp, reward_params):
    if not path:
        return {
            "status": "DENIED/BLOCKED",
            "delay_ms": float("inf"),
            "qos_weight": float("inf"),
            "bandwidth_mbps": 0.0,
            "hops": 0,
            "min_trust": 0.0,
            "avg_bn_on_path": 0.0,
            "reward_sum": 0.0,
        }

    delay_total = 0.0
    qos_total = 0.0
    bw_bottleneck = float("inf")
    reward_total = 0.0
    trust_scores = []
    bn_scores = []

    for i in range(len(path) - 1):
        u, v = str(path[i]), str(path[i + 1])
        delay, bw, qos_weight = edge_qos(C[u][v])
        delay_total += delay
        qos_total += qos_weight
        bw_bottleneck = min(bw_bottleneck, bw)
        reward_total += compute_reward(
            u,
            v,
            C,
            bridge.G,
            path_so_far=[str(n) for n in path[: i + 1]],
            hyperparams=reward_params,
        )

    for node in path:
        node_str = str(node)
        zone = C.get_zone(node_str)
        trust_scores.append(pdp.get_trust_score(node_str, zone, C))
        bn_scores.append(float(bridge.bn_scores.get(node_str, 0.0)))

    return {
        "status": "ACTIVE",
        "delay_ms": delay_total,
        "qos_weight": qos_total,
        "bandwidth_mbps": bw_bottleneck,
        "hops": len(path) - 1,
        "min_trust": min(trust_scores) if trust_scores else 0.0,
        "avg_bn_on_path": sum(bn_scores) / len(bn_scores) if bn_scores else 0.0,
        "reward_sum": reward_total,
    }


def route_for_baseline(name, C, pdp, zm, bridge, source=SOURCE, target=TARGET):
    if name == "SP-Routing":
        return Baselines.sp_routing(source, target, C)
    if name == "QoS-Routing":
        return Baselines.qos_routing(source, target, C)
    if name == "Seg-Routing":
        return Baselines.seg_routing(source, target, C, zm)
    if name == "ZT-Routing":
        return Baselines.zt_routing(source, target, C, pdp)
    if name == "ZT-SR-VI":
        return Baselines.zt_sr_drl(source, target, C, pdp, zm, bridge, None)
    raise ValueError(f"Unknown baseline: {name}")


def export_qos_edges(rows, state, C):
    for u, v, data in C.edges(data=True):
        delay, bw, qos_weight = edge_qos(data)
        rows.append({
            "state": state,
            "u": str(u),
            "v": str(v),
            "zone_u": C.get_zone(str(u)),
            "zone_v": C.get_zone(str(v)),
            "active": bw > 0.0,
            "delay_ms": fmt(delay),
            "bandwidth_mbps": fmt(bw),
            "loss_rate": fmt(float(data.get("loss_rate", 0.0) or 0.0)),
            "qos_weight_delay_plus_1000_over_bw": fmt(qos_weight),
        })


def export_robustness(rows_global, rows_nodes, rows_bn_pairs, state, C, bridge):
    G = bridge.G
    metrics = RobustnessG.calculate_all(G)
    roots = [str(n) for n in G.nodes() if G.nodes[n].get("is_root")]
    targets = [str(n) for n in G.nodes() if G.nodes[n].get("is_target")]
    critical = sorted(set(roots).intersection(targets))

    rows_global.append({
        "state": state,
        "R_G": ";".join(roots),
        "L_G": ";".join(targets),
        "critical_nodes": ";".join(critical),
        "MSPL": fmt(metrics.get("MSPL", float("inf"))),
        "NSP": metrics.get("NSP", 0),
        "CMPL": metrics.get("CMPL", 0),
        "CMC": metrics.get("CMC", 0),
        "MOD": metrics.get("MOD", 0),
        "AOD": fmt(metrics.get("AOD", 0.0)),
        "AB_G": fmt(metrics.get("AB", 0.0)),
        "theta_bn": fmt(bridge.theta_bn),
        "theta_mod": fmt(bridge.theta_mod),
    })

    for node in G.nodes():
        node_str = str(node)
        attrs = G.nodes[node]
        rows_nodes.append({
            "state": state,
            "node": node_str,
            "zone": C.get_zone(node_str) if C.has_node(node_str) else attrs.get("zone", ""),
            "is_root": bool(attrs.get("is_root", False)),
            "is_target": bool(attrs.get("is_target", False)),
            "is_critical": node_str in critical,
            "BN": fmt(metrics["BN"].get(node_str, 0.0)),
            "MOD_node_out_degree": fmt(float(G.out_degree(node_str))),
            "on_shortest_attack_path": bool(attrs.get("on_shortest_attack_path", False)),
            "cvss_max": fmt(float(attrs.get("cvss_max", 0.0) or 0.0)),
            "theta_bn": fmt(bridge.theta_bn),
            "theta_mod": fmt(bridge.theta_mod),
            "struct_pass_raw": bool(bridge.get_struct_mask().get(node_str, True)),
        })

    for root in roots:
        for target in targets:
            if root == target:
                rows_bn_pairs.append({
                    "state": state,
                    "root_r": root,
                    "target_l": target,
                    "pair_status": "skip_same_root_target",
                    "NSP_rl": 0,
                    "path_index": "",
                    "shortest_path": "",
                    "intermediate_node_n": "",
                    "contribution_NSP_rl_n_over_NSP_rl": "",
                })
                continue
            if not nx.has_path(G, root, target):
                rows_bn_pairs.append({
                    "state": state,
                    "root_r": root,
                    "target_l": target,
                    "pair_status": "no_path",
                    "NSP_rl": 0,
                    "path_index": "",
                    "shortest_path": "",
                    "intermediate_node_n": "",
                    "contribution_NSP_rl_n_over_NSP_rl": "",
                })
                continue
            paths = list(nx.all_shortest_paths(G, root, target))
            nsp_rl = len(paths)
            for path_index, path in enumerate(paths):
                intermediates = [str(n) for n in path[1:-1]]
                if not intermediates:
                    rows_bn_pairs.append({
                        "state": state,
                        "root_r": root,
                        "target_l": target,
                        "pair_status": "direct_no_intermediate",
                        "NSP_rl": nsp_rl,
                        "path_index": path_index,
                        "shortest_path": path_text(path),
                        "intermediate_node_n": "",
                        "contribution_NSP_rl_n_over_NSP_rl": "0.000000",
                    })
                    continue
                for node in intermediates:
                    rows_bn_pairs.append({
                        "state": state,
                        "root_r": root,
                        "target_l": target,
                        "pair_status": "has_intermediate",
                        "NSP_rl": nsp_rl,
                        "path_index": path_index,
                        "shortest_path": path_text(path),
                        "intermediate_node_n": node,
                        "contribution_NSP_rl_n_over_NSP_rl": fmt(1.0 / nsp_rl),
                    })


def export_masks_and_edges(rows_trust, rows_edges, state, C, pdp, zm, bridge):
    theta_path = pdp.get_theta_path(C.get_zone(SOURCE), C.get_zone(TARGET), C)
    struct_mask = bridge.get_struct_mask()
    node_masks = ActionMask.build_node_masks(C, pdp, SOURCE, TARGET, struct_mask)

    for node in C.nodes():
        node_str = str(node)
        zone = C.get_zone(node_str)
        identity = pdp.identity.get_score(node_str)
        context = pdp.context.get_score(node_str, zone, C, pdp.use_avod_context)
        behavior = pdp.behavior.get_score(node_str)
        trust = pdp.get_trust_score(node_str, zone, C)
        raw_struct = bool(struct_mask.get(node_str, True))
        exempt = str(zone).lower() == "core" or node_str in {SOURCE, TARGET}
        struct_after_exemption = True if exempt else raw_struct
        trust_pass = trust >= theta_path
        rows_trust.append({
            "state": state,
            "node": node_str,
            "zone": zone,
            "I_identity": fmt(identity),
            "B_behavior": fmt(behavior),
            "C_context": fmt(context),
            "T_trust_0_4I_0_3B_0_3C": fmt(trust),
            "theta_path": fmt(theta_path),
            "trust_pass": trust_pass,
            "BN": fmt(bridge.bn_scores.get(node_str, 0.0)),
            "MOD": fmt(bridge.mod_scores.get(node_str, 0.0)),
            "theta_bn": fmt(bridge.theta_bn),
            "theta_mod": fmt(bridge.theta_mod),
            "struct_pass_raw": raw_struct,
            "struct_exempt_core_or_endpoint": exempt,
            "struct_pass_after_exemption": struct_after_exemption,
            "composite_node_mask": bool(node_masks.get(node_str, True)),
        })

    for u, v, data in C.edges(data=True):
        u_str, v_str = str(u), str(v)
        delay, bw, qos_weight = edge_qos(data)
        zone_u = C.get_zone(u_str)
        zone_v = C.get_zone(v_str)
        active = bw > 0.0
        zone_allowed = zm.is_allowed(zone_u, zone_v)
        mask_u = bool(node_masks.get(u_str, True))
        mask_v = bool(node_masks.get(v_str, True))
        rows_edges.append({
            "state": state,
            "u": u_str,
            "v": v_str,
            "zone_u": zone_u,
            "zone_v": zone_v,
            "active": active,
            "zone_allowed": zone_allowed,
            "mask_u": mask_u,
            "mask_v": mask_v,
            "feasible_edge": active and zone_allowed and mask_u and mask_v,
            "delay_ms": fmt(delay),
            "bandwidth_mbps": fmt(bw),
            "qos_weight": fmt(qos_weight),
        })


def reward_components(u, v, path_prefix, C, bridge, params):
    data = C[u][v]
    delay, bw, _ = edge_qos(data)
    bw_max = params.get("bw_max", 1000.0) or 1000.0
    delay_max = params.get("delay_max", 100.0) or 100.0
    norm_bw = bw / bw_max
    norm_delay = delay / delay_max
    graph_g = bridge.G
    mod_n = graph_g.out_degree(v) if graph_g.has_node(v) else 0.0
    bn_n = graph_g.nodes[v].get("bn", 0.0) if graph_g.has_node(v) else 0.0
    malicious_penalty = params["lambda1"] * mod_n + params["lambda2"] * bn_n
    delta_mspl = compute_delta_mspl(v, path_prefix, graph_g)
    nsp_delta = compute_nsp_delta(v, graph_g, params)
    reward = compute_reward(u, v, C, graph_g, path_prefix, params)
    return {
        "norm_bw": norm_bw,
        "norm_delay": norm_delay,
        "BN_next": bn_n,
        "MOD_next": mod_n,
        "malicious_penalty": malicious_penalty,
        "delta_mspl": delta_mspl,
        "nsp_delta": nsp_delta,
        "reward": reward,
    }


def export_paths(rows_summary, rows_edges, state, C, pdp, zm, bridge, reward_params):
    metrics_g = RobustnessG.calculate_all(bridge.G)
    for baseline in BASELINES:
        path = route_for_baseline(baseline, C, pdp, zm, bridge)
        metrics = calculate_path_metrics(path, C, bridge, pdp, reward_params)
        rows_summary.append({
            "state": state,
            "baseline": baseline,
            "status": metrics["status"],
            "path": path_text(path),
            "delay_ms": fmt(metrics["delay_ms"]),
            "qos_weight": fmt(metrics["qos_weight"]),
            "bandwidth_mbps": fmt(metrics["bandwidth_mbps"]),
            "hops": metrics["hops"],
            "min_trust": fmt(metrics["min_trust"]),
            "avg_bn_on_path": fmt(metrics["avg_bn_on_path"]),
            "reward_sum": fmt(metrics["reward_sum"]),
            "MSPL_G": fmt(metrics_g.get("MSPL", float("inf"))),
            "NSP_G": metrics_g.get("NSP", 0),
            "AB_G": fmt(metrics_g.get("AB", 0.0)),
            "CMC_G": metrics_g.get("CMC", 0),
        })

        if not path:
            continue

        cumulative_delay = 0.0
        cumulative_qos = 0.0
        bottleneck = float("inf")
        for i in range(len(path) - 1):
            u, v = str(path[i]), str(path[i + 1])
            delay, bw, qos_weight = edge_qos(C[u][v])
            cumulative_delay += delay
            cumulative_qos += qos_weight
            bottleneck = min(bottleneck, bw)
            components = reward_components(u, v, [str(n) for n in path[: i + 1]], C, bridge, reward_params)
            rows_edges.append({
                "state": state,
                "baseline": baseline,
                "path": path_text(path),
                "edge_index": i,
                "u": u,
                "v": v,
                "zone_u": C.get_zone(u),
                "zone_v": C.get_zone(v),
                "delay_ms": fmt(delay),
                "bandwidth_mbps": fmt(bw),
                "qos_weight": fmt(qos_weight),
                "cumulative_delay_ms": fmt(cumulative_delay),
                "cumulative_qos_weight": fmt(cumulative_qos),
                "bottleneck_bandwidth_so_far": fmt(bottleneck),
                "norm_bw": fmt(components["norm_bw"]),
                "norm_delay": fmt(components["norm_delay"]),
                "BN_next": fmt(components["BN_next"]),
                "MOD_next": fmt(components["MOD_next"]),
                "malicious_penalty": fmt(components["malicious_penalty"]),
                "delta_mspl": fmt(components["delta_mspl"]),
                "nsp_delta": fmt(components["nsp_delta"]),
                "reward": fmt(components["reward"]),
            })


def export_bn_ab_controlled_demo(output_dir: Path):
    """
    Controlled example for explaining BN and AB_G without changing the real
    benchmark topology. The validation path is an actual C path and is
    intentionally different from the original 14->7 routing flow:

        14 -> 8 -> 6 -> 5

    Nodes 8 and 6 are intermediate nodes for the 14->5 pair. Node 6 is also
    in L_G, so AB_G changes when BN(6) changes.
    """
    G = GraphG()
    G.add_node("14", is_root=True, is_target=False)
    G.add_node("8", is_root=False, is_target=False)
    G.add_node("6", is_root=False, is_target=True)
    G.add_node("5", is_root=False, is_target=True)
    G.entry_nodes = {"14"}
    G.target_nodes = {"6", "5"}
    G.add_edges_from([
        ("14", "8"),
        ("8", "6"),
        ("6", "5"),
    ])

    metrics = RobustnessG.calculate_all(G)
    validation_path = ["14", "8", "6", "5"]
    pairs = [("14", "6"), ("14", "5")]
    nodes_to_explain = ["8", "6"]
    rows = []

    for root, target in pairs:
        paths = list(nx.all_shortest_paths(G, root, target))
        nsp_rl = len(paths)
        for node in nodes_to_explain:
            nsp_rl_n = sum(1 for path in paths if node in [str(x) for x in path[1:-1]])
            contribution = nsp_rl_n / nsp_rl if nsp_rl else 0.0
            role = "intermediate" if nsp_rl_n else "endpoint_or_not_on_path"
            if node == root:
                role = "source_endpoint"
            elif node == target:
                role = "target_endpoint"
            rows.append({
                "demo": "bn_ab_validation",
                "root_r": root,
                "target_l": target,
                "shortest_paths": ";".join(path_text(path) for path in paths),
                "NSP_rl": nsp_rl,
                "node_n": node,
                "role_for_this_pair": role,
                "NSP_rl_n": nsp_rl_n,
                "contribution_NSP_rl_n_over_NSP_rl": fmt(contribution),
                "BN_n_final_after_all_pairs": fmt(metrics["BN"].get(node, 0.0)),
                "node_n_in_L_G": bool(G.nodes[node].get("is_target", False)),
                "AB_G_final": fmt(metrics["AB"]),
            })

    write_csv(output_dir / "bn_ab_controlled_demo.csv", rows, [
        "demo", "root_r", "target_l", "shortest_paths", "NSP_rl", "node_n",
        "role_for_this_pair", "NSP_rl_n", "contribution_NSP_rl_n_over_NSP_rl",
        "BN_n_final_after_all_pairs", "node_n_in_L_G", "AB_G_final",
    ])

    avg_bn_on_validation_path = sum(metrics["BN"].get(node, 0.0) for node in validation_path) / len(validation_path)
    write_csv(output_dir / "bn_ab_validation_summary.csv", [{
        "scenario": "BN_AB_VALIDATION",
        "source": "14",
        "target": "5",
        "validation_path": path_text(validation_path),
        "R_G": "14",
        "L_G": "6;5",
        "BN_8": fmt(metrics["BN"].get("8", 0.0)),
        "BN_6": fmt(metrics["BN"].get("6", 0.0)),
        "BN_5": fmt(metrics["BN"].get("5", 0.0)),
        "avg_bn_on_validation_path": fmt(avg_bn_on_validation_path),
        "MSPL": fmt(metrics["MSPL"]),
        "NSP": metrics["NSP"],
        "AB_G": fmt(metrics["AB"]),
        "CMC": metrics["CMC"],
        "purpose": "Dedicated non-zero BN/AB metric validation case, not the production benchmark",
    }], [
        "scenario", "source", "target", "validation_path", "R_G", "L_G",
        "BN_8", "BN_6", "BN_5", "avg_bn_on_validation_path", "MSPL",
        "NSP", "AB_G", "CMC", "purpose",
    ])


def _build_final_validation_g():
    G = GraphG()
    for node in ["14", "8", "6", "5"]:
        G.add_node(node, is_root=(node == "14"), is_target=(node in {"6", "5"}))
    G.entry_nodes = {"14"}
    G.target_nodes = {"6", "5"}
    G.add_edges_from([
        ("14", "8"),
        ("8", "6"),
        ("6", "5"),
    ])
    return G


def prepare_final_validation_environment(state, config_dir, topo_path):
    overlay = OverlayManager(str(config_dir), str(topo_path))
    C = overlay.get_c()
    pdp = PDP(str(config_dir))
    zm = ZoneMatrix(str(config_dir))
    bridge = CGBridge(zm, k=1.0)

    pdp.use_avod_context = False
    pdp.use_adaptive_theta = False  # fixed theta, consistent with main benchmark
    for zone in pdp.context.profiles:
        pdp.context.profiles[zone]["cvss"] = 0.0
    for node in C.nodes():
        node_str = str(node)
        pdp.identity.set_score(node_str, 1.0)
        pdp.context.set_patch_factor(node_str, 1.0)
        pdp.behavior.set_score(node_str, 0.95)

    bridge.G = _build_final_validation_g()
    bridge.update_structural_thresholds()
    RobustnessG.calculate_all(bridge.G)

    state_note = "Clean state for validation flow 14->5."
    if state == "BW_CONGESTION":
        overlay.update_edge_qos("14", "8", "bandwidth_mbps", 10.0)
        state_note = "Edge 14->8 bandwidth degraded to 10 Mbps on validation path."
    elif state == "TRUST_DEGRADED":
        pdp.behavior.set_score("6", 0.3)
        state_note = "Node 6 on validation path is behavior-compromised (trust=0.79 < theta)."
    elif state == "DELAY_SPIKE":
        overlay.update_edge_qos("14", "8", "delay_ms", 200.0)
        state_note = "Edge 14->8 on validation path has delay spike."
    elif state == "STRUCTURE_MITIGATED":
        overlay.update_edge_qos("8", "6", "bandwidth_mbps", 0.0)
        C["8"]["6"]["delay_ms"] = float("inf")
        state_note = "High-BN edge 8->6 is disabled to force an alternate path."

    return C, pdp, zm, bridge, state_note



def export_final_baseline_statistics(output_dir: Path, config_dir: Path, topo_path: Path, reward_params: dict):
    source = "14"
    target = "5"
    rows = []

    for state in STATES:
        C, pdp, zm, bridge, state_note = prepare_final_validation_environment(state, config_dir, topo_path)
        metrics_g = RobustnessG.calculate_all(bridge.G)
        bn = metrics_g["BN"]

        for baseline in BASELINES:
            path = route_for_baseline(baseline, C, pdp, zm, bridge, source, target)
            metrics = calculate_path_metrics(path, C, bridge, pdp, reward_params)
            rows.append({
                "State": state,
                "Baseline": baseline,
                "Flow": f"{source}->{target}",
                "Status": metrics["status"],
                "Path": path_text(path),
                "Delay_ms": fmt(metrics["delay_ms"]),
                "QoS_weight": fmt(metrics["qos_weight"]),
                "Bandwidth_Mbps": fmt(metrics["bandwidth_mbps"]),
                "Hops": metrics["hops"],
                "Min_Trust": fmt(metrics["min_trust"]),
                "Avg_BN_on_path": fmt(metrics["avg_bn_on_path"]),
                "Reward_sum": fmt(metrics["reward_sum"]),
                "BN_8": fmt(bn.get("8", 0.0)),
                "BN_6": fmt(bn.get("6", 0.0)),
                "BN_5": fmt(bn.get("5", 0.0)),
                "MSPL_G": fmt(metrics_g.get("MSPL", float("inf"))),
                "NSP_G": metrics_g.get("NSP", 0),
                "AB_G": fmt(metrics_g.get("AB", 0.0)),
                "CMC_G": metrics_g.get("CMC", 0),
                "State_note": state_note,
            })

    write_csv(output_dir / "final_baseline_statistics_validation_flow.csv", rows, [
        "State", "Baseline", "Flow", "Status", "Path", "Delay_ms",
        "QoS_weight", "Bandwidth_Mbps", "Hops", "Min_Trust",
        "Avg_BN_on_path", "Reward_sum", "BN_8", "BN_6", "BN_5",
        "MSPL_G", "NSP_G", "AB_G", "CMC_G", "State_note",
    ])


def main():
    base_dir = Path(__file__).resolve().parents[1]
    config_dir = base_dir / "config"
    topo_path = base_dir / "data" / "topologies" / "internetmci.graphml"
    output_dir = base_dir / "results" / "calculations"
    reward_params = load_reward_hyperparams(str(config_dir / "hyperparams.yaml"))

    qos_edge_rows = []
    robustness_global_rows = []
    robustness_node_rows = []
    bn_pair_rows = []
    trust_rows = []
    feasible_edge_rows = []
    path_summary_rows = []
    path_edge_rows = []

    for state in STATES:
        _, C, pdp, zm, bridge, _ = prepare_environment(state, config_dir, topo_path)
        export_qos_edges(qos_edge_rows, state, C)
        export_robustness(robustness_global_rows, robustness_node_rows, bn_pair_rows, state, C, bridge)
        export_masks_and_edges(trust_rows, feasible_edge_rows, state, C, pdp, zm, bridge)
        export_paths(path_summary_rows, path_edge_rows, state, C, pdp, zm, bridge, reward_params)

    write_csv(output_dir / "qos_edge_metrics_by_state.csv", qos_edge_rows, [
        "state", "u", "v", "zone_u", "zone_v", "active", "delay_ms",
        "bandwidth_mbps", "loss_rate", "qos_weight_delay_plus_1000_over_bw",
    ])
    write_csv(output_dir / "robustness_global_metrics_by_state.csv", robustness_global_rows, [
        "state", "R_G", "L_G", "critical_nodes", "MSPL", "NSP", "CMPL",
        "CMC", "MOD", "AOD", "AB_G", "theta_bn", "theta_mod",
    ])
    write_csv(output_dir / "robustness_node_metrics_by_state.csv", robustness_node_rows, [
        "state", "node", "zone", "is_root", "is_target", "is_critical",
        "BN", "MOD_node_out_degree", "on_shortest_attack_path", "cvss_max",
        "theta_bn", "theta_mod", "struct_pass_raw",
    ])
    write_csv(output_dir / "robustness_bn_pair_contributions_by_state.csv", bn_pair_rows, [
        "state", "root_r", "target_l", "pair_status", "NSP_rl", "path_index",
        "shortest_path", "intermediate_node_n", "contribution_NSP_rl_n_over_NSP_rl",
    ])
    write_csv(output_dir / "trust_node_scores_and_masks_by_state.csv", trust_rows, [
        "state", "node", "zone", "I_identity", "B_behavior", "C_context",
        "T_trust_0_4I_0_3B_0_3C", "theta_path", "trust_pass", "BN", "MOD",
        "theta_bn", "theta_mod", "struct_pass_raw",
        "struct_exempt_core_or_endpoint", "struct_pass_after_exemption",
        "composite_node_mask",
    ])
    write_csv(output_dir / "feasible_edges_by_state.csv", feasible_edge_rows, [
        "state", "u", "v", "zone_u", "zone_v", "active", "zone_allowed",
        "mask_u", "mask_v", "feasible_edge", "delay_ms", "bandwidth_mbps",
        "qos_weight",
    ])
    write_csv(output_dir / "routing_path_summary_by_state.csv", path_summary_rows, [
        "state", "baseline", "status", "path", "delay_ms", "qos_weight",
        "bandwidth_mbps", "hops", "min_trust", "avg_bn_on_path",
        "reward_sum", "MSPL_G", "NSP_G", "AB_G", "CMC_G",
    ])
    write_csv(output_dir / "routing_path_edge_breakdown_by_state.csv", path_edge_rows, [
        "state", "baseline", "path", "edge_index", "u", "v", "zone_u",
        "zone_v", "delay_ms", "bandwidth_mbps", "qos_weight",
        "cumulative_delay_ms", "cumulative_qos_weight",
        "bottleneck_bandwidth_so_far", "norm_bw", "norm_delay", "BN_next",
        "MOD_next", "malicious_penalty", "delta_mspl", "nsp_delta", "reward",
    ])
    write_csv(output_dir / "baseline_comparison_by_state.csv", path_summary_rows, [
        "state", "baseline", "status", "path", "delay_ms", "qos_weight",
        "bandwidth_mbps", "hops", "min_trust", "avg_bn_on_path",
        "reward_sum", "MSPL_G", "NSP_G", "AB_G", "CMC_G",
    ])
    export_bn_ab_controlled_demo(output_dir)
    export_final_baseline_statistics(output_dir, config_dir, topo_path, reward_params)

    print(f"Exported calculation CSV files to: {output_dir}")


if __name__ == "__main__":
    main()
