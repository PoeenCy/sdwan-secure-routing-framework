import networkx as nx
from src.models.graph_c import GraphC


def _active_graph(graph_c: GraphC) -> nx.DiGraph:
    active = graph_c.__class__()
    active.add_nodes_from(graph_c.nodes(data=True))
    for u, v, data in graph_c.edges(data=True):
        if data.get('bandwidth_mbps', 1.0) > 0.0:
            active.add_edge(u, v, **data)
    return active


def _largest_scc_subgraph(graph_c: GraphC):
    if graph_c.number_of_nodes() == 0:
        return graph_c
    largest = max(nx.strongly_connected_components(graph_c), key=len)
    return graph_c.subgraph(largest).copy()


def compute_enice(graph_c: GraphC) -> float:
    # w(a) is the number of allowed services on edge a.
    # In this simulation, bandwidth_mbps is used as a proxy for w(a).
    return sum(data.get('bandwidth_mbps', 0.0) for _, _, data in graph_c.edges(data=True))


def compute_gcc(graph_c: GraphC) -> float:
    return nx.transitivity(graph_c)


def compute_mpl(graph_c: GraphC) -> float:
    if graph_c.number_of_nodes() <= 1:
        return 0.0
    subgraph = graph_c if nx.is_strongly_connected(graph_c) else _largest_scc_subgraph(graph_c)
    if subgraph.number_of_nodes() <= 1:
        return 0.0
    return nx.average_shortest_path_length(subgraph)


def compute_cd(graph_c: GraphC) -> float:
    if graph_c.number_of_nodes() <= 1:
        return 0.0
    subgraph = graph_c if nx.is_strongly_connected(graph_c) else _largest_scc_subgraph(graph_c)
    if subgraph.number_of_nodes() <= 1:
        return 0.0
    return nx.diameter(subgraph)


def compute_tinr(graph_c: GraphC) -> int:
    tc = nx.transitive_closure(graph_c)
    return tc.number_of_edges()


def compute_avod(graph_c: GraphC) -> float:
    if graph_c.number_of_nodes() == 0:
        return 0.0
    return sum(degree for _, degree in graph_c.out_degree()) / graph_c.number_of_nodes()


def compute_avod_per_node(graph_c: GraphC) -> dict:
    return {node: float(graph_c.out_degree(node)) for node in graph_c.nodes()}


def compute_exposure(graph_c: GraphC) -> dict:
    # TINR is computed with nx.transitive_closure in compute_tinr().
    return ExposureC.calculate_all(graph_c)


class ExposureC:
    @staticmethod
    def calculate_all(C: GraphC) -> dict:
        """
        Calculates the 8 network exposure metrics on Graph C.
        Returns a dict of metrics.
        """
        nodes = list(C.nodes())
        num_nodes = len(nodes)
        if num_nodes == 0:
            return {}

        active = _active_graph(C)
        enice = compute_enice(active)
        gcc = compute_gcc(active)
        mpl = compute_mpl(active)
        cd = compute_cd(active)
        tinr = compute_tinr(active)
        avod = compute_avod(active)
        avod_per_node = compute_avod_per_node(active)
        cl = nx.closeness_centrality(active)
        acc = sum(cl.values()) / num_nodes if num_nodes > 0 else 0.0

        metrics = {
            'ENICE': enice,
            'GCC': gcc,
            'MPL': mpl,
            'CD': cd,
            'TINR': tinr,
            'AVOD': avod,
            'AVOD_PER_NODE': avod_per_node,
            'ACC': acc,
            'CL': cl
        }
        metrics.update({
            'enice': enice,
            'gcc': gcc,
            'mpl': mpl,
            'cd': cd,
            'tinr': tinr,
            'avod': avod,
            'avod_per_node': avod_per_node,
            'acc': acc,
            'cl': cl,
        })
        return metrics
