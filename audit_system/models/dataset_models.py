"""
Data models for dataset building and unified training data.

Covers Requirements 12, 13, 14.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import networkx as nx


@dataclass
class TrafficData:
    """
    Real traffic data from CAIDA or synthetic baseline.

    Attributes:
        edge_id: Tuple of (source_node, dest_node) identifiers
        latency_ms: Edge latency in milliseconds
        bandwidth_mbps: Available bandwidth in Mbps
        packet_loss_rate: Packet loss rate as a fraction [0, 1]
        jitter_ms: Jitter in milliseconds
        source: Data source identifier (e.g., "CAIDA passive-2024")
    """

    edge_id: Tuple[str, str]
    latency_ms: float
    bandwidth_mbps: float
    packet_loss_rate: float
    jitter_ms: float
    source: str

    def __post_init__(self):
        """Validate traffic data ranges."""
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative, got {self.latency_ms}")
        if self.bandwidth_mbps < 0:
            raise ValueError(
                f"bandwidth_mbps must be non-negative, got {self.bandwidth_mbps}"
            )
        if not 0 <= self.packet_loss_rate <= 1:
            raise ValueError(
                f"packet_loss_rate must be in [0, 1], got {self.packet_loss_rate}"
            )
        if self.jitter_ms < 0:
            raise ValueError(f"jitter_ms must be non-negative, got {self.jitter_ms}")


@dataclass
class VulnerabilityData:
    """
    Node vulnerability data from NVD CVE database.

    Attributes:
        node_id: Identifier of the node
        zone: Micro-segmentation zone (Core, DMZ, FIN, HR, IT)
        cve_id: CVE identifier (e.g., "CVE-2024-1234")
        cvss_score: CVSS base score [0, 10]
        patch_status: Patch level - 0.0 (unpatched), 0.6 (partial), 1.0 (fully patched)
        device_type: Type of device (router, web_server, database, endpoint, admin_tools)
    """

    node_id: str
    zone: str
    cve_id: str
    cvss_score: float
    patch_status: float
    device_type: str

    def __post_init__(self):
        """Validate vulnerability data."""
        valid_zones = {"Core", "DMZ", "FIN", "HR", "IT"}
        if self.zone not in valid_zones:
            raise ValueError(f"zone must be one of {valid_zones}, got {self.zone}")

        if not 0 <= self.cvss_score <= 10:
            raise ValueError(f"cvss_score must be in [0, 10], got {self.cvss_score}")

        valid_patch_statuses = {0.0, 0.6, 1.0}
        if self.patch_status not in valid_patch_statuses:
            raise ValueError(
                f"patch_status must be one of {valid_patch_statuses}, got {self.patch_status}"
            )


@dataclass
class BehaviorData:
    """
    Node behavior data - synthetic with controlled anomaly injection.

    Attributes:
        node_id: Identifier of the node
        timestamp: Simulation timestamp
        behavior_score: B(v,t) score in [0, 1]
        anomaly_type: Optional anomaly type (None or "attack_scenario_X")
        source: Data source identifier (e.g., "synthetic_controlled")
    """

    node_id: str
    timestamp: float
    behavior_score: float
    anomaly_type: Optional[str]
    source: str

    def __post_init__(self):
        """Validate behavior data."""
        if not 0 <= self.behavior_score <= 1:
            raise ValueError(
                f"behavior_score must be in [0, 1], got {self.behavior_score}"
            )
        if self.timestamp < 0:
            raise ValueError(f"timestamp must be non-negative, got {self.timestamp}")


@dataclass
class UnifiedDataset:
    """
    Unified training dataset combining traffic, vulnerability, and behavior data.

    Attributes:
        traffic: List of traffic data for edges
        vulnerabilities: List of vulnerability data for nodes
        behaviors: List of behavior data for nodes over time
        topology: NetworkX graph representing the network topology
        metadata: Additional metadata about the dataset
    """

    traffic: List[TrafficData]
    vulnerabilities: List[VulnerabilityData]
    behaviors: List[BehaviorData]
    topology: nx.Graph
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate unified dataset consistency."""
        # Ensure topology is provided
        if self.topology is None:
            raise ValueError("topology must be provided")

        # Validate that traffic edges exist in topology
        topology_edges = set(self.topology.edges())
        for traffic in self.traffic:
            edge = traffic.edge_id
            # Check both directions since graph might be undirected
            if edge not in topology_edges and (edge[1], edge[0]) not in topology_edges:
                raise ValueError(f"Traffic edge {edge} not found in topology")

        # Validate that vulnerability nodes exist in topology
        topology_nodes = set(self.topology.nodes())
        for vuln in self.vulnerabilities:
            if vuln.node_id not in topology_nodes:
                raise ValueError(
                    f"Vulnerability node {vuln.node_id} not found in topology"
                )

        # Validate that behavior nodes exist in topology
        for behavior in self.behaviors:
            if behavior.node_id not in topology_nodes:
                raise ValueError(
                    f"Behavior node {behavior.node_id} not found in topology"
                )

    @property
    def node_count(self) -> int:
        """Number of nodes in the topology."""
        return self.topology.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Number of edges in the topology."""
        return self.topology.number_of_edges()

    @property
    def traffic_coverage(self) -> float:
        """Percentage of edges with traffic data."""
        if self.edge_count == 0:
            return 0.0
        return len(self.traffic) / self.edge_count
