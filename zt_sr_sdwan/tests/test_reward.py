from src.models.graph_c import GraphC
from src.models.graph_g import GraphG
from src.routing.reward import compute_reward


def test_compute_reward_penalizes_chokepoints_and_roots():
    C = GraphC()
    for node in ['A', 'B', 'X', 'R']:
        C.add_node(node)
    C.add_edge('A', 'B', bandwidth_mbps=500.0, delay_ms=10.0)
    C.add_edge('A', 'X', bandwidth_mbps=500.0, delay_ms=10.0)
    C.add_edge('A', 'R', bandwidth_mbps=500.0, delay_ms=10.0)

    G = GraphG()
    G.add_node('B', bn=0.0, mod=0.0, is_root=False, on_shortest_attack_path=False)
    G.add_node('X', bn=0.8, mod=0.0, is_root=False, on_shortest_attack_path=True)
    G.add_node('R', bn=0.0, mod=0.0, is_root=True, on_shortest_attack_path=True)

    hyperparams = {
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
    }

    reward_safe = compute_reward('A', 'B', C, G, ['A'], hyperparams)
    reward_choke = compute_reward('A', 'X', C, G, ['A'], hyperparams)
    reward_root = compute_reward('A', 'R', C, G, ['A'], hyperparams)

    assert reward_safe > reward_choke
    assert reward_safe > reward_root
