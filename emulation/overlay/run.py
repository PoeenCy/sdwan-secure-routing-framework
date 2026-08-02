from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from emulation.artifacts import ArtifactClass, artifact_envelope
from emulation.underlay.containernet_builder import ContainernetUnderlay
from emulation.underlay.model import build_underlay_plan, load_underlay_config

from .containernet_builder import ContainernetOverlay
from .model import load_overlay_config


def _make_runtime_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if os.geteuid() == 0 and sudo_uid and sudo_gid:
        for directory in (path.parent, path):
            os.chown(directory, int(sudo_uid), int(sudo_gid))


def _write_artifact(
    path: Path,
    artifact_class: ArtifactClass,
    method: str,
    payload: object,
) -> None:
    document = artifact_envelope(
        artifact_class=artifact_class,
        producer="emulation.overlay.run",
        method=method,
        payload=payload,
    )
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if os.geteuid() == 0 and sudo_uid and sudo_gid:
        os.chown(path, int(sudo_uid), int(sudo_gid))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full Abilene underlay and real SD-WAN overlay."
    )
    parser.add_argument("--no-cli", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        from mininet.cli import CLI
        from mininet.log import setLogLevel
        from mininet.net import Containernet
    except ImportError as exc:
        raise SystemExit(
            "Containernet is not installed. Run bootstrap_parrot.sh first."
        ) from exc

    args = parse_args()
    setLogLevel("info")
    repo_root = Path(__file__).resolve().parents[2]
    underlay_config = load_underlay_config(
        repo_root, repo_root / "emulation/config/underlay.yaml"
    )
    underlay_plan = build_underlay_plan(underlay_config, "abilene")
    overlay_config = load_overlay_config(
        repo_root / "emulation/config/overlay.yaml"
    )
    selected_routers = {node.node_id for node in underlay_plan.nodes}
    attachment_routers = {
        wan.router
        for site in overlay_config.sites.values()
        for wan in site.wans.values()
    }
    missing = attachment_routers - selected_routers
    if missing:
        raise RuntimeError(f"Overlay attachment routers are absent: {sorted(missing)}")

    runtime_dir = repo_root / "emulation/runtime/overlay"
    configuration_dir = runtime_dir / "configuration"
    measurement_dir = runtime_dir / "measurements"
    _make_runtime_dir(configuration_dir)
    _make_runtime_dir(measurement_dir)
    _write_artifact(
        configuration_dir / "overlay_plan.json",
        "configuration",
        "validated overlay.yaml and SNDlib Abilene plan",
        {
            "sites": list(overlay_config.sites),
            "tunnels": [tunnel.tunnel_id for tunnel in overlay_config.tunnels],
            "policies": [policy.policy_id for policy in overlay_config.policies],
            "underlay": underlay_plan.to_dict(),
        },
    )

    net = Containernet(controller=None, build=False)
    underlay = ContainernetUnderlay(net, underlay_config, underlay_plan)
    overlay = ContainernetOverlay(net, underlay, overlay_config, repo_root)
    try:
        underlay.add_nodes_and_links()
        overlay.add_nodes_and_links()
        net.build()
        net.start()

        queue_state = underlay.configure_queue_disciplines()
        _write_artifact(
            configuration_dir / "qdisc_applied.json",
            "configuration",
            "TCLink HTB/NetEm plus tc qdisc CoDel configuration",
            queue_state,
        )
        extra_interfaces = overlay.configure_layer3()
        underlay.configure_addresses(extra_interfaces=extra_interfaces)
        underlay.wait_for_ospf()
        _write_artifact(
            measurement_dir / "underlay_routing_state.json",
            "measurement",
            "iproute2 and FRR runtime state capture",
            underlay.collect_routing_state(),
        )
        wan_reachability = overlay.verify_wan_reachability()
        _write_artifact(
            measurement_dir / "wan_reachability.json",
            "measurement",
            "real ICMP echo packets between CPE outer endpoints",
            wan_reachability,
        )

        overlay.configure_ovs_and_gre()
        overlay.start_controller_and_sensors()
        openflow = overlay.wait_for_openflow()
        _write_artifact(
            measurement_dir / "openflow_connections.json",
            "measurement",
            "OVSDB is_connected state observed after OF1.3 negotiation",
            openflow,
        )

        policy = overlay.verify_policy_forwarding()
        _write_artifact(
            measurement_dir / "policy_forwarding.json",
            "measurement",
            "real ICMP allow/deny flows through OpenFlow and GRE",
            policy,
        )
        gre = overlay.verify_gre_transport()
        _write_artifact(
            measurement_dir / "gre_underlay_capture.json",
            "measurement",
            "tcpdump of outer IP protocol 47 at both underlay attachments",
            gre,
        )
        isolation = overlay.verify_underlay_isolation()
        _write_artifact(
            measurement_dir / "underlay_isolation.json",
            "measurement",
            "runtime route-table inspection on every underlay router",
            isolation,
        )

        time.sleep(float(overlay_config.controller["probe_interval_seconds"]) + 1)
        state = overlay.collect_state()
        _write_artifact(
            measurement_dir / "overlay_state.json",
            "measurement",
            "OVS flows, Suricata RX counters, and active GRE probe JSONL",
            state,
        )
        if not state["tunnel_probes"]:
            raise RuntimeError("Controller produced no active-probe telemetry")
        if not all(
            sensor["capture_rx_packets"] > 0
            for sensor in state["sensors"].values()
        ):
            raise RuntimeError("At least one Suricata mirror received no packets")

        print(
            "OVERLAY READY: 4 namespace-isolated OVS CPEs, "
            "6 GRE tunnels over Abilene, OpenFlow 1.3 connected, "
            "HR->FIN path A allowed, IT->FIN path B allowed, "
            "DMZ->FIN denied, SPAN and active probes observed"
        )
        if not args.no_cli:
            CLI(net)
    finally:
        net.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
