from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .containernet_builder import ContainernetUnderlay
from .model import build_underlay_plan, load_underlay_config


def write_runtime_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if os.geteuid() == 0 and sudo_uid and sudo_gid:
        os.chown(path, int(sudo_uid), int(sudo_gid))


def make_runtime_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if os.geteuid() == 0 and sudo_uid and sudo_gid:
        for directory in (path.parent, path):
            os.chown(directory, int(sudo_uid), int(sudo_gid))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run only the routed underlay.")
    parser.add_argument("--profile", choices=("mini", "abilene"), default="mini")
    parser.add_argument("--no-cli", action="store_true")
    parser.add_argument(
        "--load-response",
        action="store_true",
        help="Run below/above-capacity UDP probes and record queue/loss response.",
    )
    return parser.parse_args()


def main() -> int:
    try:
        from mininet.cli import CLI
        from mininet.log import setLogLevel
        from mininet.net import Containernet
    except ImportError as exc:
        raise SystemExit(
            "Containernet is not installed. Run emulation/scripts/bootstrap_parrot.sh."
        ) from exc

    args = parse_args()
    setLogLevel("info")
    repo_root = Path(__file__).resolve().parents[2]
    config = load_underlay_config(
        repo_root, repo_root / "emulation/config/underlay.yaml"
    )
    plan = build_underlay_plan(config, args.profile)
    runtime_dir = repo_root / "emulation/runtime/underlay" / args.profile
    make_runtime_dir(runtime_dir)
    write_runtime_file(
        runtime_dir / "underlay_plan.json",
        plan.to_json() + "\n",
    )

    net = Containernet(controller=None, build=False)
    underlay = ContainernetUnderlay(net, config, plan)
    try:
        underlay.add_nodes_and_links()
        net.build()
        net.start()
        queue_state_initial = underlay.configure_queue_disciplines()
        write_runtime_file(
            runtime_dir / "underlay_qdisc_initial.json",
            json.dumps(queue_state_initial, indent=2) + "\n",
        )
        underlay.configure_addresses()
        underlay.wait_for_ospf()
        routing_state = underlay.collect_routing_state()
        write_runtime_file(
            runtime_dir / "underlay_routing_state.json",
            json.dumps(routing_state, indent=2) + "\n",
        )
        reachability = underlay.verify_loopback_reachability()
        write_runtime_file(
            runtime_dir / "underlay_reachability.json",
            json.dumps(reachability, indent=2) + "\n",
        )
        failed = [item for item in reachability if not item["reachable"]]
        if failed:
            raise RuntimeError(f"{len(failed)} underlay loopback checks failed")
        traffic = underlay.run_iperf_probe()
        write_runtime_file(
            runtime_dir / "underlay_traffic.json",
            json.dumps(traffic, indent=2) + "\n",
        )
        if not traffic["all_path_hops_forwarded"]:
            raise RuntimeError("iperf3 flow did not increment every path hop")
        ditg_traffic = underlay.run_ditg_probe()
        write_runtime_file(
            runtime_dir / "underlay_ditg_traffic.json",
            json.dumps(ditg_traffic, indent=2) + "\n",
        )
        if ditg_traffic["decoded_packets"] <= 0:
            raise RuntimeError("D-ITG did not deliver the selected SNDlib demand")
        if args.load_response:
            load_response = underlay.run_load_response_probe()
            write_runtime_file(
                runtime_dir / "underlay_load_response.json",
                json.dumps(load_response, indent=2) + "\n",
            )
            write_runtime_file(
                runtime_dir / "underlay_qdisc_final.json",
                json.dumps(underlay.collect_qdisc_state(), indent=2) + "\n",
            )
            if not (
                load_response["capacity_enforced"]
                and load_response["congestion_reacted"]
                and load_response["aqm_observed"]
            ):
                raise RuntimeError(
                    "underlay did not enforce capacity and produce AQM response"
                )
        print(
            f"UNDERLAY READY: {len(plan.nodes)} routers, {len(plan.links)} links, "
            "OSPF converged, all loopbacks reachable, "
            f"iperf3={traffic['measured_receiver_mbps']} Mbps"
        )
        if not args.no_cli:
            CLI(net)
    finally:
        net.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
