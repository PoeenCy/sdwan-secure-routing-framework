from typing import Literal
from audit_system.models.audit import Discrepancy

SEVERITY_RULES = {
    "Trust Score Formula": "Critical",
    "Action Masking Conditions": "Critical",
    "Dynamic Threshold": "Critical",
    "Reward Function Components": "Critical",
    "ΔMSPL Calculation": "Critical",
    "Double DQN Architecture": "Critical",
    "Control Plane Partition": "Critical",
    "Basta Metrics Completeness": "Medium",
    "CMC Definition": "Medium",
    "Network Layer Sizes": "Medium",
    "Oscillation Control": "Medium",
    "Magic Numbers": "Light",
}


class DiscrepancyClassifier:
    @staticmethod
    def classify_severity(
        component_name: str,
    ) -> Literal["Critical", "Medium", "Light"]:
        # Fallback to Medium if unknown
        return SEVERITY_RULES.get(component_name, "Medium")

    @staticmethod
    def create_discrepancy(
        file_path: str,
        component: str,
        formula_in_code: str,
        correct_formula_ki: str,
        ki_reference: str,
        line_numbers: list[int] = None,
    ) -> Discrepancy:
        severity = DiscrepancyClassifier.classify_severity(component)
        return Discrepancy(
            file_path=file_path,
            component=component,
            formula_in_code=formula_in_code,
            correct_formula_ki=correct_formula_ki,
            ki_reference=ki_reference,
            severity=severity,
            line_numbers=line_numbers or [],
        )
