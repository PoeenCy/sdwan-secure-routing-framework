from dataclasses import dataclass
from typing import List, Literal
from datetime import datetime
from enum import Enum


class PhaseStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_CHECKPOINT = "awaiting_checkpoint"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Discrepancy:
    file_path: str
    component: str
    formula_in_code: str
    correct_formula_ki: str
    ki_reference: str
    severity: Literal["Critical", "Medium", "Light"]
    line_numbers: List[int]


@dataclass
class AuditReport:
    discrepancies: List[Discrepancy]
    total_critical: int
    total_medium: int
    total_light: int
    audit_timestamp: datetime
