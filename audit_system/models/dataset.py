from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import networkx as nx


@dataclass
class TrafficData:
    edge_id: Tuple[str, str]
    latency_ms: float
    bandwidth_mbps: float
    packet_loss_rate: float
    jitter_ms: float
    source: str


@dataclass
class VulnerabilityData:
    node_id: str
    zone: str
    cve_id: str
    cvss_score: float
    patch_status: float
    device_type: str


@dataclass
class BehaviorData:
    node_id: str
    timestamp: float
    behavior_score: float
    anomaly_type: Optional[str]
    source: str


@dataclass
class UnifiedDataset:
    traffic: List[TrafficData]
    vulnerabilities: List[VulnerabilityData]
    behaviors: List[BehaviorData]
    topology: nx.Graph
    metadata: Dict[str, Any]
