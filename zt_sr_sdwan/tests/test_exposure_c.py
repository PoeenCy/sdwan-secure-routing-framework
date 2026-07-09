import networkx as nx

from src.metrics.exposure_c import compute_cd, compute_gcc, compute_mpl, compute_tinr


def test_exposure_metrics_on_fully_connected_graph():
    G = nx.complete_graph(4, create_using=nx.DiGraph())

    assert 0 <= compute_gcc(G) <= 1
    assert compute_mpl(G) > 0
    assert compute_tinr(G) >= G.number_of_edges()
    assert compute_cd(G) >= 1
