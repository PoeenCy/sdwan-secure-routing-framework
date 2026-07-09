import os
import json
import random
from typing import List, Dict
from audit_system.models.dataset import VulnerabilityData
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class NVDFetcher:
    def __init__(self, use_mock: bool = False):
        self.data_path = Path("d:/SD_WAN_Secure_Routing/zt_sr_sdwan/data/nvd/cve_dataset.json")

    def fetch_vulnerabilities(self, zone_device_map: Dict[str, str], nodes: List[str], node_zones: Dict[str, str]) -> List[VulnerabilityData]:
        vulns = []
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Missing NVD dataset at {self.data_path}. Please run scripts/download_datasets.py first.")
            
        with open(self.data_path, "r", encoding="utf-8") as f:
            cve_db = json.load(f)
            
        for node in nodes:
            zone = node_zones.get(node, "Core")
            device = zone_device_map.get(zone, "router")
            
            cve_list = cve_db.get(device)
            if not cve_list or len(cve_list) == 0:
                raise KeyError(f"No CVE data found in static dataset for device: {device}")
                
            # Randomly sample one CVE from the massive dataset for this specific node
            # This creates a highly diverse and realistic vulnerability topology
            vuln_info = random.choice(cve_list)
                
            patch_status = 1.0 if zone == "Core" else 0.0
            
            vulns.append(VulnerabilityData(
                node_id=str(node),
                zone=zone,
                cve_id=vuln_info["cve_id"],
                cvss_score=vuln_info["cvss"],
                patch_status=patch_status,
                device_type=device
            ))
        return vulns
