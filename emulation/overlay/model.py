from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class OverlayConfigurationError(ValueError):
    """Raised when overlay.yaml is unsafe or internally inconsistent."""


@dataclass(frozen=True)
class WanAttachment:
    name: str
    router: str
    subnet: str
    router_ip: str
    cpe_ip: str
    route_table: int


@dataclass(frozen=True)
class Site:
    site_id: str
    label: str
    dpid: int
    management_ip: str
    lan_subnet: str
    gateway_ip: str
    gateway_mac: str
    host_ip: str
    host_mac: str
    wans: dict[str, WanAttachment]


@dataclass(frozen=True)
class TunnelEndpoint:
    site: str
    wan: str
    port: str
    ofport: int


@dataclass(frozen=True)
class Tunnel:
    tunnel_id: str
    path: str
    key: int
    left: TunnelEndpoint
    right: TunnelEndpoint


@dataclass(frozen=True)
class Policy:
    policy_id: str
    source: str
    destination: str
    tunnel: str
    bidirectional: bool


@dataclass(frozen=True)
class OverlayConfig:
    source_path: Path
    controller: dict[str, Any]
    management: dict[str, Any]
    containers: dict[str, Any]
    sites: dict[str, Site]
    tunnels: tuple[Tunnel, ...]
    policies: tuple[Policy, ...]

    @property
    def site_by_dpid(self) -> dict[int, Site]:
        return {site.dpid: site for site in self.sites.values()}

    @property
    def tunnel_by_id(self) -> dict[str, Tunnel]:
        return {tunnel.tunnel_id: tunnel for tunnel in self.tunnels}


