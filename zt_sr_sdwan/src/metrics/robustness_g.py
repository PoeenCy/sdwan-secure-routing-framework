import networkx as nx
from src.models.graph_g import GraphG


def _roots(G: GraphG) -> list:
    roots = [n for n in G.nodes() if G.nodes[n].get('is_root')]
    if not roots and hasattr(G, 'entry_nodes'):
        roots = list(G.entry_nodes)
    return roots


def _targets(G: GraphG) -> list:
    targets = [n for n in G.nodes() if G.nodes[n].get('is_target')]
    if not targets and hasattr(G, 'target_nodes'):
        targets = list(G.target_nodes)
    return targets


def compute_bn(graph_g: GraphG) -> dict:
    """
    Basta-style attack-path betweenness:
    BN(n) = sum_{r in R_G, l in L_G} NSP_rl(n) / NSP_rl.

    The ratio is computed per root-target pair first, then accumulated.
    Root and target endpoints are excluded; only intermediate nodes count.
    """
    roots = _roots(graph_g)
    targets = _targets(graph_g)
    bn = {n: 0.0 for n in graph_g.nodes()}

    for root in roots:
        for target in targets:
            if root == target:
                continue
            if not nx.has_path(graph_g, root, target):
                continue
            paths = list(nx.all_shortest_paths(graph_g, root, target))
            nsp_rl = len(paths)
            if nsp_rl == 0:
                continue
            for path in paths:
                for node in path[1:-1]:
                    bn[node] += 1.0 / nsp_rl

    return bn


def compute_mspl(graph_g: GraphG):
    lengths = []
    for root in _roots(graph_g):
        for target in _targets(graph_g):
            if root == target:
                continue
            if nx.has_path(graph_g, root, target):
                lengths.append(nx.shortest_path_length(graph_g, root, target))
    return min(lengths) if lengths else float('inf')


def compute_nsp(graph_g: GraphG) -> int:
    count = 0
    for root in _roots(graph_g):
        for target in _targets(graph_g):
            if root == target:
                continue
            if nx.has_path(graph_g, root, target):
                count += len(list(nx.all_shortest_paths(graph_g, root, target)))
    return count


def compute_cmpl(graph_g: GraphG, mspl) -> int:
    if mspl == float('inf'):
        return 0
    count = 0
    for root in _roots(graph_g):
        for target in _targets(graph_g):
            if root == target:
                continue
            if nx.has_path(graph_g, root, target):
                if nx.shortest_path_length(graph_g, root, target) == mspl:
                    count += len(list(nx.all_shortest_paths(graph_g, root, target)))
    return count


def compute_cmc(graph_g: GraphG) -> int:
    return len(_roots(graph_g))


def compute_mod(graph_g: GraphG) -> int:
    targets = _targets(graph_g)
    if not targets:
        return 0
    return max(graph_g.out_degree(node) for node in targets)


def compute_aod(graph_g: GraphG) -> float:
    targets = _targets(graph_g)
    if not targets:
        return 0.0
    return sum(graph_g.out_degree(node) for node in targets) / len(targets)


def compute_ab(graph_g: GraphG, bn_dict: dict) -> float:
    """Average BN over privilege/target nodes L_G."""
    targets = _targets(graph_g)
    if not targets:
        return 0.0
    return sum(bn_dict.get(node, 0.0) for node in targets) / len(targets)


def compute_robustness(graph_g: GraphG) -> dict:
    R_G = [n for n in graph_g.nodes() if graph_g.nodes[n].get('is_root')]
    L_G = [n for n in graph_g.nodes() if graph_g.nodes[n].get('is_target')]
    metrics = RobustnessG.calculate_all(graph_g)
    metrics.setdefault('CMC', len(R_G))
    metrics.setdefault('cmc', len(R_G))
    metrics.setdefault('R_G', R_G)
    metrics.setdefault('L_G', L_G)
    return metrics


class RobustnessG:
    @staticmethod
    def calculate_all(G: GraphG) -> dict:
        """
        Calculates the 8 attack-path robustness metrics on Graph G.
        Returns a dict of metrics.
        """
        if G.number_of_nodes() == 0:
            return {}

        bn = compute_bn(G)
        mspl = compute_mspl(G)
        nsp = compute_nsp(G)
        cmpl = compute_cmpl(G, mspl)
        cmc = compute_cmc(G)
        mod = compute_mod(G)
        aod = compute_aod(G)
        ab = compute_ab(G, bn)

        for node in G.nodes():
            G.nodes[node]['bn'] = bn.get(node, 0.0)
            G.nodes[node]['mod'] = float(G.out_degree(node))

        metrics = {
            'MOD': mod,
            'BN': bn,
            'MSPL': mspl,
            'NSP': nsp,
            'CMPL': cmpl,
            'CMC': cmc,
            'AOD': aod,
            'AB': ab,
        }
        metrics.update({
            'mod': mod,
            'bn': bn,
            'mspl': mspl,
            'nsp': nsp,
            'cmpl': cmpl,
            'cmc': cmc,
            'aod': aod,
            'ab': ab,
        })
        return metrics
