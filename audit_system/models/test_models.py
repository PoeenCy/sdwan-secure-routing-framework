"""
Unit tests for all data models in the audit system.

Tests cover Requirements 2, 3, 4, 5, 6, 7, 12, 13, 14.
"""

import pytest
from datetime import datetime
from typing import List
import networkx as nx
import pandas as pd

from audit_system.models.audit_models import Discrepancy, AuditReport
from audit_system.models.dataset_models import (
    TrafficData,
    VulnerabilityData,
    BehaviorData,
    UnifiedDataset,
)
from audit_system.models.phase_models import PhaseStatus, PhaseResult
from audit_system.models.baseline_models import BaselineResult, ComparisonReport


class TestDiscrepancy:
    """Test Discrepancy dataclass."""

    def test_discrepancy_creation_valid(self):
        """Test creating a valid Discrepancy object."""
        disc = Discrepancy(
            file_path="src/trust.py",
            component="Trust Score Formula",
            formula_in_code="min(I, B, C)",
            correct_formula_ki="T(v) = w_I·I + w_B·B + w_C·C",
            ki_reference="KI_04 §2",
            severity="Critical",
            line_numbers=[42, 43],
        )

        assert disc.file_path == "src/trust.py"
        assert disc.severity == "Critical"
        assert len(disc.line_numbers) == 2

    def test_discrepancy_invalid_severity(self):
        """Test that invalid severity raises ValueError."""
        with pytest.raises(ValueError, match="Invalid severity"):
            Discrepancy(
                file_path="src/test.py",
                component="Test",
                formula_in_code="test",
                correct_formula_ki="correct",
                ki_reference="KI_04",
                severity="Invalid",  # Invalid severity
                line_numbers=[],
            )

    def test_discrepancy_all_severity_levels(self):
        """Test all valid severity levels."""
        for severity in ["Critical", "Medium", "Light"]:
            disc = Discrepancy(
                file_path="test.py",
                component="Test",
                formula_in_code="test",
                correct_formula_ki="correct",
                ki_reference="KI_04",
                severity=severity,
                line_numbers=[],
            )
            assert disc.severity == severity


class TestAuditReport:
    """Test AuditReport dataclass."""

    def test_audit_report_from_discrepancies(self):
        """Test creating AuditReport from discrepancies list."""
        discrepancies = [
            Discrepancy(
                file_path="a.py",
                component="Test1",
                formula_in_code="x",
                correct_formula_ki="y",
                ki_reference="KI_04",
                severity="Critical",
                line_numbers=[],
            ),
            Discrepancy(
                file_path="b.py",
                component="Test2",
                formula_in_code="x",
                correct_formula_ki="y",
                ki_reference="KI_04",
                severity="Critical",
                line_numbers=[],
            ),
            Discrepancy(
                file_path="c.py",
                component="Test3",
                formula_in_code="x",
                correct_formula_ki="y",
                ki_reference="KI_04",
                severity="Medium",
                line_numbers=[],
            ),
            Discrepancy(
                file_path="d.py",
                component="Test4",
                formula_in_code="x",
                correct_formula_ki="y",
                ki_reference="KI_04",
                severity="Light",
                line_numbers=[],
            ),
        ]

        report = AuditReport.from_discrepancies(discrepancies)

        assert report.total_critical == 2
        assert report.total_medium == 1
        assert report.total_light == 1
        assert report.total_discrepancies == 4
        assert report.has_critical_issues is True

    def test_audit_report_no_critical_issues(self):
        """Test report with no critical issues."""
        discrepancies = [
            Discrepancy(
                file_path="a.py",
                component="Test",
                formula_in_code="x",
                correct_formula_ki="y",
                ki_reference="KI_04",
                severity="Light",
                line_numbers=[],
            )
        ]

        report = AuditReport.from_discrepancies(discrepancies)

        assert report.total_critical == 0
        assert report.has_critical_issues is False


class TestTrafficData:
    """Test TrafficData dataclass."""

    def test_traffic_data_valid(self):
        """Test creating valid TrafficData."""
        traffic = TrafficData(
            edge_id=("node1", "node2"),
            latency_ms=10.5,
            bandwidth_mbps=1000.0,
            packet_loss_rate=0.01,
            jitter_ms=2.5,
            source="CAIDA passive-2024",
        )

        assert traffic.edge_id == ("node1", "node2")
        assert traffic.latency_ms == 10.5
        assert 0 <= traffic.packet_loss_rate <= 1

    def test_traffic_data_negative_latency(self):
        """Test that negative latency raises ValueError."""
        with pytest.raises(ValueError, match="latency_ms must be non-negative"):
            TrafficData(
                edge_id=("n1", "n2"),
                latency_ms=-5.0,
                bandwidth_mbps=100.0,
                packet_loss_rate=0.0,
                jitter_ms=0.0,
                source="test",
            )

    def test_traffic_data_invalid_packet_loss(self):
        """Test that packet loss rate outside [0,1] raises ValueError."""
        with pytest.raises(ValueError, match="packet_loss_rate must be in"):
            TrafficData(
                edge_id=("n1", "n2"),
                latency_ms=10.0,
                bandwidth_mbps=100.0,
                packet_loss_rate=1.5,  # Invalid: > 1
                jitter_ms=0.0,
                source="test",
            )


