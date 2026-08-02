import pytest

from emulation.artifacts import (
    ArtifactClassificationError,
    artifact_envelope,
    require_measurement,
)


def test_static_configuration_is_never_plot_eligible() -> None:
    document = artifact_envelope(
        artifact_class="configuration",
        producer="test",
        method="Haversine value configured in NetEm",
        payload={"configured_propagation_delay_ms": 8.0},
    )

    assert document["plot_eligible"] is False
    with pytest.raises(ArtifactClassificationError):
        require_measurement(document)


def test_packet_measurement_is_plot_eligible() -> None:
    document = artifact_envelope(
        artifact_class="measurement",
        producer="test",
        method="D-ITG receiver log and tc -s qdisc counter delta",
        payload={"measured_delay_ms": 13.2, "drop_delta": 4},
    )

    assert require_measurement(document) == {
        "measured_delay_ms": 13.2,
        "drop_delta": 4,
    }
