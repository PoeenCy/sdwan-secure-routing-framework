from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd


@dataclass
class BaselineResult:
    algorithm: str
    scenario: str
    avg_latency: float
    avg_bn_on_path: float
    min_trust_on_path: float
    mspl_g_final: float
    reroute_time_ms: float
    metadata: Dict[str, Any]


@dataclass
class ComparisonReport:
    results: List[BaselineResult]
    comparison_table: pd.DataFrame
    timestamp: datetime
    dataset_source: str


@dataclass
class PatchReport:
    patches: List[Any]