class TestVulnerabilityData:
    """Test VulnerabilityData dataclass."""

    def test_vulnerability_data_valid(self):
        """Test creating valid VulnerabilityData."""
        vuln = VulnerabilityData(
            node_id="node1",
            zone="Core",
            cve_id="CVE-2024-1234",
            cvss_score=7.5,
            patch_status=0.6,
            device_type="router",
        )

        assert vuln.zone == "Core"
        assert 0 <= vuln.cvss_score <= 10
        assert vuln.patch_status in [0.0, 0.6, 1.0]

    def test_vulnerability_data_invalid_zone(self):
        """Test that invalid zone raises ValueError."""
        with pytest.raises(ValueError, match="zone must be one of"):
            VulnerabilityData(
                node_id="node1",
                zone="InvalidZone",
                cve_id="CVE-2024-1234",
                cvss_score=7.5,
                patch_status=1.0,
                device_type="router",
            )

    def test_vulnerability_data_all_zones(self):
        """Test all valid zones."""
        for zone in ["Core", "DMZ", "FIN", "HR", "IT"]:
            vuln = VulnerabilityData(
                node_id="node1",
                zone=zone,
                cve_id="CVE-2024-1234",
                cvss_score=7.5,
                patch_status=1.0,
                device_type="router",
            )
            assert vuln.zone == zone

    def test_vulnerability_data_all_patch_statuses(self):
        """Test all valid patch statuses."""
        for patch_status in [0.0, 0.6, 1.0]:
            vuln = VulnerabilityData(
                node_id="node1",
                zone="Core",
                cve_id="CVE-2024-1234",
                cvss_score=7.5,
                patch_status=patch_status,
                device_type="router",
            )
            assert vuln.patch_status == patch_status


class TestBehaviorData:
    """Test BehaviorData dataclass."""

    def test_behavior_data_valid(self):
        """Test creating valid BehaviorData."""
        behavior = BehaviorData(
            node_id="node1",
            timestamp=100.0,
            behavior_score=0.85,
            anomaly_type=None,
            source="synthetic_controlled",
        )

        assert 0 <= behavior.behavior_score <= 1
        assert behavior.anomaly_type is None

    def test_behavior_data_with_anomaly(self):
        """Test BehaviorData with anomaly."""
        behavior = BehaviorData(
            node_id="node1",
            timestamp=100.0,
            behavior_score=0.3,
            anomaly_type="attack_scenario_1",
            source="synthetic_controlled",
        )

        assert behavior.anomaly_type == "attack_scenario_1"

    def test_behavior_data_invalid_score(self):
        """Test that behavior score outside [0,1] raises ValueError."""
        with pytest.raises(ValueError, match="behavior_score must be in"):
            BehaviorData(
                node_id="node1",
                timestamp=100.0,
                behavior_score=1.5,  # Invalid
                anomaly_type=None,
                source="test",
            )


