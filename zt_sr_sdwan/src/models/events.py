class CUpdated:
    def __init__(self, edge: tuple, attr: str = None, old_value=None, new_value=None, is_cut: bool = False):
        self.edge = edge  # tuple (u, v)
        self.attr = attr  # e.g., 'delay_ms', 'bandwidth_mbps'
        self.old_value = old_value
        self.new_value = new_value
        self.is_cut = is_cut

    def __repr__(self):
        if self.is_cut:
            return f"CUpdated(Cut edge {self.edge})"
        return f"CUpdated(Edge {self.edge} attribute '{self.attr}' changed from {self.old_value} to {self.new_value})"


class TrustUpdated:
    def __init__(self, node: str, component: str, old_value: float, new_value: float):
        self.node = node  # node ID
        self.component = component  # 'I', 'C', 'B'
        self.old_value = old_value
        self.new_value = new_value

    def __repr__(self):
        return f"TrustUpdated(Node {self.node} component '{self.component}' changed from {self.old_value} to {self.new_value})"
