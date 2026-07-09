import networkx as nx
from src.models.graph_c import GraphC
from src.microseg.zone_matrix import ZoneMatrix
from src.trust.pdp import PDP
from src.microseg.bridge_cg import CGBridge
from .action_mask import ActionMask
from .feasible_paths import FeasiblePaths
from .heuristic_agent import HeuristicAgent

class Baselines:
    @staticmethod
    def sp_routing(s: str, d: str, C: GraphC) -> list:
        """
        1. SP-Routing: Dijkstra delay on the full active C.
        Ignores micro-segmentation, trust, and structural masks.
        """
        s_str, d_str = str(s), str(d)
        
        # Build temp subgraph with active edges (bandwidth > 0)
        temp_g = nx.DiGraph()
        for u, v, data in C.edges(data=True):
            if data.get('bandwidth_mbps', 0.0) > 0.0:
                temp_g.add_edge(u, v, delay_ms=data.get('delay_ms', 1.0))
                
        if not temp_g.has_node(s_str) or not temp_g.has_node(d_str):
            return None
        try:
            path = nx.shortest_path(temp_g, source=s_str, target=d_str, weight='delay_ms')
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    @staticmethod
    def qos_routing(s: str, d: str, C: GraphC) -> list:
        """
        2. QoS-Routing: Dijkstra using a composite QoS weight = delay_ms + 1000.0 / bandwidth_mbps.
        Ignores security rules (micro-seg, trust, G).
        """
        s_str, d_str = str(s), str(d)
        temp_g = nx.DiGraph()
        for u, v, data in C.edges(data=True):
            bw = data.get('bandwidth_mbps', 0.0)
            if bw > 0.0:
                qos_weight = data.get('delay_ms', 0.0) + (1000.0 / bw)
                temp_g.add_edge(u, v, qos_weight=qos_weight)

        if not temp_g.has_node(s_str) or not temp_g.has_node(d_str):
            return None
        try:
            path = nx.shortest_path(temp_g, source=s_str, target=d_str, weight='qos_weight')
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    @staticmethod
    def seg_routing(s: str, d: str, C: GraphC, zone_matrix: ZoneMatrix) -> list:
        """
        3. Seg-Routing: Dijkstra delay on C filtered by the zone matrix M.
        Ignores trust and structural masks.
        """
        s_str, d_str = str(s), str(d)
        temp_g = nx.DiGraph()
        for u, v, data in C.edges(data=True):
            if data.get('bandwidth_mbps', 0.0) > 0.0:
                zone_u = C.get_zone(u)
                zone_v = C.get_zone(v)
                if zone_matrix.is_allowed(zone_u, zone_v):
                    temp_g.add_edge(u, v, delay_ms=data.get('delay_ms', 1.0))

        if not temp_g.has_node(s_str) or not temp_g.has_node(d_str):
            return None
        try:
            path = nx.shortest_path(temp_g, source=s_str, target=d_str, weight='delay_ms')
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    @staticmethod
    def zt_routing(s: str, d: str, C: GraphC, pdp: PDP) -> list:
        """
        4. ZT-Routing: Dijkstra delay on C filtered by the PDP trust mask only.
        Ignores micro-segmentation and structural masks.
        """
        s_str, d_str = str(s), str(d)
        zone_s = C.get_zone(s_str)
        zone_d = C.get_zone(d_str)
        theta_path = pdp.get_theta_path(zone_s, zone_d, C)

        temp_g = nx.DiGraph()
        for u, v, data in C.edges(data=True):
            u_str, v_str = str(u), str(v)
            if data.get('bandwidth_mbps', 0.0) > 0.0:
                # Check trust score of both nodes
                zone_u = C.get_zone(u_str)
                zone_v = C.get_zone(v_str)
                t_u = pdp.get_trust_score(u_str, zone_u, C)
                t_v = pdp.get_trust_score(v_str, zone_v, C)
                
                # We use dynamic theta_path, but ensure it doesn't block entirely if network is compromised
                if t_u >= theta_path and t_v >= theta_path:
                    temp_g.add_edge(u_str, v_str, delay_ms=data.get('delay_ms', 1.0))

        if not temp_g.has_node(s_str) or not temp_g.has_node(d_str):
            return None
        try:
            path = nx.shortest_path(temp_g, source=s_str, target=d_str, weight='delay_ms')
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    @staticmethod
    def zt_sr_drl(s: str, d: str, C: GraphC, pdp: PDP, zone_matrix: ZoneMatrix,
                  bridge: CGBridge, agent) -> list:
        """
        5. ZT-SR-VI: Framework sử dụng Value Iteration trên không gian hành động đã lọc.
        Môi trường đã tích hợp điểm phạt CVSS và dữ liệu CAIDA theo QoS.
        """
        s_str, d_str = str(s), str(d)
        
        # We instantiate the ZTEnv on the fly for this routing request
        from src.routing.drl_env import ZTEnv
        from src.routing.drl_agent import train_or_load_agent
        from src.routing.action_mask import ActionMask
        
        struct_mask = bridge.get_struct_mask() if bridge else None
        node_masks = ActionMask.build_node_masks(C, pdp, s_str, d_str, struct_mask)
        E_f = ActionMask.get_feasible_edges(C, node_masks, zone_matrix)
        
        env = ZTEnv(C, pdp, s_str, d_str, E_f, bridge.G if bridge else None)
        
        # Train or load the DRL model
        drl_model = train_or_load_agent(env, force_retrain=False)
        
        # Perform Inference
        obs, _ = env.reset()
        done = False
        truncated = False
        
        # Safety limit to prevent infinite loops
        max_steps = env.n_nodes
        step_count = 0
        
        while not done and not truncated and step_count < max_steps:
            action, _ = drl_model.predict(obs, deterministic=True)
            obs, reward, done, truncated, _ = env.step(action)
            step_count += 1
            
        if done:
            return env.path
        print(f"DRL TRUNCATED! path: {env.path}, last_obs: {obs}, target: {env.target}")
        return None