class TestUnifiedDataset:
    """Test UnifiedDataset dataclass."""

    def test_unified_dataset_valid(self):
        """Test creating valid UnifiedDataset."""
        # Create simple topology
        G = nx.Graph()
        G.add_nodes_from(["n1", "n2", "n3"])
        G.add_edges_from([("n1", "n2"), ("n2", "n3")])

        traffic = [
            TrafficData(
                edge_id=("n1", "n2"),
                latency_ms=10.0,
                bandwidth_mbps=100.0,
                packet_loss_rate=0.01,
                jitter_ms=1.0,
                source="test",
            )
        ]

        vulnerabilities = [
            VulnerabilityData(
                node_id="n1",
                zone="Core",
                cve_id="CVE-2024-1234",
                cvss_score=7.5,
                patch_status=1.0,
                device_type="router",
            )
        ]

        behaviors = [
            BehaviorData(
                node_id="n1",
                timestamp=100.0,
                behavior_score=0.9,
                anomaly_type=None,
                source="test",
            )
        ]

        dataset = UnifiedDataset(
            traffic=traffic,
            vulnerabilities=vulnerabilities,
            behaviors=behaviors,
            topology=G,
            metadata={"source": "test"},
        )

        assert dataset.node_count == 3
        assert dataset.edge_count == 2
        assert dataset.traffic_coverage > 0

    def test_unified_dataset_invalid_traffic_edge(self):
        """Test that traffic edge not in topology raises ValueError."""
        G = nx.Graph()
        G.add_nodes_from(["n1", "n2"])
        G.add_edge("n1", "n2")

        traffic = [
            TrafficData(
                edge_id=("n1", "n3"),  # n3 doesn't exist
                latency_ms=10.0,
                bandwidth_mbps=100.0,
                packet_loss_rate=0.01,
                jitter_ms=1.0,
                source="test",
            )
        ]

        with pytest.raises(ValueError, match="Traffic edge .* not found in topology"):
            UnifiedDataset(
                traffic=traffic, vulnerabilities=[], behaviors=[], topology=G
            )

    def test_unified_dataset_invalid_vulnerability_node(self):
        """Test that vulnerability node not in topology raises ValueError."""
        G = nx.Graph()
        G.add_node("n1")

        vulnerabilities = [
            VulnerabilityData(
                node_id="n2",  # Doesn't exist
                zone="Core",
                cve_id="CVE-2024-1234",
                cvss_score=7.5,
                patch_status=1.0,
                device_type="router",
            )
        ]

        with pytest.raises(
            ValueError, match="Vulnerability node .* not found in topology"
        ):
            UnifiedDataset(
                traffic=[], vulnerabilities=vulnerabilities, behaviors=[], topology=G
            )


class TestPhaseStatus:
    """Test PhaseStatus enum."""

    def test_phase_status_values(self):
        """Test all PhaseStatus values exist."""
        assert PhaseStatus.NOT_STARTED.value == "not_started"
        assert PhaseStatus.IN_PROGRESS.value == "in_progress"
        assert PhaseStatus.AWAITING_CHECKPOINT.value == "awaiting_checkpoint"
        assert PhaseStatus.COMPLETED.value == "completed"
        assert PhaseStatus.FAILED.value == "failed"

    def test_phase_status_is_terminal(self):
        """Test is_terminal property."""
        assert PhaseStatus.COMPLETED.is_terminal is True
        assert PhaseStatus.FAILED.is_terminal is True
        assert PhaseStatus.IN_PROGRESS.is_terminal is False
        assert PhaseStatus.NOT_STARTED.is_terminal is False

    def test_phase_status_is_active(self):
        """Test is_active property."""
        assert PhaseStatus.IN_PROGRESS.is_active is True
        assert PhaseStatus.COMPLETED.is_active is False

    def test_phase_status_needs_approval(self):
        """Test needs_approval property."""
        assert PhaseStatus.AWAITING_CHECKPOINT.needs_approval is True
        assert PhaseStatus.COMPLETED.needs_approval is False


class TestPhaseResult:
    """Test PhaseResult dataclass."""

    def test_phase_result_valid(self):
        """Test creating valid PhaseResult."""
        start = datetime.now()
        result = PhaseResult(
            phase_name="audit", status=PhaseStatus.IN_PROGRESS, start_time=start
        )

        assert result.phase_name == "audit"
        assert result.status == PhaseStatus.IN_PROGRESS
        assert result.is_successful is False

    def test_phase_result_mark_completed(self):
        """Test marking phase as completed."""
        result = PhaseResult(
            phase_name="audit",
            status=PhaseStatus.IN_PROGRESS,
            start_time=datetime.now(),
        )

        result.mark_completed(result_data={"count": 5})

        assert result.status == PhaseStatus.COMPLETED
        assert result.is_successful is True
        assert result.end_time is not None
        assert result.result_data == {"count": 5}

    def test_phase_result_mark_failed(self):
        """Test marking phase as failed."""
        result = PhaseResult(
            phase_name="audit",
            status=PhaseStatus.IN_PROGRESS,
            start_time=datetime.now(),
        )

        result.mark_failed("Test error")

        assert result.status == PhaseStatus.FAILED
        assert result.error_message == "Test error"
        assert result.end_time is not None

    def test_phase_result_invalid_phase_name(self):
        """Test that invalid phase name raises ValueError."""
        with pytest.raises(ValueError, match="phase_name must be one of"):
            PhaseResult(
                phase_name="invalid_phase",
                status=PhaseStatus.IN_PROGRESS,
                start_time=datetime.now(),
            )


