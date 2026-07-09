"""
Data models for phase execution and orchestration.

Handles phase status tracking and result reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class PhaseStatus(Enum):
    """
    Status of a phase in the audit-refactor workflow.

    Values:
        NOT_STARTED: Phase has not begun
        IN_PROGRESS: Phase is currently executing
        AWAITING_CHECKPOINT: Phase completed, waiting for user approval
        COMPLETED: Phase successfully completed and approved
        FAILED: Phase failed or was rejected
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_CHECKPOINT = "awaiting_checkpoint"
    COMPLETED = "completed"
    FAILED = "failed"

    def __str__(self) -> str:
        """String representation for display."""
        return self.value

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (completed or failed)."""
        return self in {PhaseStatus.COMPLETED, PhaseStatus.FAILED}

    @property
    def is_active(self) -> bool:
        """Check if this phase is currently active."""
        return self == PhaseStatus.IN_PROGRESS

    @property
    def needs_approval(self) -> bool:
        """Check if this phase is waiting for checkpoint approval."""
        return self == PhaseStatus.AWAITING_CHECKPOINT


@dataclass
class PhaseResult:
    """
    Result of a phase execution with metadata.

    Attributes:
        phase_name: Name of the phase (audit, dataset, fix, baseline)
        status: Current status of the phase
        start_time: When phase execution started
        end_time: When phase execution completed (None if still running)
        result_data: Any phase-specific result data
        error_message: Error message if phase failed
        metadata: Additional metadata about the phase execution
    """

    phase_name: str
    status: PhaseStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    result_data: Optional[Any] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate phase result."""
        valid_phases = {"audit", "dataset", "fix", "baseline"}
        if self.phase_name not in valid_phases:
            raise ValueError(
                f"phase_name must be one of {valid_phases}, got {self.phase_name}"
            )

        # If status is FAILED, error_message should be set
        if self.status == PhaseStatus.FAILED and not self.error_message:
            raise ValueError("error_message required when status is FAILED")

        # If phase is completed or failed, end_time should be set
        if self.status.is_terminal and not self.end_time:
            self.end_time = datetime.now()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate phase duration in seconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    @property
    def is_successful(self) -> bool:
        """Check if phase completed successfully."""
        return self.status == PhaseStatus.COMPLETED

    def mark_completed(self, result_data: Any = None) -> None:
        """
        Mark the phase as completed.

        Args:
            result_data: Optional result data to store
        """
        self.status = PhaseStatus.COMPLETED
        self.end_time = datetime.now()
        if result_data is not None:
            self.result_data = result_data

    def mark_failed(self, error_message: str) -> None:
        """
        Mark the phase as failed.

        Args:
            error_message: Description of the failure
        """
        self.status = PhaseStatus.FAILED
        self.end_time = datetime.now()
        self.error_message = error_message

    def mark_awaiting_checkpoint(self, result_data: Any = None) -> None:
        """
        Mark the phase as awaiting checkpoint approval.

        Args:
            result_data: Optional result data to store
        """
        self.status = PhaseStatus.AWAITING_CHECKPOINT
        self.end_time = datetime.now()
        if result_data is not None:
            self.result_data = result_data
