from pathlib import Path

import networkx as nx
import yaml

from src.models.graph_c import GraphC


def parse_cvss_fields(cvss_vector: str) -> dict:
    """
    Parse CVSS v3 vector fields used by the attack graph.
    Example: AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H
    """
    mapping = {
        'AV': {'N': 'NETWORK', 'A': 'ADJACENT', 'L': 'LOCAL', 'P': 'PHYSICAL'},
        'PR': {'N': 'NONE', 'L': 'LOW', 'H': 'HIGH'},
        'S': {'U': 'UNCHANGED', 'C': 'CHANGED'},
    }
    parsed = {}
    if not cvss_vector:
        return {
            'access_vector': 'NETWORK',
            'privilege_required': 'NONE',
            'scope': 'UNCHANGED',
        }

    for part in cvss_vector.split('/'):
        if ':' not in part:
            continue
        key, value = part.split(':', 1)
        if key in mapping:
            parsed[key] = mapping[key].get(value, value)

    return {
        'access_vector': parsed.get('AV', 'NETWORK'),
        'privilege_required': parsed.get('PR', 'NONE'),
        'scope': parsed.get('S', 'UNCHANGED'),
    }


def _normalize_cve(cve: dict) -> dict:
    normalized = dict(cve or {})
    if normalized.get('cvss_vector'):
        normalized.update(parse_cvss_fields(normalized['cvss_vector']))
    normalized['access_vector'] = str(
        normalized.get('access_vector', 'NETWORK')
    ).upper()
    normalized['privilege_required'] = str(
        normalized.get('privilege_required', 'NONE')
    ).upper()
    normalized['scope'] = str(normalized.get('scope', 'UNCHANGED')).upper()
    normalized['cvss_score'] = float(
        normalized.get('cvss_score', normalized.get('cvss', 0.0)) or 0.0
    )
    return normalized


def load_cve_profiles(path: str = None) -> dict:
    """Load node-keyed CVE profiles and parse AV/PR/S fields from vectors."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / 'config' / 'cve_profiles.yaml'
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    if 'nodes' in data:
        profiles = data['nodes'] or {}
    elif 'cve_profiles' in data:
        # Legacy zone-keyed format. Kept for compatibility with older tests.
        profiles = {}
        for zone, profile in (data.get('cve_profiles') or {}).items():
            cve_id = profile.get('cve') if isinstance(profile, dict) else None
            cvss = profile.get('cvss', 0.0) if isinstance(profile, dict) else 0.0
            profiles[zone] = {
                'zone': zone,
                'cve_list': [] if not cve_id else [{
                    'cve_id': cve_id,
                    'cvss_score': cvss,
                    'access_vector': 'NETWORK',
                    'privilege_required': 'NONE',
                    'scope': 'UNCHANGED',
                }],
            }
    else:
        profiles = data

    normalized_profiles = {}
    for node, profile in (profiles or {}).items():
        if isinstance(profile, list):
            cve_list = profile
            profile_dict = {'cve_list': cve_list}
        else:
            profile_dict = dict(profile or {})
            cve_list = profile_dict.get('cve_list', [])
        profile_dict['cve_list'] = [_normalize_cve(cve) for cve in cve_list]
        normalized_profiles[str(node)] = profile_dict
    return normalized_profiles


def _cves_for_node(cve_profiles: dict, node, zone: str = None) -> list:
    if not cve_profiles:
        return []

    node_key = str(node)
    if 'nodes' in cve_profiles:
        profile = (cve_profiles.get('nodes') or {}).get(node_key, {})
    else:
        profile = cve_profiles.get(node_key)
        if profile is None and zone is not None:
            profile = cve_profiles.get(zone)

    if isinstance(profile, list):
        cve_list = profile
    elif isinstance(profile, dict):
        cve_list = profile.get('cve_list', [])
    else:
        cve_list = []

    return [_normalize_cve(cve) for cve in cve_list]


def _is_exploitable(cve: dict) -> bool:
    return (
        str(cve.get('access_vector', '')).upper() == 'NETWORK'
        and str(cve.get('privilege_required', '')).upper() in {'NONE', 'LOW'}
    )


def _is_root_cve(cve: dict) -> bool:
    return (
        str(cve.get('access_vector', '')).upper() == 'NETWORK'
        and str(cve.get('privilege_required', '')).upper() == 'NONE'
    )


def mark_attack_path_nodes(graph_g):
    """
    Mark nodes that lie on a shortest attack path from any root to any target.
    """
    roots = [n for n in graph_g.nodes() if graph_g.nodes[n].get('is_root')]
    targets = [n for n in graph_g.nodes() if graph_g.nodes[n].get('is_target')]
    on_path = set()

    for root in roots:
        for target in targets:
            if root == target:
                continue
            if nx.has_path(graph_g, root, target):
                for path in nx.all_shortest_paths(graph_g, root, target):
                    on_path.update(path)

    for node in graph_g.nodes():
        graph_g.nodes[node]['on_shortest_attack_path'] = node in on_path

    return on_path

class GraphG(nx.DiGraph):
    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.entry_nodes = set()
        self.target_nodes = set()

    def generate_from_c(self, C: GraphC, cve_profiles: dict = None):
        """
        Generate attack graph G from active connectivity C and node CVEs.
        An edge u->v exists only when u can reach v and v has an exploitable CVE.
        """
        if cve_profiles is None:
            cve_profiles = load_cve_profiles()

        self.clear()
        
        roots = set()
        targets = set()

        for node, attrs in C.nodes(data=True):
            zone = attrs.get('zone', C.get_zone(node) if hasattr(C, 'get_zone') else None)
            node_cves = _cves_for_node(cve_profiles, node, zone)
            cvss_max = max((cve.get('cvss_score', 0.0) for cve in node_cves), default=0.0)
            zone_lower = str(zone or '').lower()

            is_root = (
                zone_lower == 'dmz'
                or any(_is_root_cve(cve) for cve in node_cves)
                or str(attrs.get('connection_status', '')).upper() == 'ISOLATED'
            )
            is_target = zone_lower in {'fin', 'core'}

            if is_root:
                roots.add(node)
            if is_target:
                targets.add(node)

            node_attrs = dict(attrs)
            node_attrs.update({
                'zone': zone,
                'is_root': is_root,
                'is_target': is_target,
                'cvss_max': cvss_max,
            })
            self.add_node(node, **node_attrs)
            
        for u, v, attrs in C.edges(data=True):
            if attrs.get('bandwidth_mbps', 0.0) <= 0.0:
                continue
            target_zone = C.nodes[v].get('zone', C.get_zone(v) if hasattr(C, 'get_zone') else None)
            exploitable_cves = [
                cve for cve in _cves_for_node(cve_profiles, v, target_zone)
                if _is_exploitable(cve)
            ]
            if not exploitable_cves:
                continue
            self.add_edge(
                u,
                v,
                max_cvss=max(cve['cvss_score'] for cve in exploitable_cves),
                exploitable_cve_count=len(exploitable_cves),
                source_zone=C.nodes[u].get('zone', C.get_zone(u) if hasattr(C, 'get_zone') else None),
                target_zone=target_zone,
            )

        critical_nodes = roots & targets
        for node in self.nodes():
            self.nodes[node]['is_critical'] = node in critical_nodes

        self.entry_nodes = roots
        self.target_nodes = targets
        self.graph['critical_exposure_nodes'] = sorted(critical_nodes, key=str)
        if critical_nodes:
            print(f"WARNING: {len(critical_nodes)} nodes are both entry points and targets")
        mark_attack_path_nodes(self)
        return self
