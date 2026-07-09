import os
from pathlib import Path
from typing import List
from datetime import datetime
from audit_system.engine.ki_parser import KIFileParser
from audit_system.engine.code_inspector import CodeInspector
from audit_system.engine.classifier import DiscrepancyClassifier
from audit_system.models.audit import AuditReport, Discrepancy


class AuditEngine:
    def __init__(self, ki_dir: Path, code_dir: Path):
        self.ki_dir = ki_dir
        self.code_dir = code_dir
        self.ki_parser = KIFileParser()
        self.classifier = DiscrepancyClassifier()

        self.code_files = self._discover_code_files(code_dir)
        self._load_ki_files(ki_dir)

    def _load_ki_files(self, ki_dir: Path) -> None:
        if ki_dir.exists():
            self.ki_parser.parse_directory(ki_dir)

    def _discover_code_files(self, code_dir: Path) -> List[Path]:
        files = []
        if not code_dir.exists():
            return files
        for root, _, filenames in os.walk(code_dir):
            for filename in filenames:
                if filename.endswith(".py"):
                    files.append(Path(root) / filename)
        return files

    def audit_trust_score(self) -> List[Discrepancy]:
        discrepancies = []
        correct = "T(v) = w_I·I + w_B·B + w_C·C"
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            formula = inspector.detect_trust_score_calculation()
            if formula and formula == "MIN(I, B, C)":
                d = self.classifier.create_discrepancy(
                    str(filepath), "Trust Score Formula", formula, correct, "KI_04 §2"
                )
                discrepancies.append(d)
        return discrepancies

    def audit_action_masking(self) -> List[Discrepancy]:
        discrepancies = []
        correct = "M_t = M^zone AND M^trust AND M^struct"
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            formula = inspector.detect_action_masking()
            if formula and formula != correct:  # Very simplistic check
                d = self.classifier.create_discrepancy(
                    str(filepath),
                    "Action Masking Conditions",
                    formula,
                    correct,
                    "KI_04",
                )
                discrepancies.append(d)
        return discrepancies

    def audit_dynamic_threshold(self) -> List[Discrepancy]:
        discrepancies = []
        correct = "θ(t) = μ_T(t) + k·σ_T(t)"
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            formula = inspector.detect_dynamic_threshold()
            if formula and "0." in formula:  # Hardcoded float
                d = self.classifier.create_discrepancy(
                    str(filepath), "Dynamic Threshold", formula, correct, "KI_04 §2.4"
                )
                discrepancies.append(d)
        return discrepancies

    def audit_reward_function(self) -> List[Discrepancy]:
        discrepancies = []
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            formula = inspector.detect_reward_function()
            # Assuming we only flag if missing components
            pass  # Simplification for mock
        return discrepancies

    def audit_delta_mspl(self) -> List[Discrepancy]:
        discrepancies = []
        correct = "forward-looking MSPL simulation"
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            formula = inspector.detect_delta_mspl()
            if formula == "static value":
                d = self.classifier.create_discrepancy(
                    str(filepath), "ΔMSPL Calculation", formula, correct, "KI_04"
                )
                discrepancies.append(d)
        return discrepancies

    def audit_basta_metrics(self) -> List[Discrepancy]:
        discrepancies = []
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            metrics = inspector.detect_basta_metrics()
            if metrics and len(metrics) < 16:
                d = self.classifier.create_discrepancy(
                    str(filepath),
                    "Basta Metrics Completeness",
                    f"Found {len(metrics)}/16",
                    "16 metrics",
                    "KI_02",
                )
                discrepancies.append(d)
        return discrepancies

    def audit_dqn_architecture(self) -> List[Discrepancy]:
        discrepancies = []
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            arch = inspector.detect_dqn_architecture()
            if arch == "Single DQN":
                d = self.classifier.create_discrepancy(
                    str(filepath),
                    "Double DQN Architecture",
                    arch,
                    "Double DQN",
                    "KI_04",
                )
                discrepancies.append(d)
        return discrepancies

    def audit_control_plane_partition(self) -> List[Discrepancy]:
        discrepancies = []
        correct = "{CONNECTED, SUSPECT, ISOLATED}"
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            cp = inspector.detect_control_plane()
            if cp == "{CONNECTED, DISCONNECTED}":
                d = self.classifier.create_discrepancy(
                    str(filepath), "Control Plane Partition", cp, correct, "KI_05"
                )
                discrepancies.append(d)
        return discrepancies

    def audit_oscillation_control(self) -> List[Discrepancy]:
        discrepancies = []
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            osc = inspector.detect_oscillation_control()
            if osc is None and len(inspector.functions) > 0:
                pass  # simplification
        return discrepancies

    def audit_magic_numbers(self) -> List[Discrepancy]:
        discrepancies = []
        for filepath in self.code_files:
            inspector = CodeInspector()
            inspector.extract_from_file(str(filepath))
            if len(inspector.magic_numbers) > 0:
                d = self.classifier.create_discrepancy(
                    str(filepath),
                    "Magic Numbers",
                    f"{len(inspector.magic_numbers)} magic numbers",
                    "Documented parameters",
                    "KI_04",
                )
                discrepancies.append(d)
        return discrepancies

    def generate_report(self) -> AuditReport:
        discrepancies = []
        discrepancies.extend(self.audit_trust_score())
        discrepancies.extend(self.audit_action_masking())
        discrepancies.extend(self.audit_dynamic_threshold())
        discrepancies.extend(self.audit_reward_function())
        discrepancies.extend(self.audit_delta_mspl())
        discrepancies.extend(self.audit_basta_metrics())
        discrepancies.extend(self.audit_dqn_architecture())
        discrepancies.extend(self.audit_control_plane_partition())
        discrepancies.extend(self.audit_oscillation_control())
        discrepancies.extend(self.audit_magic_numbers())

        return AuditReport(
            discrepancies=discrepancies,
            total_critical=len([d for d in discrepancies if d.severity == "Critical"]),
            total_medium=len([d for d in discrepancies if d.severity == "Medium"]),
            total_light=len([d for d in discrepancies if d.severity == "Light"]),
            audit_timestamp=datetime.now(),
        )

    def generate_markdown_report(self, report: AuditReport, output_dir: Path) -> None:
        if not output_dir.exists():
            output_dir.mkdir(parents=True)

        md = "# ZT-SR Audit Report\n\n"
        md += f"**Audit Timestamp:** {report.audit_timestamp}\n\n"
        md += f"**Summary:** {report.total_critical} Critical | {report.total_medium} Medium | {report.total_light} Light\n\n"

        md += "| File | Component | Formula in code | Correct Formula | Severity | KI Ref |\n"
        md += "|---|---|---|---|---|---|\n"

        # Sort by severity: Critical > Medium > Light
        severity_order = {"Critical": 0, "Medium": 1, "Light": 2}
        sorted_discrepancies = sorted(
            report.discrepancies, key=lambda d: severity_order.get(d.severity, 3)
        )

        for d in sorted_discrepancies:
            filename = Path(d.file_path).name
            md += f"| {filename} | {d.component} | `{d.formula_in_code}` | `{d.correct_formula_ki}` | **{d.severity}** | {d.ki_reference} |\n"

        with open(output_dir / "audit_discrepancies.md", "w", encoding="utf-8") as f:
            f.write(md)
