import networkx as nx
from pathlib import Path
from audit_system.models.dataset import UnifiedDataset
from audit_system.dataset.caida_fetcher import CAIDAFetcher
from audit_system.dataset.nvd_fetcher import NVDFetcher
from audit_system.dataset.mapper import DatasetMapper


class DatasetBuilder:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.caida_fetcher = CAIDAFetcher()
        self.nvd_fetcher = NVDFetcher()
        self.mapper = DatasetMapper()

    def build_unified_dataset(self) -> UnifiedDataset:
        topology = self.mapper.load_internetmci()
        edges = list(topology.edges())
        nodes = list(topology.nodes())
        node_zones = {n: topology.nodes[n]["zone"] for n in nodes}

        zone_device_mapping = {
            "Core": "router",
            "DMZ": "web_server",
            "FIN": "database",
            "HR": "windows",
            "IT": "vpn"
        }

        traffic = self.caida_fetcher.fetch_traffic_data(edges, topology)
        vulnerabilities = self.nvd_fetcher.fetch_vulnerabilities(
            zone_device_mapping, nodes, node_zones
        )
        behaviors = self.mapper.generate_controlled_behavior(nodes)

        return UnifiedDataset(
            traffic=traffic,
            vulnerabilities=vulnerabilities,
            behaviors=behaviors,
            topology=topology,
            metadata={"source": "Mock API Data Pipeline"},
        )