def _required(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise OverlayConfigurationError(f"Missing '{key}' in {context}")
    return mapping[key]


def _ipv4_interface(value: Any, context: str) -> ipaddress.IPv4Interface:
    try:
        result = ipaddress.ip_interface(str(value))
    except ValueError as exc:
        raise OverlayConfigurationError(f"Invalid IPv4 interface in {context}") from exc
    if not isinstance(result, ipaddress.IPv4Interface):
        raise OverlayConfigurationError(f"Only IPv4 is supported in {context}")
    return result


def _ipv4_network(value: Any, context: str) -> ipaddress.IPv4Network:
    try:
        result = ipaddress.ip_network(str(value))
    except ValueError as exc:
        raise OverlayConfigurationError(f"Invalid IPv4 network in {context}") from exc
    if not isinstance(result, ipaddress.IPv4Network):
        raise OverlayConfigurationError(f"Only IPv4 is supported in {context}")
    return result


def _endpoint(raw: dict[str, Any], context: str) -> TunnelEndpoint:
    port = str(_required(raw, "port", context))
    if len(port) > 15:
        raise OverlayConfigurationError(f"{context} port exceeds IFNAMSIZ: {port}")
    ofport = int(_required(raw, "ofport", context))
    if not 1 <= ofport <= 65534:
        raise OverlayConfigurationError(f"Invalid OpenFlow port in {context}")
    return TunnelEndpoint(
        site=str(_required(raw, "site", context)),
        wan=str(_required(raw, "wan", context)),
        port=port,
        ofport=ofport,
    )


def load_overlay_config(path: Path) -> OverlayConfig:
    path = path.resolve()
    with path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise OverlayConfigurationError("overlay.yaml must have version: 1")

    controller = dict(_required(raw, "controller", "root"))
    management = dict(_required(raw, "management", "root"))
    containers = dict(_required(raw, "containers", "root"))
    management_subnet = _ipv4_network(
        _required(management, "subnet", "management"), "management.subnet"
    )
    controller_ip = _ipv4_interface(
        _required(controller, "management_ip", "controller"),
        "controller.management_ip",
    )
    if controller_ip.ip not in management_subnet:
        raise OverlayConfigurationError("Controller is outside management subnet")

    sites: dict[str, Site] = {}
    seen_dpids: set[int] = set()
    seen_networks: list[tuple[str, ipaddress.IPv4Network]] = [
        ("management", management_subnet)
    ]
    for site_id, site_raw_value in dict(_required(raw, "sites", "root")).items():
        site_raw = dict(site_raw_value)
        dpid_text = str(_required(site_raw, "dpid", f"site {site_id}"))
        try:
            dpid = int(dpid_text, 16)
        except ValueError as exc:
            raise OverlayConfigurationError(
                f"Site {site_id} has invalid hexadecimal dpid"
            ) from exc
        if dpid in seen_dpids:
            raise OverlayConfigurationError(f"Duplicate dpid: {dpid_text}")
        seen_dpids.add(dpid)

        lan = _ipv4_network(
            _required(site_raw, "lan_subnet", f"site {site_id}"),
            f"site {site_id}.lan_subnet",
        )
        gateway = _ipv4_interface(
            _required(site_raw, "gateway_ip", f"site {site_id}"),
            f"site {site_id}.gateway_ip",
        )
        host = _ipv4_interface(
            _required(site_raw, "host_ip", f"site {site_id}"),
            f"site {site_id}.host_ip",
        )
        management_ip = _ipv4_interface(
            _required(site_raw, "management_ip", f"site {site_id}"),
            f"site {site_id}.management_ip",
        )
        if gateway.ip not in lan or host.ip not in lan or gateway.ip == host.ip:
            raise OverlayConfigurationError(
                f"Site {site_id} gateway/host must be distinct members of its LAN"
            )
        if management_ip.ip not in management_subnet:
            raise OverlayConfigurationError(
                f"Site {site_id} is outside management subnet"
            )

        wans: dict[str, WanAttachment] = {}
        for wan_name, wan_raw_value in dict(
            _required(site_raw, "wans", f"site {site_id}")
        ).items():
            wan_raw = dict(wan_raw_value)
            subnet = _ipv4_network(
                _required(wan_raw, "subnet", f"{site_id}.{wan_name}"),
                f"{site_id}.{wan_name}.subnet",
            )
            router_ip = _ipv4_interface(
                _required(wan_raw, "router_ip", f"{site_id}.{wan_name}"),
                f"{site_id}.{wan_name}.router_ip",
            )
            cpe_ip = _ipv4_interface(
                _required(wan_raw, "cpe_ip", f"{site_id}.{wan_name}"),
                f"{site_id}.{wan_name}.cpe_ip",
            )
            if (
                router_ip.ip not in subnet
                or cpe_ip.ip not in subnet
                or router_ip.ip == cpe_ip.ip
            ):
                raise OverlayConfigurationError(
                    f"{site_id}.{wan_name} endpoints are invalid for {subnet}"
                )
            seen_networks.append((f"{site_id}.{wan_name}", subnet))
            wans[str(wan_name)] = WanAttachment(
                name=str(wan_name),
                router=str(_required(wan_raw, "router", f"{site_id}.{wan_name}")),
                subnet=str(subnet),
                router_ip=str(router_ip),
                cpe_ip=str(cpe_ip),
                route_table=int(
                    _required(wan_raw, "route_table", f"{site_id}.{wan_name}")
                ),
            )
        if set(wans) != {"wan1", "wan2"}:
            raise OverlayConfigurationError(
                f"Site {site_id} must define exactly wan1 and wan2"
            )
        seen_networks.append((f"{site_id}.lan", lan))
        sites[str(site_id)] = Site(
            site_id=str(site_id),
            label=str(_required(site_raw, "label", f"site {site_id}")),
            dpid=dpid,
            management_ip=str(management_ip),
            lan_subnet=str(lan),
            gateway_ip=str(gateway),
            gateway_mac=str(
                _required(site_raw, "gateway_mac", f"site {site_id}")
            ).lower(),
            host_ip=str(host),
            host_mac=str(_required(site_raw, "host_mac", f"site {site_id}")).lower(),
            wans=wans,
        )

    for index, (name, network) in enumerate(seen_networks):
        for other_name, other in seen_networks[index + 1 :]:
            if network.overlaps(other):
                raise OverlayConfigurationError(
                    f"Address spaces overlap: {name}={network}, "
                    f"{other_name}={other}"
                )

    tunnels: list[Tunnel] = []
    tunnel_ids: set[str] = set()
    tunnel_keys: set[int] = set()
    site_ofports: dict[str, set[int]] = {site: {1, 2} for site in sites}
    for tunnel_raw_value in list(_required(raw, "tunnels", "root")):
        tunnel_raw = dict(tunnel_raw_value)
        tunnel_id = str(_required(tunnel_raw, "id", "tunnel"))
        key = int(_required(tunnel_raw, "key", f"tunnel {tunnel_id}"))
        left = _endpoint(
            dict(_required(tunnel_raw, "left", f"tunnel {tunnel_id}")),
            f"tunnel {tunnel_id}.left",
        )
        right = _endpoint(
            dict(_required(tunnel_raw, "right", f"tunnel {tunnel_id}")),
            f"tunnel {tunnel_id}.right",
        )
        if tunnel_id in tunnel_ids or key in tunnel_keys:
            raise OverlayConfigurationError(
                f"Duplicate tunnel id or GRE key: {tunnel_id}/{key}"
            )
        tunnel_ids.add(tunnel_id)
        tunnel_keys.add(key)
        if left.site == right.site:
            raise OverlayConfigurationError(f"Tunnel {tunnel_id} loops to one site")
        for endpoint in (left, right):
            if endpoint.site not in sites:
                raise OverlayConfigurationError(
                    f"Tunnel {tunnel_id} refers to unknown site {endpoint.site}"
                )
            if endpoint.wan not in sites[endpoint.site].wans:
                raise OverlayConfigurationError(
                    f"Tunnel {tunnel_id} refers to unknown WAN "
                    f"{endpoint.site}.{endpoint.wan}"
                )
            if endpoint.ofport in site_ofports[endpoint.site]:
                raise OverlayConfigurationError(
                    f"Duplicate ofport {endpoint.ofport} on {endpoint.site}"
                )
            site_ofports[endpoint.site].add(endpoint.ofport)
        tunnels.append(
            Tunnel(
                tunnel_id=tunnel_id,
                path=str(_required(tunnel_raw, "path", f"tunnel {tunnel_id}")),
                key=key,
                left=left,
                right=right,
            )
        )

    policies: list[Policy] = []
    for policy_raw_value in list(_required(raw, "policies", "root")):
        policy_raw = dict(policy_raw_value)
        policy_id = str(_required(policy_raw, "id", "policy"))
        source = str(_required(policy_raw, "source", f"policy {policy_id}"))
        destination = str(
            _required(policy_raw, "destination", f"policy {policy_id}")
        )
        tunnel = str(_required(policy_raw, "tunnel", f"policy {policy_id}"))
        if source not in sites or destination not in sites:
            raise OverlayConfigurationError(f"Policy {policy_id} has unknown site")
        if tunnel not in tunnel_ids:
            raise OverlayConfigurationError(f"Policy {policy_id} has unknown tunnel")
        tunnel_object = next(item for item in tunnels if item.tunnel_id == tunnel)
        if {source, destination} != {
            tunnel_object.left.site,
            tunnel_object.right.site,
        }:
            raise OverlayConfigurationError(
                f"Policy {policy_id} sites do not match tunnel {tunnel}"
            )
        policies.append(
            Policy(
                policy_id=policy_id,
                source=source,
                destination=destination,
                tunnel=tunnel,
                bidirectional=bool(policy_raw.get("bidirectional", False)),
            )
        )

    return OverlayConfig(
        source_path=path,
        controller=controller,
        management=management,
        containers=containers,
        sites=sites,
        tunnels=tuple(tunnels),
        policies=tuple(policies),
    )
