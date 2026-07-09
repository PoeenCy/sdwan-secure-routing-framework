import networkx as nx

class FeasiblePaths:
    @staticmethod
    def find_paths(s: str, d: str, E_f: set, cutoff: int = 8) -> list:
        """
        Finds all simple paths from s to d on the graph formed by feasible edges E_f.
        Uses a hop cutoff to prevent search space explosion.
        Returns a list of lists representing paths.
        """
        s_str, d_str = str(s), str(d)
        if not E_f:
            return []
            
        # Build temporary subgraph
        subgraph = nx.DiGraph()
        subgraph.add_edges_from(E_f)
        
        if not subgraph.has_node(s_str) or not subgraph.has_node(d_str):
            return []

        try:
            paths = list(nx.all_simple_paths(subgraph, source=s_str, target=d_str, cutoff=cutoff))
            return paths
        except Exception:
            return []