class TestBaselineResult:
    """Test BaselineResult dataclass."""

    def test_baseline_result_valid(self):
        """Test creating valid BaselineResult."""
        result = BaselineResult(
            algorithm="ZT-SR-DRL",
            scenario="S1",
            avg_latency=15.5,
            avg_bn_on_path=0.25,
            min_trust_on_path=0.85,
            mspl_g_final=3.5,
            reroute_time_ms=50.0,
        )

        assert result.algorithm == "ZT-SR-DRL"
        assert result.scenario == "S1"
        assert result.avg_latency > 0

    def test_baseline_result_all_algorithms(self):
        """Test all valid algorithms."""
        algorithms = [
            "SP-Routing",
            "QoS-Routing",
            "Seg-Routing",
            "ZT-Routing",
            "ZT-SR-DRL",
        ]

        for algo in algorithms:
            result = BaselineResult(
                algorithm=algo,
                scenario="S1",
                avg_latency=10.0,
                avg_bn_on_path=0.1,
                min_trust_on_path=0.9,
                mspl_g_final=3.0,
                reroute_time_ms=10.0,
            )
            assert result.algorithm == algo

    def test_baseline_result_invalid_algorithm(self):
        """Test that invalid algorithm raises ValueError."""
        with pytest.raises(ValueError, match="algorithm must be one of"):
            BaselineResult(
                algorithm="InvalidAlgo",
                scenario="S1",
                avg_latency=10.0,
                avg_bn_on_path=0.1,
                min_trust_on_path=0.9,
                mspl_g_final=3.0,
                reroute_time_ms=10.0,
            )

    def test_baseline_result_invalid_trust_range(self):
        """Test that trust score outside [0,1] raises ValueError."""
        with pytest.raises(ValueError, match="min_trust_on_path must be in"):
            BaselineResult(
                algorithm="ZT-SR-DRL",
                scenario="S1",
                avg_latency=10.0,
                avg_bn_on_path=0.1,
                min_trust_on_path=1.5,  # Invalid
                mspl_g_final=3.0,
                reroute_time_ms=10.0,
            )


class TestComparisonReport:
    """Test ComparisonReport dataclass."""

    def test_comparison_report_from_results(self):
        """Test creating ComparisonReport from results."""
        results = [
            BaselineResult(
                algorithm="ZT-SR-DRL",
                scenario="S1",
                avg_latency=15.0,
                avg_bn_on_path=0.2,
                min_trust_on_path=0.9,
                mspl_g_final=4.0,
                reroute_time_ms=50.0,
            ),
            BaselineResult(
                algorithm="SP-Routing",
                scenario="S1",
                avg_latency=20.0,
                avg_bn_on_path=0.3,
                min_trust_on_path=0.7,
                mspl_g_final=3.0,
                reroute_time_ms=10.0,
            ),
        ]

        report = ComparisonReport.from_results(results, "CAIDA-2024")

        assert len(report.results) == 2
        assert report.dataset_source == "CAIDA-2024"
        assert isinstance(report.comparison_table, pd.DataFrame)
        assert report.summary_statistics["total_runs"] == 2

    def test_comparison_report_best_algorithm_by_latency(self):
        """Test identifying best algorithm by latency."""
        results = [
            BaselineResult(
                algorithm="ZT-SR-DRL",
                scenario="S1",
                avg_latency=15.0,
                avg_bn_on_path=0.2,
                min_trust_on_path=0.9,
                mspl_g_final=4.0,
                reroute_time_ms=50.0,
            ),
            BaselineResult(
                algorithm="SP-Routing",
                scenario="S1",
                avg_latency=20.0,
                avg_bn_on_path=0.3,
                min_trust_on_path=0.7,
                mspl_g_final=3.0,
                reroute_time_ms=10.0,
            ),
        ]

        report = ComparisonReport.from_results(results, "test")

        # ZT-SR-DRL has lower latency (15.0 < 20.0)
        assert report.best_algorithm_by_latency == "ZT-SR-DRL"

    def test_comparison_report_filter_by_scenario(self):
        """Test filtering results by scenario."""
        results = [
            BaselineResult(
                algorithm="ZT-SR-DRL",
                scenario="S1",
                avg_latency=15.0,
                avg_bn_on_path=0.2,
                min_trust_on_path=0.9,
                mspl_g_final=4.0,
                reroute_time_ms=50.0,
            ),
            BaselineResult(
                algorithm="ZT-SR-DRL",
                scenario="S2",
                avg_latency=16.0,
                avg_bn_on_path=0.25,
                min_trust_on_path=0.85,
                mspl_g_final=3.8,
                reroute_time_ms=55.0,
            ),
        ]

        report = ComparisonReport.from_results(results, "test")
        s1_results = report.get_results_for_scenario("S1")

        assert len(s1_results) == 1
        assert s1_results[0].scenario == "S1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
