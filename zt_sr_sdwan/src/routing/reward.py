from pathlib import Path

import yaml

from src.models.graph_c import GraphC
from src.microseg.bridge_cg import CGBridge


DEFAULT_REWARD_HYPERPARAMS = {
    'alpha': 0.30,
    'beta': 0.30,
    'gamma': 0.20,
    'mu': 0.10,
    'nu': 0.10,
    'lambda1': 0.50,
    'lambda2': 0.50,
    'theta_bn': 0.30,
    'bw_max': 1000.0,
    'delay_max': 100.0,
    # QoS-aware: reciprocal BW penalty. bw_ref = congestion threshold (Mbps).
    # Reward contribution: -alpha * bw_ref / (BW + bw_ref)
    # At BW >> bw_ref: contribution -> 0 (good link, small penalty)
    # At BW =  bw_ref: contribution = -alpha * 0.5
    # At BW << bw_ref: contribution -> -alpha (congested, max penalty)
    'bw_ref': 50.0,
    # E_f bandwidth threshold: edges below this are treated as congested by ZT-SR-VI
    'bw_min_threshold': 20.0,
}


def load_reward_hyperparams(config_path: str = None) -> dict:
    params = dict(DEFAULT_REWARD_HYPERPARAMS)
    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / 'config' / 'hyperparams.yaml'
    config_path = Path(config_path)
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        params.update(data.get('reward', {}))
    return params


def _node_attrs(graph, node) -> dict:
    if graph is not None and graph.has_node(node):
        return graph.nodes[node]
    return {}


def compute_delta_mspl(next_node, path_so_far, graph_g) -> float:
    attrs = _node_attrs(graph_g, next_node)
    if attrs.get('is_root', False):
        return -1.0
    if attrs.get('on_shortest_attack_path', False):
        return 0.0
    return 1.0


def compute_nsp_delta(next_node, graph_g, hyperparams: dict) -> float:
    attrs = _node_attrs(graph_g, next_node)
    bn_next = attrs.get('bn', 0.0)
    theta_bn = hyperparams.get('theta_bn', 0.30)
    return 1.0 if bn_next > theta_bn else 0.0


def compute_reward(current_node, next_node, graph_c, graph_g=None,
                   path_so_far=None, hyperparams=None) -> float:
    """
    R_t = -alpha * QoS_BW_penalty - beta*Delay - gamma*MaliciousPenalty(n)
          + mu*DeltaMSPL(p) - nu*NSP_delta(p)

    QoS BW penalty: reciprocal form = bw_ref / (BW + bw_ref)
      - Ranges in [0, 1], concave (sensitive to low BW).
      - At BW >> bw_ref: penalty -> 0 (good link).
      - At BW =  bw_ref: penalty = 0.5 (threshold).
      - At BW -> 0:      penalty -> 1 (congested, max penalty).
    """
    params = dict(DEFAULT_REWARD_HYPERPARAMS)
    if hyperparams:
        params.update(hyperparams)

    edge = graph_c[current_node][next_node]
    bw = edge.get('bandwidth_mbps', 0.0)
    bw_ref = params.get('bw_ref', 50.0)
    delay_max = params.get('delay_max', 100.0) or 100.0

    # Reciprocal QoS BW penalty: sensitive to congestion
    bw_penalty = bw_ref / (bw + bw_ref)  # in [0, 1]
    norm_delay = edge.get('delay_ms', 0.0) / delay_max

    g_attrs = _node_attrs(graph_g, next_node)
    c_attrs = _node_attrs(graph_c, next_node)
    mod_n = g_attrs.get('mod', graph_g.out_degree(next_node) if graph_g is not None and graph_g.has_node(next_node) else c_attrs.get('mod', 0.0))
    bn_n = g_attrs.get('bn', c_attrs.get('bn', 0.0))
    malicious_penalty = params['lambda1'] * mod_n + params['lambda2'] * bn_n

    delta_mspl = compute_delta_mspl(next_node, path_so_far or [], graph_g)
    nsp_delta = compute_nsp_delta(next_node, graph_g, params)

    return (
        - params['alpha'] * bw_penalty       # concave QoS BW: penalise congestion
        - params['beta'] * norm_delay         # latency penalty
        - params['gamma'] * malicious_penalty # security penalty
        + params['mu'] * delta_mspl           # attack-path length reward
        - params['nu'] * nsp_delta            # BN avoidance penalty
    )

class RewardCalculator:
    def __init__(self, hyperparams: dict = None, config_path: str = None, **overrides):
        self.hyperparams = load_reward_hyperparams(config_path)
        if hyperparams:
            self.hyperparams.update(hyperparams)
        for key, value in overrides.items():
            if key in self.hyperparams and value is not None:
                self.hyperparams[key] = value

    def calculate_path_reward(self, path: list, C: GraphC, bridge: CGBridge) -> float:
        """
        Calculates the reward score R_t(p) for a path in C.
        """
        if not path or len(path) < 2:
            return -1e9

        graph_g = bridge.G if bridge is not None else None
        reward = 0.0
        for i in range(len(path) - 1):
            u, v = str(path[i]), str(path[i+1])
            if not C.has_edge(u, v):
                return -1e9  # Invalid path in C
            reward += compute_reward(u, v, C, graph_g, path[:i+1], self.hyperparams)
        return reward
