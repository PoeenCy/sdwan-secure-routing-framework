from pathlib import Path
from audit_system.models.audit import PhaseStatus
from audit_system.engine.audit_engine import AuditEngine
from audit_system.dataset.builder import DatasetBuilder
from audit_system.dataset.validator import ConsistencyChecker
from audit_system.deployment.patcher import DeploymentPipeline
from audit_system.deployment.baseline_runner import BaselineRunner
from audit_system.deployment.metrics import MetricsCollector


class Orchestrator:
    def __init__(self, ki_dir: Path, code_dir: Path, output_dir: Path):
        self.ki_dir = ki_dir
        self.code_dir = code_dir
        self.output_dir = output_dir
        self.audit_engine = AuditEngine(ki_dir, code_dir)
        self.dataset_builder = DatasetBuilder(output_dir)
        self.deployment_pipeline = None
        self.phase_status = {
            "audit": PhaseStatus.NOT_STARTED,
            "dataset": PhaseStatus.NOT_STARTED,
            "fix": PhaseStatus.NOT_STARTED,
            "baseline": PhaseStatus.NOT_STARTED,
        }

    def execute_phase_1_audit(self):
        self.phase_status["audit"] = PhaseStatus.IN_PROGRESS
        report = self.audit_engine.generate_report()
        self.audit_engine.generate_markdown_report(report, self.output_dir)
        self.phase_status["audit"] = PhaseStatus.AWAITING_CHECKPOINT
        return report

    def execute_phase_2_dataset(self):
        self.phase_status["dataset"] = PhaseStatus.IN_PROGRESS
        dataset = self.dataset_builder.build_unified_dataset()
        report = ConsistencyChecker.validate(dataset)
        if not report.passed:
            self.phase_status["dataset"] = PhaseStatus.FAILED
            raise Exception("Dataset consistency failed")
        self.phase_status["dataset"] = PhaseStatus.AWAITING_CHECKPOINT
        return dataset

    def execute_phase_3_fix(self, audit_report):
        self.phase_status["fix"] = PhaseStatus.IN_PROGRESS
        self.deployment_pipeline = DeploymentPipeline(self.code_dir)
        patch_report = self.deployment_pipeline.apply_fixes(audit_report.discrepancies)
        self.phase_status["fix"] = PhaseStatus.AWAITING_CHECKPOINT
        return patch_report

    def execute_phase_4_baseline(self, dataset):
        self.phase_status["baseline"] = PhaseStatus.IN_PROGRESS
        runner = BaselineRunner(self.code_dir, dataset)
        scenarios = ["NORMAL", "TRUST_COMPROMISED", "DELAY_SPIKE", "STRUCTURE_MITIGATED"]
        results = runner.run_baselines(scenarios)
        report = MetricsCollector.generate_comparison_report(
            results, dataset.metadata.get("source", "unknown")
        )
        self.phase_status["baseline"] = PhaseStatus.COMPLETED
        return report
