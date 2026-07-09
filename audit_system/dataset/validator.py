from audit_system.models.dataset import UnifiedDataset
from dataclasses import dataclass
from typing import List


@dataclass
class ConsistencyReport:
    passed: bool
    errors: List[str]


class ConsistencyChecker:
    @staticmethod
    def validate(dataset: UnifiedDataset) -> ConsistencyReport:
        errors = []
        for v in dataset.vulnerabilities:
            if not (0.0 <= v.patch_status <= 1.0):
                errors.append(f"Invalid patch status for node {v.node_id}")
            if not (0.0 <= v.cvss_score <= 10.0):
                errors.append(f"Invalid CVSS score for node {v.node_id}")

        for b in dataset.behaviors:
            if not (0.0 <= b.behavior_score <= 1.0):
                errors.append(f"Invalid behavior score for node {b.node_id}")

        for t in dataset.traffic:
            if t.latency_ms < 0 or t.bandwidth_mbps < 0:
                errors.append(f"Invalid traffic metrics for edge {t.edge_id}")

        return ConsistencyReport(passed=len(errors) == 0, errors=errors)
