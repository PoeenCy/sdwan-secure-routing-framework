import os
import yaml
from src.models.graph_c import GraphC

class ZoneMatrix:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.matrix = {}
        self.load_config()

    def load_config(self):
        matrix_path = os.path.join(self.config_dir, "zone_matrix.yaml")
        with open(matrix_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            self.matrix = data.get('matrix', {})

    def is_allowed(self, zone_u: str, zone_v: str) -> bool:
        """Returns True if communication is allowed between zone_u and zone_v."""
        src_key = self._zone_key(zone_u)
        dst_key = self._zone_key(zone_v, self.matrix.get(src_key, {}))
        return self.matrix.get(src_key, {}).get(dst_key, 0) == 1

    def _zone_key(self, zone: str, matrix: dict = None) -> str:
        matrix = self.matrix if matrix is None else matrix
        if zone in matrix:
            return zone
        zone_lower = str(zone).lower()
        for key in matrix:
            if str(key).lower() == zone_lower:
                return key
        return zone

    def is_mandatory_edge(self, C: GraphC, u: str, v: str) -> bool:
        """
        Returns True if the edge u-v is mandatory (connected to Core or IT).
        Core<->* and IT<->* are business whitelisted and cannot be cut.
        """
        zone_u = C.get_zone(u)
        zone_v = C.get_zone(v)
        return str(zone_u).lower() in {'core', 'it'} or str(zone_v).lower() in {'core', 'it'}

    def filter_edges(self, C: GraphC) -> list:
        """Returns the list of edges in C that are allowed by the zone matrix."""
        allowed_edges = []
        for u, v in C.edges():
            zone_u = C.get_zone(u)
            zone_v = C.get_zone(v)
            if self.is_allowed(zone_u, zone_v):
                allowed_edges.append((u, v))
        return allowed_edges
