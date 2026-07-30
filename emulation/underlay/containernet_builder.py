from __future__ import annotations

import ipaddress
import json
import re
import time
from dataclasses import dataclass
from typing import Any

from .frr import RouterInterface, ospf_vtysh_arguments, render_vtysh_command
from .model import UnderlayConfig, UnderlayPlan


@dataclass(frozen=True)
class RuntimeLink:
    link_id: str
    left_interface: str
    right_interface: str


class UnderlayRuntimeError(RuntimeError):
    pass


class ContainernetUnderlay:
    """Create and configure only the routed underlay layer."""

    def __init__(self, net: Any, config: UnderlayConfig, plan: UnderlayPlan):
        self.net = net
        self.config = config
        self.plan = plan
        self.routers: dict[str, Any] = {}
        self.runtime_links: dict[str, RuntimeLink] = {}

    def add_nodes_and_links(self) -> None:
        try:
            from mininet.link import TCLink
        except ImportError as exc:
            raise UnderlayRuntimeError(
                "Containernet/Mininet is not installed in the active environment"
            ) from exc

        for node in self.plan.nodes:
            self.routers[node.node_id] = self.net.addDocker(
                node.container_name,
                dimage=self.plan.router_image,
                dcmd=self.plan.router_command,
                cap_add=list(self.plan.container_capabilities),
                sysctls=self.plan.container_sysctls,
                rm=True,
            )

        for link in self.plan.links:
            created = self.net.addLink(
                self.routers[link.left],
                self.routers[link.right],
                cls=TCLink,
                bw=link.bandwidth_mbps,
                delay=f"{link.delay_ms}ms",
                loss=link.loss_percent,
                max_queue_size=link.max_queue_packets,
                use_htb=True,
            )
            self.runtime_links[link.link_id] = RuntimeLink(
                link_id=link.link_id,
                left_interface=created.intf1.name,
                right_interface=created.intf2.name,
            )

    @staticmethod
    def _count_full_ospf_neighbors(raw_output: str) -> int:
        output = ContainernetUnderlay._clean_terminal_output(raw_output).strip()
        try:
            document = json.loads(output)
        except json.JSONDecodeError:
            return len(
                re.findall(
                    r'"(?:nbrState|state)"\s*:\s*"Full(?:/[^"]*)?"',
                    output,
                )
            )

        count = 0

        def visit(value: Any) -> None:
            nonlocal count
            if isinstance(value, dict):
                state = value.get("nbrState", value.get("state"))
                if isinstance(state, str) and state.startswith("Full"):
                    count += 1
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(document)
        return count

    @staticmethod
    def _clean_terminal_output(output: str) -> str:
        """Remove control sequences emitted by an interactive container shell."""
        ansi_csi = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
        return ansi_csi.sub("", output).replace("\r", "")

    @staticmethod
    def _checked_cmd(node: Any, command: str) -> str:
        marker = "__ZT_RC__"
        raw_output = node.cmd(f"{command}; rc=$?; echo {marker}$rc")
        output = ContainernetUnderlay._clean_terminal_output(raw_output or "")
        matches = list(re.finditer(rf"{marker}(\d+)", output))
        if not matches:
            raise UnderlayRuntimeError(
                f"{node.name}: command did not return a status marker: {command}"
            )
        match = matches[-1]
        return_code = int(match.group(1))
        body = output[: match.start()].strip()
        if return_code != 0:
            raise UnderlayRuntimeError(
                f"{node.name}: command failed ({return_code}): {command}\n{body}"
            )
        return body

    def configure_addresses(self) -> None:
        node_by_id = {node.node_id: node for node in self.plan.nodes}
        interface_inventory: dict[str, list[RouterInterface]] = {
            node.node_id: [] for node in self.plan.nodes
        }

        for node in self.plan.nodes:
            router = self.routers[node.node_id]
            # Containernet assigns its Docker management interface an address
            # from 10.0.0.0/8. That connected route would shadow the lab's
            # 10.64.0.0/16 links and 10.255.0.0/24 loopbacks. Docker exec does
            # not depend on this address, so remove it before routing starts.
            self._checked_cmd(router, "ip addr flush dev eth0")
            self._checked_cmd(router, "ip link set lo up")
            self._checked_cmd(router, f"ip addr replace {node.loopback} dev lo")
            self._checked_cmd(
                router, "test \"$(sysctl -n net.ipv4.ip_forward)\" = 1"
            )
            self._checked_cmd(
                router, "test \"$(sysctl -n net.ipv4.conf.all.rp_filter)\" = 0"
            )

        for link in self.plan.links:
            runtime = self.runtime_links[link.link_id]
            left_router = self.routers[link.left]
            right_router = self.routers[link.right]
            self._checked_cmd(
                left_router,
                f"ip addr flush dev {runtime.left_interface} && "
                f"ip addr add {link.left_ip} dev {runtime.left_interface} && "
                f"ip link set {runtime.left_interface} up",
            )
            self._checked_cmd(
                right_router,
                f"ip addr flush dev {runtime.right_interface} && "
                f"ip addr add {link.right_ip} dev {runtime.right_interface} && "
                f"ip link set {runtime.right_interface} up",
            )
            interface_inventory[link.left].append(
                RouterInterface(runtime.left_interface, link.subnet)
            )
            interface_inventory[link.right].append(
                RouterInterface(runtime.right_interface, link.subnet)
            )

        for node_id, interfaces in interface_inventory.items():
            node = node_by_id[node_id]
            arguments = ospf_vtysh_arguments(
                router_id=node.loopback,
                interfaces=interfaces,
                area=self.plan.ospf_area,
                hello_interval_seconds=self.config.ospf_hello_seconds,
                dead_interval_seconds=self.config.ospf_dead_seconds,
            )
            self._checked_cmd(
                self.routers[node_id],
                render_vtysh_command(arguments),
            )

    def configure_queue_disciplines(self) -> dict[str, dict[str, str]]:
        """Install CoDel/FQ-CoDel below TCLink's HTB and NetEm qdiscs."""
        if self.config.queue_profile == "htb_netem_codel":
            aqm_kind = "codel"
        elif self.config.queue_profile == "htb_netem_fq_codel":
            aqm_kind = "fq_codel"
        else:
            raise UnderlayRuntimeError(
                f"Unsupported queue profile: {self.config.queue_profile}"
            )

        ecn = " ecn" if self.config.codel_ecn else " noecn"
        configured: dict[str, dict[str, str]] = {}
        for link in self.plan.links:
            runtime = self.runtime_links[link.link_id]
            for node_id, interface in (
                (link.left, runtime.left_interface),
                (link.right, runtime.right_interface),
            ):
                router = self.routers[node_id]
                before = self._clean_terminal_output(
                    router.cmd(f"tc qdisc show dev {interface}") or ""
                ).strip()
                if "htb 5:" not in before or "netem 10:" not in before:
                    raise UnderlayRuntimeError(
                        f"{router.name}:{interface} does not have the expected "
                        f"TCLink HTB/NetEm hierarchy:\n{before}"
                    )
                self._checked_cmd(
                    router,
                    f"tc qdisc replace dev {interface} parent 10:1 handle 20: "
                    f"{aqm_kind} limit {self.config.max_queue_packets} "
                    f"target {self.config.codel_target_ms}ms "
                    f"interval {self.config.codel_interval_ms}ms{ecn}",
                )
                after = self._clean_terminal_output(
                    router.cmd(f"tc -s -d qdisc show dev {interface}") or ""
                ).strip()
                if f"qdisc {aqm_kind} 20:" not in after:
                    raise UnderlayRuntimeError(
                        f"{router.name}:{interface} failed to install {aqm_kind}:\n"
                        f"{after}"
                    )
                configured.setdefault(router.name, {})[interface] = after
        return configured

    def wait_for_ospf(self) -> None:
        expected_neighbors = {node.node_id: 0 for node in self.plan.nodes}
        for link in self.plan.links:
            expected_neighbors[link.left] += 1
            expected_neighbors[link.right] += 1

        deadline = time.monotonic() + self.plan.convergence_timeout_seconds
        pending = set(expected_neighbors)
        last_seen: dict[str, int] = {}
        last_routes: dict[str, int] = {}
        while pending and time.monotonic() < deadline:
            for node_id in list(pending):
                output = self.routers[node_id].cmd(
                    "vtysh -c 'show ip ospf neighbor json' 2>/dev/null"
                )
                full_count = self._count_full_ospf_neighbors(output or "")
                last_seen[node_id] = full_count
                route_count = 0
                for target in self.plan.nodes:
                    if target.node_id == node_id:
                        continue
                    target_ip = str(ipaddress.ip_interface(target.loopback).ip)
                    route_output = self._clean_terminal_output(
                        self.routers[node_id].cmd(
                            f"ip route get {target_ip} 2>/dev/null"
                        )
                        or ""
                    )
                    if " dev " in route_output and "-eth" in route_output:
                        route_count += 1
                last_routes[node_id] = route_count
                if (
                    full_count >= expected_neighbors[node_id]
                    and route_count >= len(self.plan.nodes) - 1
                ):
                    pending.remove(node_id)
            if pending:
                time.sleep(1)

        if pending:
            details = ", ".join(
                f"r{node_id}={last_seen.get(node_id, 0)}/"
                f"{expected_neighbors[node_id]} neighbors, "
                f"{last_routes.get(node_id, 0)}/{len(self.plan.nodes) - 1} routes"
                for node_id in sorted(pending)
            )
            raise UnderlayRuntimeError(
                f"OSPF did not converge within "
                f"{self.plan.convergence_timeout_seconds}s: {details}"
            )

    def collect_routing_state(self) -> dict[str, dict[str, str]]:
        commands = {
            "addresses": "ip -br address",
            "routes": "ip route show table main",
            "ospf_neighbors": "vtysh -c 'show ip ospf neighbor'",
            "ospf_routes": "vtysh -c 'show ip ospf route'",
            "qdiscs": "tc -s qdisc show",
        }
        state: dict[str, dict[str, str]] = {}
        for node in self.plan.nodes:
            router = self.routers[node.node_id]
            state[node.container_name] = {
                label: self._clean_terminal_output(router.cmd(command) or "").strip()
                for label, command in commands.items()
            }
        return state

    def collect_qdisc_state(self) -> dict[str, dict[str, dict[str, Any]]]:
        state: dict[str, dict[str, dict[str, Any]]] = {}
        for link in self.plan.links:
            runtime = self.runtime_links[link.link_id]
            for node_id, interface in (
                (link.left, runtime.left_interface),
                (link.right, runtime.right_interface),
            ):
                router = self.routers[node_id]
                raw = self._clean_terminal_output(
                    router.cmd(f"tc -s -d qdisc show dev {interface}") or ""
                ).strip()
                qdiscs: list[dict[str, str | int]] = []
                pattern = re.compile(
                    r"^qdisc\s+(?P<kind>\S+)\s+(?P<handle>\S+)"
                    r"(?P<description>[^\n]*)\n"
                    r"\s*Sent\s+\d+\s+bytes\s+\d+\s+pkt\s+"
                    r"\(dropped\s+(?P<dropped>\d+),\s+"
                    r"overlimits\s+(?P<overlimits>\d+),",
                    re.MULTILINE,
                )
                for match in pattern.finditer(raw):
                    qdiscs.append(
                        {
                            "kind": match.group("kind"),
                            "handle": match.group("handle"),
                            "description": match.group("description").strip(),
                            "dropped": int(match.group("dropped")),
                            "overlimits": int(match.group("overlimits")),
                        }
                    )
                state.setdefault(router.name, {})[interface] = {
                    "raw": raw,
                    "qdiscs": qdiscs,
                }
        return state

    def _diameter_path(self) -> list[str]:
        adjacency = {node.node_id: set() for node in self.plan.nodes}
        for link in self.plan.links:
            adjacency[link.left].add(link.right)
            adjacency[link.right].add(link.left)

        longest: list[str] = []
        for start in adjacency:
            queue = [start]
            parents: dict[str, str | None] = {start: None}
            for current in queue:
                for neighbor in sorted(adjacency[current]):
                    if neighbor not in parents:
                        parents[neighbor] = current
                        queue.append(neighbor)
            for target in parents:
                path: list[str] = []
                cursor: str | None = target
                while cursor is not None:
                    path.append(cursor)
                    cursor = parents[cursor]
                path.reverse()
                if len(path) > len(longest):
                    longest = path
        return longest

    def _interface_counters(self) -> dict[str, dict[str, dict[str, int]]]:
        counters: dict[str, dict[str, dict[str, int]]] = {
            node.node_id: {} for node in self.plan.nodes
        }
        for link in self.plan.links:
            runtime = self.runtime_links[link.link_id]
            for node_id, interface in (
                (link.left, runtime.left_interface),
                (link.right, runtime.right_interface),
            ):
                router = self.routers[node_id]
                rx = int(
                    self._checked_cmd(
                        router,
                        f"cat /sys/class/net/{interface}/statistics/rx_bytes",
                    ).splitlines()[-1]
                )
                tx = int(
                    self._checked_cmd(
                        router,
                        f"cat /sys/class/net/{interface}/statistics/tx_bytes",
                    ).splitlines()[-1]
                )
                counters[node_id][interface] = {"rx_bytes": rx, "tx_bytes": tx}
        return counters

    def _qdisc_drop_counters(
        self,
        kinds: set[str] | None = None,
    ) -> dict[str, dict[str, int]]:
        counters: dict[str, dict[str, int]] = {
            node.node_id: {} for node in self.plan.nodes
        }
        for link in self.plan.links:
            runtime = self.runtime_links[link.link_id]
            for node_id, interface in (
                (link.left, runtime.left_interface),
                (link.right, runtime.right_interface),
            ):
                output = self._clean_terminal_output(
                    self.routers[node_id].cmd(
                        f"tc -s qdisc show dev {interface}"
                    )
                    or ""
                )
                drops: list[int] = []
                current_kind: str | None = None
                for line in output.splitlines():
                    qdisc_match = re.match(r"qdisc\s+(\S+)\s+", line)
                    if qdisc_match:
                        current_kind = qdisc_match.group(1)
                    dropped_match = re.search(r"dropped\s+(\d+)", line)
                    if (
                        dropped_match
                        and current_kind is not None
                        and (kinds is None or current_kind in kinds)
                    ):
                        drops.append(int(dropped_match.group(1)))
                # Parent and child qdiscs can account for the same drop.
                # The maximum avoids counting one packet more than once.
                counters[node_id][interface] = max(drops, default=0)
        return counters

    @staticmethod
    def _ping_metrics(output: str) -> dict[str, float]:
        loss_match = re.search(r"([\d.]+)% packet loss", output)
        rtt_match = re.search(
            r"rtt min/avg/max/mdev = "
            r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms",
            output,
        )
        return {
            "packet_loss_percent": (
                float(loss_match.group(1)) if loss_match else 100.0
            ),
            "rtt_avg_ms": float(rtt_match.group(2)) if rtt_match else 0.0,
            "rtt_max_ms": float(rtt_match.group(3)) if rtt_match else 0.0,
        }

    def _run_udp_load_case(
        self,
        offered_mbps: float,
        duration_seconds: int,
        port: int,
        source_id: str,
        target_id: str,
    ) -> dict[str, Any]:
        node_by_id = {node.node_id: node for node in self.plan.nodes}
        source = self.routers[source_id]
        target = self.routers[target_id]
        source_ip = str(ipaddress.ip_interface(node_by_id[source_id].loopback).ip)
        target_ip = str(ipaddress.ip_interface(node_by_id[target_id].loopback).ip)
        result_file = f"/tmp/iperf-udp-{port}.json"

        drops_before = self._qdisc_drop_counters()
        aqm_before = self._qdisc_drop_counters({"codel", "fq_codel"})
        self._checked_cmd(target, "pkill -x iperf3 >/dev/null 2>&1 || true")
        self._checked_cmd(
            target, f"iperf3 -s -D -B {target_ip} -p {port} --one-off"
        )
        time.sleep(0.2)
        source.cmd(
            f"rm -f {result_file}; "
            f"iperf3 -c {target_ip} -B {source_ip} -p {port} -u "
            f"-b {offered_mbps}M -t {duration_seconds} -J "
            f">{result_file} 2>&1 &"
        )
        time.sleep(0.5)
        ping_output = self._clean_terminal_output(
            source.cmd(f"ping -c 10 -i 0.2 -W 1 {target_ip} 2>&1") or ""
        )
        deadline = time.monotonic() + duration_seconds + 15
        while time.monotonic() < deadline:
            process_ids = self._clean_terminal_output(
                source.cmd("pgrep -x iperf3 2>/dev/null || true") or ""
            ).strip()
            if not process_ids:
                break
            time.sleep(0.5)
        raw_result = self._clean_terminal_output(
            source.cmd(f"cat {result_file} 2>&1") or ""
        ).strip()
        source.cmd("pkill -x iperf3 >/dev/null 2>&1 || true")
        target.cmd("pkill -x iperf3 >/dev/null 2>&1 || true")

        json_start = raw_result.find("{")
        json_end = raw_result.rfind("}")
        if json_start < 0 or json_end < json_start:
            raise UnderlayRuntimeError(
                f"UDP iperf3 did not return JSON: {raw_result[-500:]}"
            )
        result = json.loads(raw_result[json_start : json_end + 1])
        if "error" in result:
            raise UnderlayRuntimeError(f"UDP iperf3 failed: {result['error']}")

        drops_after = self._qdisc_drop_counters()
        aqm_after = self._qdisc_drop_counters({"codel", "fq_codel"})
        qdisc_drop_delta = sum(
            max(0, value - drops_before[node_id][interface])
            for node_id, interfaces in drops_after.items()
            for interface, value in interfaces.items()
        )
        aqm_drop_delta = sum(
            max(0, value - aqm_before[node_id][interface])
            for node_id, interfaces in aqm_after.items()
            for interface, value in interfaces.items()
        )
        end = result.get("end", {})
        received = end.get("sum_received", end.get("sum", {}))
        return {
            "offered_mbps": offered_mbps,
            "receiver_mbps": round(
                float(received.get("bits_per_second", 0.0)) / 1_000_000,
                3,
            ),
            "udp_lost_packets": int(received.get("lost_packets", 0)),
            "udp_packets": int(received.get("packets", 0)),
            "udp_loss_percent": round(
                float(received.get("lost_percent", 0.0)), 3
            ),
            "udp_jitter_ms": round(float(received.get("jitter_ms", 0.0)), 3),
            "qdisc_drop_delta": qdisc_drop_delta,
            "aqm_drop_delta": aqm_drop_delta,
            "concurrent_ping": self._ping_metrics(ping_output),
        }

    def run_load_response_probe(self) -> dict[str, Any]:
        """Measure the lowest-capacity physical link at 80/100/110% load."""
        bottleneck_link = min(
            self.plan.links,
            key=lambda link: (link.bandwidth_mbps, link.link_id),
        )
        source_id = bottleneck_link.left
        target_id = bottleneck_link.right
        bottleneck_mbps = bottleneck_link.bandwidth_mbps
        cases: list[dict[str, Any]] = []
        for index, factor in enumerate(self.config.load_factors):
            if index:
                time.sleep(self.config.load_settle_seconds)
            measurement = self._run_udp_load_case(
                bottleneck_mbps * factor,
                self.config.load_duration_seconds,
                5202 + index,
                source_id,
                target_id,
            )
            measurement["load_factor"] = factor
            cases.append(measurement)
        low, nominal, high = cases
        below_capacity_preserved = (
            low["receiver_mbps"] >= low["offered_mbps"] * 0.95
            and low["udp_loss_percent"] <= 1.0
        )
        return {
            "kind": "real_udp_80_100_110_load_response",
            "source": source_id,
            "target": target_id,
            "path": [source_id, target_id],
            "path_link_ids": [bottleneck_link.link_id],
            "configured_bottleneck_mbps": bottleneck_mbps,
            "configured_link_loss_percent": bottleneck_link.loss_percent,
            "queue_profile": self.config.queue_profile,
            "codel_target_ms": self.config.codel_target_ms,
            "codel_interval_ms": self.config.codel_interval_ms,
            "cases": cases,
            "below_capacity_preserved": below_capacity_preserved,
            "capacity_enforced": (
                below_capacity_preserved
                and nominal["receiver_mbps"] <= bottleneck_mbps * 1.05
                and high["receiver_mbps"] <= bottleneck_mbps * 1.05
            ),
            "congestion_reacted": (
                high["aqm_drop_delta"] > low["aqm_drop_delta"]
                or high["qdisc_drop_delta"] > low["qdisc_drop_delta"]
                or high["udp_loss_percent"] > low["udp_loss_percent"]
                or high["concurrent_ping"]["rtt_avg_ms"]
                > low["concurrent_ping"]["rtt_avg_ms"] * 1.1
            ),
            "aqm_observed": high["aqm_drop_delta"] > 0,
        }

    def run_ditg_probe(self) -> dict[str, Any]:
        """Replay one measured SNDlib OD demand as a real D-ITG packet flow."""
        if not self.plan.demands:
            raise UnderlayRuntimeError(
                "The selected profile contains no SNDlib traffic demands"
            )
        demand = max(
            self.plan.demands,
            key=lambda item: (item.scaled_mbps, item.demand_id),
        )
        source = self.routers[demand.source]
        target = self.routers[demand.target]
        node_by_id = {node.node_id: node for node in self.plan.nodes}
        source_ip = str(
            ipaddress.ip_interface(node_by_id[demand.source].loopback).ip
        )
        target_ip = str(
            ipaddress.ip_interface(node_by_id[demand.target].loopback).ip
        )
        packet_size = self.config.traffic_packet_size_bytes
        packet_rate = demand.scaled_mbps * 1_000_000 / (packet_size * 8)
        sender_log = "/tmp/ditg-sender.log"
        receiver_log = "/tmp/ditg-receiver.log"
        route_output = self._checked_cmd(
            source, f"ip -4 route get {target_ip}"
        )
        route_source_match = re.search(r"\bsrc\s+(\S+)", route_output)
        routed_source_ip = (
            route_source_match.group(1) if route_source_match else source_ip
        )

        self._checked_cmd(source, "command -v ITGSend >/dev/null")
        self._checked_cmd(target, "command -v ITGRecv >/dev/null")
        self._checked_cmd(target, "command -v ITGDec >/dev/null")
        self._checked_cmd(
            target,
            "pkill -x ITGRecv >/dev/null 2>&1 || true; "
            f"rm -f {receiver_log} /tmp/ditg-recv-daemon.log",
        )
        target.cmd(
            "nohup ITGRecv </dev/null "
            ">/tmp/ditg-recv-daemon.log 2>&1 &"
        )
        time.sleep(0.5)
        self._checked_cmd(target, "pgrep -x ITGRecv >/dev/null")
        try:
            sender_output = self._checked_cmd(
                source,
                f"rm -f {sender_log}; "
                f"ITGSend -T {self.config.traffic_protocol} "
                f"-a {target_ip} -Sda {target_ip} "
                f"-C {packet_rate:.9f} -c {packet_size} "
                f"-t {self.config.traffic_duration_seconds * 1000} "
                f"-s {self.config.traffic_seed} "
                f"-l {sender_log} -x {receiver_log}",
            )
            time.sleep(0.5)
            decoder_output = self._checked_cmd(
                target, f"ITGDec {receiver_log}"
            )
        finally:
            target.cmd("pkill -x ITGRecv >/dev/null 2>&1 || true")

        def metric(pattern: str, default: float = 0.0) -> float:
            match = re.search(pattern, decoder_output)
            return float(match.group(1)) if match else default

        packets_match = re.search(r"Total packets\s*=\s*(\d+)", decoder_output)
        dropped_match = re.search(
            r"Packets dropped\s*=\s*(\d+)\s+\(([\d.]+)\s*%\)",
            decoder_output,
        )
        total_packets = int(packets_match.group(1)) if packets_match else 0
        if total_packets <= 0:
            daemon_log = self._clean_terminal_output(
                target.cmd("cat /tmp/ditg-recv-daemon.log 2>/dev/null") or ""
            )
            raise UnderlayRuntimeError(
                "D-ITG receiver decoded no packets. "
                f"Sender output: {sender_output}\nReceiver: {daemon_log}"
            )
        return {
            "kind": "real_ditg_sndlib_measured_demand",
            "selection_policy": self.config.traffic_selection_policy,
            "demand_id": demand.demand_id,
            "source": source.name,
            "source_loopback": source_ip,
            "source_address_selected_by_route": routed_source_ip,
            "source_route": route_output,
            "target": target.name,
            "target_loopback": target_ip,
            "dataset_original_mbps": demand.original_mbps,
            "configured_scaled_mbps": demand.scaled_mbps,
            "demand_scale": self.plan.demand_scale,
            "packet_size_bytes": packet_size,
            "configured_packet_rate_pps": round(packet_rate, 6),
            "duration_seconds": self.config.traffic_duration_seconds,
            "seed": self.config.traffic_seed,
            "decoded_packets": total_packets,
            "decoded_average_bitrate_kbps": metric(
                r"Average bitrate\s*=\s*([\d.]+)\s*Kbit/s"
            ),
            "decoded_average_delay_ms": metric(
                r"Average delay\s*=\s*([\d.]+)\s*s"
            )
            * 1000,
            "decoded_average_jitter_ms": metric(
                r"Average jitter\s*=\s*([\d.]+)\s*s"
            )
            * 1000,
            "decoded_dropped_packets": (
                int(dropped_match.group(1)) if dropped_match else 0
            ),
            "decoded_loss_percent": (
                float(dropped_match.group(2)) if dropped_match else 0.0
            ),
            "sender_output": sender_output,
            "decoder_output": decoder_output,
        }

    def run_iperf_probe(self, duration_seconds: int = 3) -> dict[str, Any]:
        """Send a real TCP flow across the longest-hop underlay path."""
        endpoint_path = self._diameter_path()
        if len(endpoint_path) < 2:
            raise UnderlayRuntimeError("iperf probe needs at least two routers")

        node_by_id = {node.node_id: node for node in self.plan.nodes}
        source_id, target_id = endpoint_path[0], endpoint_path[-1]
        source = self.routers[source_id]
        target = self.routers[target_id]
        source_ip = str(ipaddress.ip_interface(node_by_id[source_id].loopback).ip)
        target_ip = str(ipaddress.ip_interface(node_by_id[target_id].loopback).ip)
        capture_id = endpoint_path[1] if len(endpoint_path) > 2 else target_id
        capture = self.routers[capture_id]
        capture_file = "/tmp/underlay-iperf.pcap"
        port = 5201

        before = self._interface_counters()
        capture.cmd(
            f"rm -f {capture_file}; "
            f"tcpdump -i any -nn -U -c 12 -w {capture_file} "
            f"'tcp port {port}' >/tmp/underlay-tcpdump.log 2>&1 &"
        )
        time.sleep(0.5)
        self._checked_cmd(target, f"pkill -x iperf3 >/dev/null 2>&1 || true")
        self._checked_cmd(
            target, f"iperf3 -s -D -B {target_ip} -p {port} --one-off"
        )

        try:
            raw_client = self._clean_terminal_output(
                source.cmd(
                    f"iperf3 -c {target_ip} -B {source_ip} -p {port} "
                    f"-t {duration_seconds} -J 2>&1"
                )
                or ""
            ).strip()
            json_start = raw_client.find("{")
            json_end = raw_client.rfind("}")
            if json_start < 0 or json_end < json_start:
                raise UnderlayRuntimeError(
                    f"iperf3 did not return JSON: {raw_client[-500:]}"
                )
            iperf_result = json.loads(raw_client[json_start : json_end + 1])
            if "error" in iperf_result:
                raise UnderlayRuntimeError(
                    f"iperf3 failed: {iperf_result['error']}"
                )
        finally:
            target.cmd("pkill -x iperf3 >/dev/null 2>&1 || true")

        time.sleep(0.5)
        after = self._interface_counters()
        capture_text = self._clean_terminal_output(
            capture.cmd(f"tcpdump -nn -r {capture_file} 2>&1") or ""
        ).strip()
        capture.cmd("pkill -x tcpdump >/dev/null 2>&1 || true")

        deltas: dict[str, dict[str, dict[str, int]]] = {}
        for node_id, interfaces in after.items():
            deltas[node_id] = {}
            for interface, values in interfaces.items():
                deltas[node_id][interface] = {
                    counter: values[counter] - before[node_id][interface][counter]
                    for counter in ("rx_bytes", "tx_bytes")
                }

        received = iperf_result.get("end", {}).get("sum_received", {})
        sent = iperf_result.get("end", {}).get("sum_sent", {})
        bits_per_second = float(received.get("bits_per_second", 0.0))
        bytes_received = int(received.get("bytes", 0))
        forwarding_threshold = max(100_000, bytes_received // 4)

        active: dict[str, list[tuple[str, dict[str, Any]]]] = {
            node.node_id: [] for node in self.plan.nodes
        }
        for link in self.plan.links:
            runtime = self.runtime_links[link.link_id]
            directions = (
                (
                    link.left,
                    link.right,
                    runtime.left_interface,
                    runtime.right_interface,
                ),
                (
                    link.right,
                    link.left,
                    runtime.right_interface,
                    runtime.left_interface,
                ),
            )
            for left, right, left_interface, right_interface in directions:
                tx_delta = deltas[left][left_interface]["tx_bytes"]
                rx_delta = deltas[right][right_interface]["rx_bytes"]
                if min(tx_delta, rx_delta) >= forwarding_threshold:
                    active[left].append(
                        (
                            right,
                            {
                                "from": node_by_id[left].container_name,
                                "to": node_by_id[right].container_name,
                                "link_id": link.link_id,
                                "egress_interface": left_interface,
                                "ingress_interface": right_interface,
                                "tx_delta_bytes": tx_delta,
                                "rx_delta_bytes": rx_delta,
                                "bandwidth_mbps": link.bandwidth_mbps,
                                "forwarded": True,
                            },
                        )
                    )

        queue = [source_id]
        parents: dict[str, tuple[str, dict[str, Any]] | None] = {source_id: None}
        for current in queue:
            if current == target_id:
                break
            for neighbor, hop in active[current]:
                if neighbor not in parents:
                    parents[neighbor] = (current, hop)
                    queue.append(neighbor)

        actual_path: list[str] = []
        path_checks: list[dict[str, Any]] = []
        if target_id in parents:
            cursor = target_id
            reverse_hops: list[dict[str, Any]] = []
            while parents[cursor] is not None:
                parent, hop = parents[cursor]
                reverse_hops.append(hop)
                actual_path.append(cursor)
                cursor = parent
            actual_path.append(source_id)
            actual_path.reverse()
            path_checks = list(reversed(reverse_hops))

        return {
            "kind": "real_tcp_iperf3",
            "source": node_by_id[source_id].container_name,
            "source_loopback": source_ip,
            "target": node_by_id[target_id].container_name,
            "target_loopback": target_ip,
            "path": [node_by_id[node_id].container_name for node_id in actual_path],
            "duration_seconds": duration_seconds,
            "configured_bottleneck_mbps": (
                min(item["bandwidth_mbps"] for item in path_checks)
                if path_checks
                else None
            ),
            "measured_receiver_mbps": round(bits_per_second / 1_000_000, 3),
            "bytes_received": bytes_received,
            "retransmits": int(sent.get("retransmits", 0)),
            "forwarding_threshold_bytes": forwarding_threshold,
            "path_counters": path_checks,
            "all_path_hops_forwarded": bool(path_checks)
            and actual_path[0] == source_id
            and actual_path[-1] == target_id,
            "capture_router": node_by_id[capture_id].container_name,
            "tcpdump_excerpt": capture_text.splitlines()[:16],
            "interface_counter_deltas": deltas,
        }

    def verify_loopback_reachability(self) -> list[dict[str, str | bool]]:
        results: list[dict[str, str | bool]] = []
        for source in self.plan.nodes:
            router = self.routers[source.node_id]
            for target in self.plan.nodes:
                if source.node_id == target.node_id:
                    continue
                target_ip = str(ipaddress.ip_interface(target.loopback).ip)
                output = self._clean_terminal_output(
                    router.cmd(f"ping -c 1 -W 1 {target_ip} 2>&1") or ""
                ).strip()
                results.append(
                    {
                        "source": source.container_name,
                        "target": target.container_name,
                        "target_ip": target_ip,
                        "reachable": "1 received" in output
                        or "1 packets received" in output,
                        "output": output,
                    }
                )
        return results
