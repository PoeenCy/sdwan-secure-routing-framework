from __future__ import annotations

from typing import Any, Literal


ArtifactClass = Literal["configuration", "measurement"]
SCHEMA_VERSION = 1


class ArtifactClassificationError(ValueError):
    """Raised when configuration is accidentally consumed as a measurement."""


def artifact_envelope(
    artifact_class: ArtifactClass,
    producer: str,
    method: str,
    payload: Any,
) -> dict[str, Any]:
    """Wrap runtime data so configured inputs cannot masquerade as results."""
    if artifact_class not in {"configuration", "measurement"}:
        raise ArtifactClassificationError(
            f"Unsupported artifact class: {artifact_class}"
        )
    if not producer.strip() or not method.strip():
        raise ArtifactClassificationError("producer and method must be non-empty")
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_class": artifact_class,
        "plot_eligible": artifact_class == "measurement",
        "producer": producer,
        "method": method,
        "payload": payload,
    }


def require_measurement(document: dict[str, Any]) -> Any:
    """Return measured payload or reject static configuration used for plots."""
    if document.get("artifact_class") != "measurement":
        raise ArtifactClassificationError(
            "Only artifact_class=measurement may be used as an experiment result"
        )
    if document.get("plot_eligible") is not True:
        raise ArtifactClassificationError("Measurement is not marked plot-eligible")
    return document["payload"]
