from __future__ import annotations

import ipaddress
import json
import re
import time
from pathlib import Path
from typing import Any

from emulation.underlay.containernet_builder import (
    ContainernetUnderlay,
    UnderlayRuntimeError,
)
from emulation.underlay.frr import RouterInterface

from .model import OverlayConfig, Site, TunnelEndpoint


class OverlayRuntimeError(RuntimeError):
    """Raised when the real overlay cannot be configured or observed."""


class ContainernetOverlay:
    """Build namespace-isolated CPE, LAN, GRE and telemetry components."""

    def __init__(
        self,
        net: Any,
        underlay: ContainernetUnderlay,
        config: OverlayConfig,
        repo_root: Path,
    ):
        self.net = net
        self.underlay = underlay
        self.config = config
        self.repo_root = repo_root
        self.cpes: dict[str, Any] = {}
        self.hosts: dict[str, Any] = {}
        self.sensors: dict[str, Any] = {}
        self.controller: Any = None
        self.management_switch: Any = None
        self.router_interfaces: dict[tuple[str, str], str] = {}

    @staticmethod
    def _ip(value: str) -> str:
        return str(ipaddress.ip_interface(value).ip)

    @staticmethod
    def _checked_cmd(node: Any, command: str) -> str:
        try:
            return ContainernetUnderlay._checked_cmd(node, command)
        except UnderlayRuntimeError as exc:
            raise OverlayRuntimeError(str(exc)) from exc

    def add_nodes_and_links(self) -> None:
        try:
            from mininet.node import OVSBridge
        except ImportError as exc:
            raise OverlayRuntimeError(
                "Containernet/Mininet is not installed in the active environment"
            ) from exc

        controller_log_dir = (
            self.repo_root
            / "emulation/runtime/overlay/measurements/controller"
        )
        controller_log_dir.mkdir(parents=True, exist_ok=True)
        controller_source = (
            self.repo_root / "emulation/controller/zt_overlay.py"
        ).resolve()
        overlay_config = self.config.source_path.resolve()

        self.management_switch = self.net.addSwitch(
            str(self.config.management["bridge"]),
            cls=OVSBridge,
            protocols="OpenFlow13",
        )
        self.controller = self.net.addDocker(
            "zt-controller",
            dimage=str(self.config.controller["image"]),
            dcmd=str(self.config.controller["command"]),
            environment={"ZT_OVERLAY_CONFIG": "/opt/zt/config/overlay.yaml"},
            volumes=[
                f"{controller_source}:/opt/zt/controller/zt_overlay.py:ro",
                f"{overlay_config}:/opt/zt/config/overlay.yaml:ro",
                f"{controller_log_dir}:/var/log/zt-sdwan:rw",
            ],
            cap_add=["NET_ADMIN", "NET_RAW"],
            rm=True,
        )
        self.net.addLink(
            self.controller,
            self.management_switch,
            intfName1="mgmt0",
        )

        cpe_volumes = []
        if Path("/lib/modules").is_dir():
            cpe_volumes.append("/lib/modules:/lib/modules:ro")

        for site_id, site in self.config.sites.items():
            sensor_log_dir = (
                self.repo_root
                / "emulation/runtime/overlay/measurements/suricata"
                / site_id
            )
            sensor_log_dir.mkdir(parents=True, exist_ok=True)
            self.cpes[site_id] = self.net.addDocker(
                f"cpe-{site_id}",
                dimage=str(self.config.containers["cpe_image"]),
                dcmd=str(self.config.containers["cpe_command"]),
                cap_add=list(self.config.containers["cpe_capabilities"]),
                sysctls={
                    "net.ipv4.ip_forward": "0",
                    "net.ipv4.conf.all.rp_filter": "0",
                    "net.ipv4.conf.default.rp_filter": "0",
                },
                volumes=cpe_volumes,
                rm=True,
            )
            self.hosts[site_id] = self.net.addDocker(
                f"host-{site_id}",
                dimage=str(self.config.containers["endpoint_image"]),
                dcmd=str(self.config.containers["endpoint_command"]),
                cap_add=list(self.config.containers["endpoint_capabilities"]),
                rm=True,
            )
            self.sensors[site_id] = self.net.addDocker(
                f"ids-{site_id}",
                dimage=str(self.config.containers["sensor_image"]),
                dcmd=str(self.config.containers["sensor_command"]),
                cap_add=list(self.config.containers["sensor_capabilities"]),
                volumes=[f"{sensor_log_dir}:/var/log/suricata:rw"],
                rm=True,
            )
            self.net.addLink(
                self.hosts[site_id],
                self.cpes[site_id],
                intfName1="lan0",
                intfName2="access0",
            )
            self.net.addLink(
                self.sensors[site_id],
                self.cpes[site_id],
                intfName1="capture0",
                intfName2="span0",
            )
            self.net.addLink(
                self.cpes[site_id],
                self.management_switch,
                intfName1="mgmt0",
            )
            for wan_name, wan in site.wans.items():
                router_interface = f"{site_id[:3]}-{wan_name[-1]}"
                self.router_interfaces[(site_id, wan_name)] = router_interface
                self.net.addLink(
                    self.underlay.routers[wan.router],
                    self.cpes[site_id],
                    intfName1=router_interface,
                    intfName2=wan_name,
                )

    def configure_layer3(self) -> dict[str, list[RouterInterface]]:
        self._checked_cmd(
            self.controller,
            "ip addr flush dev mgmt0 && "
            f"ip addr add {self.config.controller['management_ip']} dev mgmt0 && "
            "ip link set mgmt0 up",
        )
        extra_interfaces: dict[str, list[RouterInterface]] = {}
        for site_id, site in self.config.sites.items():
            cpe = self.cpes[site_id]
            host = self.hosts[site_id]
            sensor = self.sensors[site_id]
            self._checked_cmd(
                cpe,
                "ip addr flush dev mgmt0 && "
                f"ip addr add {site.management_ip} dev mgmt0 && "
                "ip link set mgmt0 up",
            )
            self._checked_cmd(
                host,
                "ip addr flush dev lan0 && "
                f"ip link set dev lan0 address {site.host_mac} && "
                f"ip addr add {site.host_ip} dev lan0 && "
                "ip link set lan0 up",
            )
            self._checked_cmd(host, "ip route del default 2>/dev/null || true")
            self._checked_cmd(
                host,
                f"ip route replace default via {self._ip(site.gateway_ip)} dev lan0",
            )
            self._checked_cmd(
                sensor,
                "ip addr flush dev capture0 && "
                "ip link set capture0 up && ip link set capture0 promisc on",
            )

            for wan_name, wan in site.wans.items():
                router = self.underlay.routers[wan.router]
                router_interface = self.router_interfaces[(site_id, wan_name)]
                self._checked_cmd(
                    router,
                    f"ip addr flush dev {router_interface} && "
                    f"ip addr add {wan.router_ip} dev {router_interface} && "
                    f"ip link set {router_interface} up",
                )
                self._checked_cmd(
                    cpe,
                    f"ip addr flush dev {wan_name} && "
                    f"ip addr add {wan.cpe_ip} dev {wan_name} && "
                    f"ip link set {wan_name} up",
                )
                cpe_ip = self._ip(wan.cpe_ip)
                router_ip = self._ip(wan.router_ip)
                self._checked_cmd(
                    cpe,
                    f"ip route replace table {wan.route_table} "
                    f"{wan.subnet} dev {wan_name} src {cpe_ip} && "
                    f"ip route replace table {wan.route_table} default "
                    f"via {router_ip} dev {wan_name} && "
                    f"ip rule add from {cpe_ip}/32 table {wan.route_table}",
                )
                extra_interfaces.setdefault(wan.router, []).append(
                    RouterInterface(
                        name=router_interface,
                        subnet=wan.subnet,
                        passive=True,
                    )
                )
        return extra_interfaces

    def verify_wan_reachability(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tunnel in self.config.tunnels:
            left_site = self.config.sites[tunnel.left.site]
            right_site = self.config.sites[tunnel.right.site]
            left_wan = left_site.wans[tunnel.left.wan]
            right_wan = right_site.wans[tunnel.right.wan]
            output = self._checked_cmd(
                self.cpes[left_site.site_id],
                f"ping -c 2 -W 2 -I {self._ip(left_wan.cpe_ip)} "
                f"{self._ip(right_wan.cpe_ip)}",
            )
            results.append(
                {
                    "tunnel": tunnel.tunnel_id,
                    "source": self._ip(left_wan.cpe_ip),
                    "destination": self._ip(right_wan.cpe_ip),
                    "reachable": " 0% packet loss" in output,
                    "output": output,
                }
            )
        failed = [result for result in results if not result["reachable"]]
        if failed:
            raise OverlayRuntimeError(
                f"{len(failed)} CPE WAN endpoint reachability checks failed"
            )
        return results

    def _peer_endpoint(
        self, endpoint: TunnelEndpoint, tunnel: Any
    ) -> TunnelEndpoint:
        return tunnel.right if endpoint == tunnel.left else tunnel.left

    def configure_ovs_and_gre(self) -> None:
        controller_ip = self._ip(str(self.config.controller["management_ip"]))
        controller_port = int(self.config.controller["openflow_port"])
        for site_id, site in self.config.sites.items():
            cpe = self.cpes[site_id]
            self._checked_cmd(cpe, "ovs-vsctl --if-exists del-br br0")
            self._checked_cmd(
                cpe,
                "ovs-vsctl add-br br0 && "
                "ovs-vsctl set bridge br0 protocols=OpenFlow13 "
                "fail_mode=secure "
                f"other-config:datapath-id={site.dpid:016x} "
                "other-config:disable-in-band=true",
            )
            self._checked_cmd(
                cpe,
                "ovs-vsctl add-port br0 access0 "
                "-- set Interface access0 ofport_request=1 && "
                "ovs-vsctl add-port br0 span0 "
                "-- set Interface span0 ofport_request=2 && "
                "ip link set access0 up && ip link set span0 up && "
                "ip link set br0 up",
            )

            for tunnel in self.config.tunnels:
                endpoint = None
                if tunnel.left.site == site_id:
                    endpoint = tunnel.left
                elif tunnel.right.site == site_id:
                    endpoint = tunnel.right
                if endpoint is None:
                    continue
                peer = self._peer_endpoint(endpoint, tunnel)
                local_wan = site.wans[endpoint.wan]
                peer_site = self.config.sites[peer.site]
                peer_wan = peer_site.wans[peer.wan]
                self._checked_cmd(
                    cpe,
                    f"ovs-vsctl add-port br0 {endpoint.port} "
                    f"-- set Interface {endpoint.port} type=gre "
                    f"ofport_request={endpoint.ofport} "
                    f"options:key={tunnel.key} "
                    f"options:local_ip={self._ip(local_wan.cpe_ip)} "
                    f"options:remote_ip={self._ip(peer_wan.cpe_ip)} "
                    "options:df_default=true options:tos=inherit",
                )

            self._checked_cmd(
                cpe,
                "ovs-vsctl -- --id=@access get Port access0 "
                "-- --id=@span get Port span0 "
                f"-- --id=@mirror create Mirror name=mirror-{site_id} "
                "select-src-port=@access select-dst-port=@access "
                "output-port=@span "
                "-- set Bridge br0 mirrors=@mirror",
            )
            self._checked_cmd(
                cpe,
                f"ovs-vsctl set-controller br0 tcp:{controller_ip}:{controller_port} "
                "&& ovs-vsctl set controller br0 connection-mode=out-of-band "
                "inactivity-probe=5000",
            )
            expected_ports = [1, 2]
            expected_ports.extend(
                endpoint.ofport
                for tunnel in self.config.tunnels
                for endpoint in (tunnel.left, tunnel.right)
                if endpoint.site == site_id
            )
            for ofport in expected_ports:
                output = self._checked_cmd(
                    cpe,
                    f"ovs-ofctl -O OpenFlow13 show br0 | grep ' {ofport}('",
                )
                if not output:
                    raise OverlayRuntimeError(
                        f"CPE {site_id} missing requested ofport {ofport}"
                    )

    def start_controller_and_sensors(self) -> None:
        port = int(self.config.controller["openflow_port"])
        self._checked_cmd(
            self.controller,
            "pkill -f '[o]sken-manager' 2>/dev/null || true; "
            "rm -f /var/log/zt-sdwan/controller.log "
            "/var/log/zt-sdwan/tunnel-probes.jsonl; "
            f"nohup osken-manager --ofp-tcp-listen-port {port} "
            "/opt/zt/controller/zt_overlay.py "
            "</dev/null >/var/log/zt-sdwan/controller.log 2>&1 &",
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            process = self.controller.cmd(
                "pgrep -f '[o]sken-manager' 2>/dev/null || true"
            )
            if str(process).strip():
                break
            time.sleep(0.5)
        else:
            log = self.controller.cmd(
                "cat /var/log/zt-sdwan/controller.log 2>/dev/null"
            )
            raise OverlayRuntimeError(f"OS-Ken failed to start:\n{log}")

        for site_id, sensor in self.sensors.items():
            site = self.config.sites[site_id]
            home_net = site.lan_subnet
            self._checked_cmd(
                sensor,
                "rm -f /var/log/suricata/eve.json "
                "/var/log/suricata/fast.log /run/suricata.pid; "
                "suricata -D -c /etc/suricata/suricata.yaml "
                "-i capture0 --pidfile /run/suricata.pid "
                f"--set 'vars.address-groups.HOME_NET=[{home_net}]'",
            )

    def wait_for_openflow(self) -> dict[str, bool]:
        deadline = time.monotonic() + 20
        connected: dict[str, bool] = {}
        while time.monotonic() < deadline:
            connected = {}
            for site_id, cpe in self.cpes.items():
                raw = ContainernetUnderlay._clean_terminal_output(
                    cpe.cmd(
                        "ovs-vsctl --if-exists get Controller br0 is_connected"
                    )
                    or ""
                ).strip()
                connected[site_id] = raw.lower() == "true"
            if all(connected.values()):
                return connected
            time.sleep(0.5)
        logs = self.controller.cmd(
            "cat /var/log/zt-sdwan/controller.log 2>/dev/null"
        )
        raise OverlayRuntimeError(
            f"OpenFlow controller connection failed: {connected}\n{logs}"
        )

    @staticmethod
    def _ping_metrics(output: str) -> dict[str, Any]:
        loss = re.search(r"([\d.]+)% packet loss", output)
        rtt = re.search(
            r"rtt min/avg/max/mdev = "
            r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms",
            output,
        )
        return {
            "loss_percent": float(loss.group(1)) if loss else 100.0,
            "rtt_avg_ms": float(rtt.group(2)) if rtt else None,
            "output": output,
        }

    def verify_policy_forwarding(self) -> dict[str, Any]:
        cases = [
            ("hr", "fin", True, "path-A"),
            ("it", "fin", True, "path-B"),
            ("dmz", "fin", False, "default-deny"),
        ]
        results: list[dict[str, Any]] = []
        for source_id, destination_id, expected, reason in cases:
            destination_ip = self._ip(self.config.sites[destination_id].host_ip)
            output = ContainernetUnderlay._clean_terminal_output(
                self.hosts[source_id].cmd(
                    f"ping -c 3 -W 2 {destination_ip} 2>&1"
                )
                or ""
            )
            metrics = self._ping_metrics(output)
            reachable = metrics["loss_percent"] < 100.0
            results.append(
                {
                    "source": source_id,
                    "destination": destination_id,
                    "expected_reachable": expected,
                    "observed_reachable": reachable,
                    "reason": reason,
                    **metrics,
                }
            )
        mismatches = [
            result
            for result in results
            if result["expected_reachable"] != result["observed_reachable"]
        ]
        if mismatches:
            raise OverlayRuntimeError(
                f"{len(mismatches)} overlay policy checks did not match"
            )
        return {"cases": results, "all_expected": True}

    def verify_underlay_isolation(self) -> dict[str, Any]:
        leaks: dict[str, str] = {}
        for node in self.underlay.plan.nodes:
            output = ContainernetUnderlay._clean_terminal_output(
                self.underlay.routers[node.node_id].cmd(
                    "ip -4 route show | grep '^192\\.168\\.' || true"
                )
                or ""
            ).strip()
            if output:
                leaks[node.node_id] = output
        if leaks:
            raise OverlayRuntimeError(f"Enterprise LAN routes leaked: {leaks}")
        return {
            "lan_routes_in_underlay": 0,
            "routers_checked": len(self.underlay.plan.nodes),
        }

    def verify_gre_transport(self) -> list[dict[str, Any]]:
        """Observe selected A/B outer GRE packets at both underlay attachments."""
        selected = [
            policy
            for policy in self.config.policies
            if policy.source in {"hr", "it"} and policy.destination == "fin"
        ]
        results: list[dict[str, Any]] = []
        for policy in selected:
            tunnel = self.config.tunnel_by_id[policy.tunnel]
            left_site = self.config.sites[tunnel.left.site]
            right_site = self.config.sites[tunnel.right.site]
            left_wan = left_site.wans[tunnel.left.wan]
            right_wan = right_site.wans[tunnel.right.wan]
            left_router = self.underlay.routers[left_wan.router]
            right_router = self.underlay.routers[right_wan.router]
            left_interface = self.router_interfaces[
                (left_site.site_id, tunnel.left.wan)
            ]
            right_interface = self.router_interfaces[
                (right_site.site_id, tunnel.right.wan)
            ]
            outer_source = self._ip(left_wan.cpe_ip)
            outer_destination = self._ip(right_wan.cpe_ip)
            capture_file = f"/tmp/{tunnel.tunnel_id}-gre.txt"
            capture_filter = (
                f"'ip proto 47 and src {outer_source} "
                f"and dst {outer_destination}'"
            )
            for router, interface in (
                (left_router, left_interface),
                (right_router, right_interface),
            ):
                router.cmd(
                    f"rm -f {capture_file}; "
                    f"timeout 8 tcpdump -l -nn -i {interface} -c 1 "
                    f"{capture_filter} >{capture_file} 2>&1 &"
                )

            destination_ip = self._ip(right_site.host_ip)
            self.hosts[left_site.site_id].cmd(
                f"ping -c 2 -W 2 {destination_ip} >/dev/null 2>&1"
            )
            deadline = time.monotonic() + 9
            left_capture = ""
            right_capture = ""
            while time.monotonic() < deadline:
                left_capture = ContainernetUnderlay._clean_terminal_output(
                    left_router.cmd(f"cat {capture_file} 2>/dev/null") or ""
                ).strip()
                right_capture = ContainernetUnderlay._clean_terminal_output(
                    right_router.cmd(f"cat {capture_file} 2>/dev/null") or ""
                ).strip()
                if (
                    f"{outer_source}" in left_capture
                    and f"{outer_destination}" in left_capture
                    and f"{outer_source}" in right_capture
                    and f"{outer_destination}" in right_capture
                ):
                    break
                time.sleep(0.25)
            observed = (
                outer_source in left_capture
                and outer_destination in left_capture
                and outer_source in right_capture
                and outer_destination in right_capture
            )
            results.append(
                {
                    "policy": policy.policy_id,
                    "tunnel": tunnel.tunnel_id,
                    "path": tunnel.path,
                    "outer_source": outer_source,
                    "outer_destination": outer_destination,
                    "source_router": left_wan.router,
                    "destination_router": right_wan.router,
                    "source_capture": left_capture,
                    "destination_capture": right_capture,
                    "observed_at_both_underlay_edges": observed,
                }
            )
        if not all(result["observed_at_both_underlay_edges"] for result in results):
            raise OverlayRuntimeError("GRE was not observed at both underlay edges")
        return results

    def collect_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {"cpes": {}, "hosts": {}, "sensors": {}}
        for site_id, cpe in self.cpes.items():
            state["cpes"][site_id] = {
                "addresses": ContainernetUnderlay._clean_terminal_output(
                    cpe.cmd("ip -br address") or ""
                ).strip(),
                "routes": ContainernetUnderlay._clean_terminal_output(
                    cpe.cmd("ip route show table all") or ""
                ).strip(),
                "ovs": ContainernetUnderlay._clean_terminal_output(
                    cpe.cmd("ovs-vsctl show") or ""
                ).strip(),
                "flows": ContainernetUnderlay._clean_terminal_output(
                    cpe.cmd("ovs-ofctl -O OpenFlow13 dump-flows br0") or ""
                ).strip(),
            }
            state["hosts"][site_id] = {
                "addresses": ContainernetUnderlay._clean_terminal_output(
                    self.hosts[site_id].cmd("ip -br address") or ""
                ).strip(),
                "routes": ContainernetUnderlay._clean_terminal_output(
                    self.hosts[site_id].cmd("ip route") or ""
                ).strip(),
            }
            state["sensors"][site_id] = {
                "process": ContainernetUnderlay._clean_terminal_output(
                    self.sensors[site_id].cmd(
                        "pgrep -a suricata 2>/dev/null || true"
                    )
                    or ""
                ).strip(),
                "capture_rx_packets": int(
                    self._checked_cmd(
                        self.sensors[site_id],
                        "cat /sys/class/net/capture0/statistics/rx_packets",
                    ).splitlines()[-1]
                ),
            }
        state["controller_log"] = ContainernetUnderlay._clean_terminal_output(
            self.controller.cmd(
                "cat /var/log/zt-sdwan/controller.log 2>/dev/null"
            )
            or ""
        ).strip()
        raw_probes = ContainernetUnderlay._clean_terminal_output(
            self.controller.cmd(
                "cat /var/log/zt-sdwan/tunnel-probes.jsonl 2>/dev/null || true"
            )
            or ""
        ).strip()
        state["tunnel_probes"] = [
            json.loads(line) for line in raw_probes.splitlines() if line.strip()
        ]
        return state
