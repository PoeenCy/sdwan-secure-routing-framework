from src.metrics.robustness_g import RobustnessG
from src.models.graph_g import GraphG


def test_robustness_uses_attack_path_semantics():
    G = GraphG()
    G.add_node('r1', is_root=True, is_target=False)
    G.add_node('a', is_root=False, is_target=False)
    G.add_node('b', is_root=False, is_target=False)
    G.add_node('l1', is_root=False, is_target=True)
    G.add_node('l2', is_root=False, is_target=True)
    G.entry_nodes = {'r1'}
    G.target_nodes = {'l1', 'l2'}
    G.add_edges_from([
        ('r1', 'a'),
        ('a', 'l1'),
        ('r1', 'b'),
        ('b', 'l1'),
        ('r1', 'l2'),
    ])

    metrics = RobustnessG.calculate_all(G)
    bn = metrics['BN']

    assert metrics['MSPL'] == 1
    assert metrics['NSP'] == 3
    assert metrics['CMPL'] == 1
    assert metrics['CMC'] == 1
    assert abs(bn['a'] - 1 / 2) < 0.01
    assert abs(bn['b'] - 1 / 2) < 0.01
    assert bn['l2'] == 0.0
    assert metrics['MOD'] == max(G.out_degree('l1'), G.out_degree('l2'))
    assert metrics['AB'] == (bn['l1'] + bn['l2']) / 2


def test_bn_counts_only_intermediate_nodes_for_each_root_target_pair():
    G = GraphG()
    G.add_node('14', is_root=True, is_target=False)
    G.add_node('12', is_root=False, is_target=False)
    G.add_node('0', is_root=False, is_target=False)
    G.add_node('7', is_root=False, is_target=True)
    G.entry_nodes = {'14'}
    G.target_nodes = {'7'}
    G.add_edges_from([
        ('14', '12'),
        ('12', '0'),
        ('0', '7'),
    ])

    metrics = RobustnessG.calculate_all(G)
    bn = metrics['BN']

    assert metrics['NSP'] == 1
    assert bn['14'] == 0.0
    assert bn['7'] == 0.0
    assert bn['12'] == 1.0
    assert bn['0'] == 1.0
    assert metrics['AB'] == 0.0
