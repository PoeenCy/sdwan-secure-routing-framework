"""
Data models for audit-specific operations.

Covers Requirements 2, 3, 4, 5, 6, 7.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal


@dataclass
class Discrepancy:
    """
    Represents a single discrepancy found between code and KI specifications.

    Attributes:
        file_path: Path to the file containing the discrepancy
        component: Name of the component with discrepancy (e.g., "Trust Score Formula")
        formula_in_code: The actual formula/implementation found in code
        correct_formula_ki: The correct formula from KI specifications
        ki_reference: Reference to the KI document section (e.g., "KI_04 §2")
        severity: Impact classification - Critical, Medium, or Light
        line_numbers: List of line numbers where the discrepancy occurs
    """

    file_path: str
    component: str
    formula_in_code: str
    correct_formula_ki: str
    ki_reference: str
    severity: Literal["Critical", "Medium", "Light"]
    line_numbers: List[int] = field(default_factory=list)

    def __post_init__(self):
        """Validate severity value."""
        valid_severities = {"Critical", "Medium", "Light"}
        if self.severity not in valid_severities:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of {valid_severities}"
            )


@dataclass
class AuditReport:
    """
    Comprehensive audit report containing all discovered discrepancies.

    Attributes:
        discrepancies: List of all discrepancies found
        total_critical: Count of Critical severity issues
        total_medium: Count of Medium severity issues
        total_light: Count of Light severity issues
        audit_timestamp: When the audit was performed
    """

    discrepancies: List[Discrepancy]
    total_critical: int
    total_medium: int
    total_light: int
    audit_timestamp: datetime

    @classmethod
    def from_discrepancies(cls, discrepancies: List[Discrepancy]) -> "AuditReport":
        """
        Create an AuditReport from a list of discrepancies.

        Automatically calculates counts by severity.

        Args:
            discrepancies: List of Discrepancy objects

        Returns:
            AuditReport with calculated severity counts
        """
        total_critical = sum(1 for d in discrepancies if d.severity == "Critical")
        total_medium = sum(1 for d in discrepancies if d.severity == "Medium")
        total_light = sum(1 for d in discrepancies if d.severity == "Light")

        return cls(
            discrepancies=discrepancies,
            total_critical=total_critical,
            total_medium=total_medium,
            total_light=total_light,
            audit_timestamp=datetime.now(),
        )

    @property
    def total_discrepancies(self) -> int:
        """Total number of discrepancies across all severities."""
        return len(self.discrepancies)

    @property
    def has_critical_issues(self) -> bool:
        """Check if any critical issues were found."""
        return self.total_critical > 0
