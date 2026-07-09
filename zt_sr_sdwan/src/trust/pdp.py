import os
import yaml
from src.models.graph_c import GraphC
from .identity import IdentityProvider
from .context import ContextProvider
from .behavior import BehaviorProvider


DEFAULT_TRUST_WEIGHTS = {'w_I': 0.4, 'w_B': 0.3, 'w_C': 0.3}


def compute_trust_score(I_v: float, B_v: float, C_v: float, weights: dict = None) -> float:
    weights = weights or DEFAULT_TRUST_WEIGHTS
    score = (
        weights.get('w_I', 0.4) * I_v
        + weights.get('w_B', 0.3) * B_v
        + weights.get('w_C', 0.3) * C_v
    )
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


class PDP:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.identity = IdentityProvider()
        self.context = ContextProvider(config_dir)
        self.behavior = BehaviorProvider()
        self.theta_zone = {}
        self.use_adaptive_theta = False
        self.k_factor = 1.0
        self.use_avod_context = False
        self.trust_weights = dict(DEFAULT_TRUST_WEIGHTS)
        
        self.load_config()

    def load_config(self):
        policy_path = os.path.join(self.config_dir, "trust_policy.yaml")
        with open(policy_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            self.theta_zone = data.get('theta_zone', {})
            self.use_adaptive_theta = data.get('use_adaptive_theta', False)
            self.k_factor = data.get('k_factor', 1.0)
            self.use_avod_context = data.get('use_avod_context', False)
            self.trust_weights.update(data.get('trust_weights', {}))

    def get_trust_score(self, node_id: str, zone: str, C=None) -> float:
        node_str = str(node_id)
        i = self.identity.get_score(node_str)
        c = self.context.get_score(node_str, zone, C, self.use_avod_context)
        b = self.behavior.get_score(node_str)
        return compute_trust_score(i, b, c, self.trust_weights)

    def _theta_for_zone(self, zone: str) -> float:
        if zone in self.theta_zone:
            return self.theta_zone[zone]
        zone_lower = str(zone).lower()
        for key, value in self.theta_zone.items():
            if str(key).lower() == zone_lower:
                return value
        return 0.50

    def get_theta_path(self, zone_s: str, zone_d: str, C=None) -> float:
        if self.use_adaptive_theta and C is not None and len(C.nodes()) > 0:
            # θ(t) = μ_T(t) + k * σ_T(t)
            import numpy as np
            scores = []
            for node in C.nodes():
                z = C.get_zone(node)
                scores.append(self.get_trust_score(node, z, C))
            mu = float(np.mean(scores))
            sigma = float(np.std(scores))
            raw_theta = mu + self.k_factor * sigma
            return max(0.1, raw_theta)

        theta_s = self._theta_for_zone(zone_s)
        theta_d = self._theta_for_zone(zone_d)
        return max(theta_s, theta_d)

    def evaluate_node(self, node_id: str, zone: str, theta_path: float, C=None) -> bool:
        t_score = self.get_trust_score(node_id, zone, C)
        return t_score >= theta_path

    def evaluate_flow(self, s: str, d: str, path: list, C: GraphC) -> bool:
        """
        Check if trust score of all nodes in path is >= theta_path(s, d).
        Returns True if allowed, False if any node fails the trust check.
        """
        if not path:
            return False
        
        zone_s = C.get_zone(s)
        zone_d = C.get_zone(d)
        theta_path = self.get_theta_path(zone_s, zone_d, C)
        
        for node in path:
            zone = C.get_zone(node)
            if not self.evaluate_node(node, zone, theta_path, C):
                return False
        return True

