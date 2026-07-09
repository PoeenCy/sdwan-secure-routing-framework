import os
import yaml
from src.models.graph_g import parse_cvss_fields

class ContextProvider:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.profiles = {}
        self.node_profiles = {}
        self.patch_factors = {}  # Dynamic tracking of patch factors per node
        self.load_config()

    def load_config(self):
        cve_path = os.path.join(self.config_dir, "cve_profiles.yaml")
        with open(cve_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        if 'nodes' in data:
            self.node_profiles = data.get('nodes', {}) or {}
            self.profiles = self._build_zone_profiles(self.node_profiles)
        else:
            self.node_profiles = {}
            self.profiles = data.get('cve_profiles', {}) or {}

    def _normalize_cve(self, cve: dict) -> dict:
        normalized = dict(cve or {})
        if normalized.get('cvss_vector'):
            normalized.update(parse_cvss_fields(normalized['cvss_vector']))
        normalized['cvss_score'] = float(
            normalized.get('cvss_score', normalized.get('cvss', 0.0)) or 0.0
        )
        return normalized

    def _build_zone_profiles(self, node_profiles: dict) -> dict:
        zone_profiles = {}
        for profile in node_profiles.values():
            zone = profile.get('zone', 'Unknown')
            cves = [self._normalize_cve(cve) for cve in profile.get('cve_list', [])]
            cvss_max = max((cve.get('cvss_score', 0.0) for cve in cves), default=0.0)
            current = zone_profiles.setdefault(zone, {
                'cve': None,
                'cvss': 0.0,
                'patch_factor': 1.0,
            })
            if cvss_max > current['cvss']:
                current['cvss'] = cvss_max
                current['cve'] = cves[0].get('cve_id') if cves else None
        return zone_profiles

    def _zone_profile(self, zone: str) -> dict:
        if zone in self.profiles:
            return self.profiles[zone]
        zone_lower = str(zone).lower()
        for key, profile in self.profiles.items():
            if str(key).lower() == zone_lower:
                return profile
        return {"cve": None, "cvss": 0.0, "patch_factor": 1.0}

    def _node_profile(self, node_id: str) -> dict:
        return self.node_profiles.get(str(node_id), {})

    def get_score(self, node_id: str, zone: str, C=None, use_avod_context: bool = False) -> float:
        node_str = str(node_id)
        if use_avod_context and C is not None:
            # Get all unique zones in C
            zones = set(C.get_zone(n) for n in C.nodes())
            if not zones:
                return 1.0
            
            # Calculate AVOD for each zone
            zone_avods = {}
            for z in zones:
                nodes_in_z = [n for n in C.nodes() if C.get_zone(n) == z]
                if not nodes_in_z:
                    zone_avods[z] = 0.0
                    continue
                out_degs = []
                for n in nodes_in_z:
                    deg = sum(1 for v in C.successors(n) if C[n][v].get('bandwidth_mbps', 0.0) > 0.0)
                    out_degs.append(deg)
                zone_avods[z] = sum(out_degs) / len(nodes_in_z)
                
            max_avod = max(zone_avods.values()) if zone_avods else 0.0
            zone_key = next((z for z in zone_avods if str(z).lower() == str(zone).lower()), zone)
            if max_avod > 0.0:
                normalized_avod = zone_avods.get(zone_key, 0.0) / max_avod
            else:
                normalized_avod = 0.0
                
            score = 1.0 - normalized_avod
            return max(0.0, min(1.0, score))

        # CVE-based fallback for non-AVOD contexts. Zone-level profiles are kept
        # mutable for legacy scripts that zero CVSS to create a clean scenario.
        profile = self._zone_profile(zone)
        cvss = profile.get("cvss", 0.0)
        
        # Get dynamic patch factor, fallback to default profile patch factor
        patch_factor = self.patch_factors.get(node_str, profile.get("patch_factor", 1.0))
        
        score = patch_factor * (1.0 - cvss / 10.0)
        return max(0.0, min(1.0, score))

    def set_patch_factor(self, node_id: str, patch_factor: float):
        self.patch_factors[str(node_id)] = float(patch_factor)


ContextTrust = ContextProvider
