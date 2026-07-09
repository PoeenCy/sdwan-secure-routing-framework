import numpy as np
from src.models.graph_c import GraphC
from src.models.graph_g import GraphG
from src.metrics.robustness_g import RobustnessG
from src.microseg.zone_matrix import ZoneMatrix

class CGBridge:
    def __init__(self, zone_matrix: ZoneMatrix, k: float = 1.0):
        self.zone_matrix = zone_matrix
        self.k = k
        self.G = GraphG()
        self.bn_scores = {}
        self.mod_scores = {}
        
        self.mu_bn = 0.0
        self.sigma_bn = 0.0
        self.theta_bn = 0.0
        
        self.mu_mod = 0.0
        self.sigma_mod = 0.0
        self.theta_mod = 0.0

    def regenerate_g(self, C: GraphC):
        """Regenerate the Attack Graph G from Connectivity Graph C and update structural metrics."""
        self.G.generate_from_c(C)
        self.update_structural_thresholds()

    def update_structural_thresholds(self):
        metrics = RobustnessG.calculate_all(self.G)
        self.bn_scores = metrics.get('BN', {})
        
        # MOD scores for G (out degrees)
        self.mod_scores = {node: float(self.G.out_degree(node)) for node in self.G.nodes()}

        nodes = list(self.G.nodes())
        if not nodes:
            return

        # 1. Betweenness Centrality (BN) Z-score
        bn_values = list(self.bn_scores.values())
        self.mu_bn = float(np.mean(bn_values))
        self.sigma_bn = float(np.std(bn_values))
        self.theta_bn = self.mu_bn + self.k * self.sigma_bn

        # 2. Max Out-Degree (MOD) Z-score
        mod_values = list(self.mod_scores.values())
        self.mu_mod = float(np.mean(mod_values))
        self.sigma_mod = float(np.std(mod_values))
        self.theta_mod = self.mu_mod + self.k * self.sigma_mod

    def get_struct_mask(self) -> dict:
        """
        Returns a dictionary {node_id: bool} representing M_t^struct.
        True means node is within thresholds (safe), False means it is an outlier.
        """
        mask = {}
        for node in self.G.nodes():
            node_str = str(node)
            bn = self.bn_scores.get(node_str, 0.0)
            mod = self.mod_scores.get(node_str, 0.0)
            
            # Safe if: BN <= theta_BN AND MOD <= theta_MOD
            # To handle cases where sigma is 0 and theta is 0, we allow minor epsilon
            is_safe_bn = (bn <= self.theta_bn + 1e-9)
            is_safe_mod = (mod <= self.theta_mod + 1e-9)
            
            mask[node_str] = is_safe_bn and is_safe_mod
        return mask

    def perform_step_5c_mitigation(self, C: GraphC, overlay_manager) -> list:
        """
        Step 5c bounded cut.
        Identifies nodes that are BN outliers (BN > theta_BN) and cuts their
        non-mandatory incoming/outgoing edges.
        Returns a list of cut edges (u, v).
        """
        cut_edges = []
        outliers = []
        
        # Identify BN outliers
        for node in self.G.nodes():
            node_str = str(node)
            bn = self.bn_scores.get(node_str, 0.0)
            if bn > self.theta_bn + 1e-9:
                outliers.append(node_str)

        # For each outlier, look at its edges in C and try to cut
        for outlier in outliers:
            # Look at incoming edges (u, outlier)
            incoming = list(C.predecessors(outlier))
            for u in incoming:
                u_str = str(u)
                # Check if it is an active edge and NOT mandatory
                if C[u_str][outlier].get('bandwidth_mbps', 0.0) > 0.0:
                    if not self.zone_matrix.is_mandatory_edge(C, u_str, outlier):
                        print(f"[Bridge C-G] Step 5c: Cutting non-mandatory edge ({u_str}, {outlier}) to isolate BN outlier {outlier}")
                        overlay_manager.cut_edge(u_str, outlier)
                        cut_edges.append((u_str, outlier))

            # Look at outgoing edges (outlier, v)
            outgoing = list(C.successors(outlier))
            for v in outgoing:
                v_str = str(v)
                # Check if it is an active edge and NOT mandatory
                if C[outlier][v_str].get('bandwidth_mbps', 0.0) > 0.0:
                    if not self.zone_matrix.is_mandatory_edge(C, outlier, v_str):
                        print(f"[Bridge C-G] Step 5c: Cutting non-mandatory edge ({outlier}, {v_str}) to isolate BN outlier {outlier}")
                        overlay_manager.cut_edge(outlier, v_str)
                        cut_edges.append((outlier, v_str))
                        
        return cut_edges
