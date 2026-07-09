from src.models.graph_c import GraphC
from src.trust.pdp import PDP
from src.microseg.zone_matrix import ZoneMatrix


class ActionMask:
    @staticmethod
    def build_node_masks(C: GraphC, pdp: PDP, s: str, d: str, struct_mask: dict = None) -> dict:
        """
        Builds the composite mask for all nodes in the context of a flow from s to d.
        Returns a dictionary of {node_id: bool} indicating if the node is allowed (True) or blocked (False).
        """
        masks = {}
        zone_s = C.get_zone(s)
        zone_d = C.get_zone(d)
        theta_path = pdp.get_theta_path(zone_s, zone_d, C)

        for node in C.nodes():
            node_str = str(node)
            zone_n = C.get_zone(node_str)

            # 1. Trust Mask
            t_score = pdp.get_trust_score(node_str, zone_n, C)
            m_trust = (t_score >= theta_path)

            # 2. Structural Mask
            if struct_mask is not None:
                m_struct = struct_mask.get(node_str, True)
            else:
                m_struct = True

            # Exempt Core backbone nodes and source/destination nodes from structural blocking
            if str(zone_n).lower() == 'core' or node_str == str(s) or node_str == str(d):
                m_struct = True

            # Composite Mask
            masks[node_str] = m_trust and m_struct

        return masks

    @staticmethod
    def get_feasible_edges(C: GraphC, node_masks: dict, zone_matrix: ZoneMatrix) -> set:
        """
        Filters edges of C to find the set of feasible edges E_f.
        E_f consists of edges (u, v) where:
        - The edge has bandwidth > 0 (it is not cut — structural, not QoS)
        - Communication between zone(u) and zone(v) is allowed by micro-segmentation
        - Both nodes u and v are allowed by the node masks (trust + structure)

        NOTE: QoS degradation (low BW) is NOT a hard-block criterion in E_f.
        QoS is handled via the reward function (reciprocal BW penalty) which makes
        ZT-SR-VI prefer high-BW paths without refusing to route when no better path exists.
        Only a completely cut edge (BW=0) is excluded, as it is physically unreachable.
        """
        feasible = set()
        for u, v in C.edges():
            u_str, v_str = str(u), str(v)

            # Exclude physically cut edges (BW=0) — not a QoS threshold, just reachability
            bw = C[u_str][v_str].get('bandwidth_mbps', 0.0)
            if bw <= 0.0:
                continue

            # Check Zone Matrix (micro-segmentation policy — security constraint)
            zone_u = C.get_zone(u_str)
            zone_v = C.get_zone(v_str)
            if not zone_matrix.is_allowed(zone_u, zone_v):
                continue

            # Check Node Masks (trust + structural — security constraints)
            if not node_masks.get(u_str, True) or not node_masks.get(v_str, True):
                continue

            feasible.add((u_str, v_str))
        return feasible

    @staticmethod
    def compute_qos_compliance(path: list, C: GraphC, bw_min_threshold: float = 20.0) -> dict:
        """
        Separate QoS monitoring — does NOT affect routing decisions.
        Returns a report on whether the chosen path meets QoS requirements.
        Called AFTER routing to flag degraded paths, not to block them.

        Returns:
          {
            'compliant': bool,
            'bottleneck_bw': float,
            'degraded_edges': list of (u, v, bw)
          }
        """
        if not path or len(path) < 2:
            return {'compliant': True, 'bottleneck_bw': float('inf'), 'degraded_edges': []}

        degraded = []
        min_bw = float('inf')
        for i in range(len(path) - 1):
            u, v = str(path[i]), str(path[i + 1])
            if C.has_edge(u, v):
                bw = C[u][v].get('bandwidth_mbps', 0.0)
                min_bw = min(min_bw, bw)
                if bw < bw_min_threshold:
                    degraded.append((u, v, bw))

        return {
            'compliant': len(degraded) == 0,
            'bottleneck_bw': min_bw,
            'degraded_edges': degraded,
        }
