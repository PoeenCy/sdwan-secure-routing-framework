from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


class UnderlayConfigurationError(ValueError):
    """Raised when the underlay input cannot produce a safe routed plan."""


@dataclass(frozen=True)
class UnderlayConfig:
    repo_root: Path
    source_path: Path
    topology_name: str
    topology_format: str
    dataset_path: Path
    canonical_url: str
    source_url: str
    source_sha256: str
    expected_provenance: str
    expected_source_note: str
    expected_unit: str
    link_model: str
    parallel_link_policy: str
    traffic_matrix_path: Path
    traffic_matrix_archive_url: str
    traffic_matrix_archive_sha256: str
    traffic_matrix_archive_member: str
    traffic_matrix_sha256: str
    traffic_matrix_time: str
    traffic_matrix_granularity: str
    traffic_matrix_unit: str
    provenance_readme_path: Path
    provenance_readme_url: str
    provenance_readme_sha256: str
    profiles: dict[str, tuple[str, ...]]
    point_to_point_pool: ipaddress.IPv4Network
    point_to_point_prefix: int
    loopback_pool: ipaddress.IPv4Network
    loopback_prefix: int
    capacity_scale: float
    demand_scale: float
    scaling_policy: str
    stretch_factor: float
    fiber_speed_km_s: float
    loss_percent: float
    max_queue_packets: int
    queue_profile: str
    codel_target_ms: float
    codel_interval_ms: float
    codel_ecn: bool
    load_factors: tuple[float, ...]
    load_duration_seconds: int
    load_settle_seconds: int
    traffic_tool: str
    traffic_tool_version: str
    traffic_tool_url: str
    traffic_tool_sha256: str
    traffic_selection_policy: str
    traffic_patch_path: Path
    traffic_protocol: str
    traffic_packet_size_bytes: int
    traffic_duration_seconds: int
    traffic_seed: float
    ospf_area: str
    ospf_hello_seconds: int
    ospf_dead_seconds: int
    convergence_timeout_seconds: int
    router_image: str
    router_command: str
    container_capabilities: tuple[str, ...]
    container_sysctls: dict[str, str]


@dataclass(frozen=True)
class UnderlayNode:
    node_id: str
    container_name: str
    label: str
    latitude: float
    longitude: float
    loopback: str


@dataclass(frozen=True)
class UnderlayLink:
    link_id: str
    source_edge_key: str
    left: str
    right: str
    subnet: str
    left_ip: str
    right_ip: str
    link_type: str
    bandwidth_mbps: float
    bandwidth_source: str
    distance_km: float
    delay_ms: float
    delay_source: str
    loss_percent: float
    max_queue_packets: int
    queue_profile: str


@dataclass(frozen=True)
class TrafficDemand:
    demand_id: str
    source: str
    target: str
    original_mbps: float
    scaled_mbps: float
    source_kind: str


@dataclass(frozen=True)
class UnderlayPlan:
    topology_name: str
    topology_format: str
    profile: str
    canonical_url: str
    source_url: str
    source_sha256: str
    source_provenance: str
    source_note: str
    source_unit: str
    link_model: str
    parallel_link_policy: str
    capacity_scale: float
    demand_scale: float
    scaling_policy: str
    traffic_matrix_archive_url: str
    traffic_matrix_archive_sha256: str
    traffic_matrix_archive_member: str
    traffic_matrix_sha256: str
    traffic_matrix_time: str
    traffic_matrix_granularity: str
    traffic_matrix_unit: str
    provenance_readme_url: str
    provenance_readme_sha256: str
    queue_profile: str
    configured_random_loss_percent: float
    max_queue_packets: int
    codel_target_ms: float
    codel_interval_ms: float
    codel_ecn: bool
    load_factors: tuple[float, ...]
    load_duration_seconds: int
    load_settle_seconds: int
    traffic_tool: str
    traffic_tool_version: str
    traffic_tool_url: str
    traffic_tool_sha256: str
    traffic_selection_policy: str
    traffic_patch_sha256: str
    traffic_protocol: str
    traffic_packet_size_bytes: int
    traffic_duration_seconds: int
    traffic_seed: float
    nodes: tuple[UnderlayNode, ...]
    links: tuple[UnderlayLink, ...]
    demands: tuple[TrafficDemand, ...]
    ospf_area: str
    convergence_timeout_seconds: int
    router_image: str
    router_command: str
    container_capabilities: tuple[str, ...]
    container_sysctls: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class _ParsedNode:
    node_id: str
    label: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class _ParsedEdge:
    left: str
    right: str
    edge_key: str
    attributes: dict[str, str]


@dataclass(frozen=True)
class _ParsedGraph:
    attributes: dict[str, str]
    nodes: dict[str, _ParsedNode]
    edges: tuple[_ParsedEdge, ...]


@dataclass(frozen=True)
class _ParsedTrafficMatrix:
    time: str
    granularity: str
    unit: str
    origin: str
    demands: tuple[TrafficDemand, ...]


def _required(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise UnderlayConfigurationError(f"Missing '{key}' in {context}")
    return mapping[key]


def _repo_path(repo_root: Path, value: str) -> Path:
    candidate = (repo_root / value).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise UnderlayConfigurationError(
            f"Path escapes repository root: {value}"
        ) from exc
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_file(
    repo_root: Path,
    relative_path: str,
    expected_sha256: str,
    description: str,
) -> Path:
    path = _repo_path(repo_root, relative_path)
    if not path.is_file():
        raise UnderlayConfigurationError(
            f"{description} not found: {path}. "
            "Run emulation/scripts/fetch_underlay_dataset.py first."
        )
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise UnderlayConfigurationError(
            f"{description} checksum mismatch: expected {expected_sha256}, "
            f"got {actual_sha256}"
        )
    return path


def load_underlay_config(repo_root: Path, config_path: Path) -> UnderlayConfig:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)

    if not isinstance(raw, dict) or raw.get("version") != 2:
        raise UnderlayConfigurationError("underlay.yaml must have version: 2")

    topology = _required(raw, "topology", "root")
    traffic_matrix = _required(raw, "traffic_matrix", "root")
    provenance_readme = _required(
        traffic_matrix, "provenance_readme", "traffic_matrix"
    )
    profiles_raw = _required(raw, "profiles", "root")
    addressing = _required(raw, "addressing", "root")
    scaling = _required(raw, "scaling", "root")
    link_defaults = _required(raw, "link_defaults", "root")
    delay_model = _required(link_defaults, "delay_model", "link_defaults")
    codel = _required(link_defaults, "codel", "link_defaults")
    load_validation = _required(raw, "load_validation", "root")
    traffic_generation = _required(raw, "traffic_generation", "root")
    routing = _required(raw, "routing", "root")
    container = _required(raw, "container", "root")

    profiles: dict[str, tuple[str, ...]] = {}
    for name, value in profiles_raw.items():
        nodes = tuple(str(node) for node in _required(value, "nodes", f"profile {name}"))
        if not nodes:
            raise UnderlayConfigurationError(f"Profile '{name}' has no nodes")
        if len(nodes) != len(set(nodes)):
            raise UnderlayConfigurationError(f"Profile '{name}' contains duplicate nodes")
        profiles[str(name)] = nodes

    point_to_point_pool = ipaddress.ip_network(
        _required(addressing, "point_to_point_pool", "addressing")
    )
    loopback_pool = ipaddress.ip_network(
        _required(addressing, "loopback_pool", "addressing")
    )
    if point_to_point_pool.version != 4 or loopback_pool.version != 4:
        raise UnderlayConfigurationError("Only IPv4 underlay pools are supported")
    if point_to_point_pool.overlaps(loopback_pool):
        raise UnderlayConfigurationError("P2P and loopback address pools overlap")

    topology_format = str(_required(topology, "format", "topology"))
    if topology_format != "sndlib_xml":
        raise UnderlayConfigurationError(
            "Only topology.format=sndlib_xml is supported by version 2"
        )
    expected_sha256 = str(_required(topology, "sha256", "topology")).lower()
    dataset_path = _verified_file(
        repo_root,
        str(_required(topology, "path", "topology")),
        expected_sha256,
        "SNDlib topology",
    )
    traffic_matrix_sha256 = str(
        _required(traffic_matrix, "sha256", "traffic_matrix")
    ).lower()
    traffic_matrix_path = _verified_file(
        repo_root,
        str(_required(traffic_matrix, "path", "traffic_matrix")),
        traffic_matrix_sha256,
        "SNDlib traffic matrix",
    )
    provenance_readme_sha256 = str(
        _required(provenance_readme, "sha256", "provenance_readme")
    ).lower()
    provenance_readme_path = _verified_file(
        repo_root,
        str(_required(provenance_readme, "path", "provenance_readme")),
        provenance_readme_sha256,
        "SNDlib provenance README",
    )

    parallel_link_policy = str(
        _required(topology, "parallel_link_policy", "topology")
    )
    if parallel_link_policy != "preserve":
        raise UnderlayConfigurationError(
            "Only parallel_link_policy=preserve is currently supported"
        )
    if str(_required(delay_model, "type", "delay_model")) != "geodesic_fiber_estimate":
        raise UnderlayConfigurationError(
            "Only delay_model.type=geodesic_fiber_estimate is supported"
        )
    link_model = str(_required(topology, "link_model", "topology"))
    if link_model != "bidirected":
        raise UnderlayConfigurationError(
            "Abilene runtime requires topology.link_model=bidirected"
        )
    capacity_scale = float(
        _required(scaling, "capacity_divisor", "scaling")
    )
    demand_scale = float(_required(scaling, "demand_divisor", "scaling"))
    scaling_policy = str(_required(scaling, "policy", "scaling"))
    if capacity_scale <= 0 or demand_scale <= 0:
        raise UnderlayConfigurationError("Scaling divisors must be positive")
    if scaling_policy != "preserve_utilization":
        raise UnderlayConfigurationError(
            "Only scaling.policy=preserve_utilization is supported"
        )
    if not math.isclose(capacity_scale, demand_scale):
        raise UnderlayConfigurationError(
            "Capacity and demand divisors must match to preserve utilization"
        )
    queue_profile = str(
        _required(link_defaults, "queue_profile", "link_defaults")
    )
    if queue_profile not in {"htb_netem_codel", "htb_netem_fq_codel"}:
        raise UnderlayConfigurationError(
            "queue_profile must be htb_netem_codel or htb_netem_fq_codel"
        )
    load_factors = tuple(
        float(value)
        for value in _required(
            load_validation, "offered_load_factors", "load_validation"
        )
    )
    if load_factors != (0.8, 1.0, 1.1):
        raise UnderlayConfigurationError(
            "load_validation.offered_load_factors must be [0.8, 1.0, 1.1]"
        )
    traffic_tool = str(
        _required(traffic_generation, "tool", "traffic_generation")
    )
    traffic_protocol = str(
        _required(traffic_generation, "protocol", "traffic_generation")
    )
    if traffic_tool != "D-ITG" or traffic_protocol != "UDP":
        raise UnderlayConfigurationError(
            "Underlay traffic validation requires D-ITG over UDP"
        )
    traffic_selection_policy = str(
        _required(
            traffic_generation,
            "demand_selection_policy",
            "traffic_generation",
        )
    )
    if (
        traffic_selection_policy
        != "maximum_scaled_demand_in_selected_profile"
    ):
        raise UnderlayConfigurationError(
            "Unsupported traffic_generation.demand_selection_policy"
        )
    traffic_seed = float(
        _required(traffic_generation, "seed", "traffic_generation")
    )
    if not 0 < traffic_seed < 1:
        raise UnderlayConfigurationError("D-ITG seed must satisfy 0 < seed < 1")
    traffic_patch_path = _repo_path(
        repo_root,
        str(
            _required(
                traffic_generation,
                "compatibility_patch",
                "traffic_generation",
            )
        ),
    )
    if not traffic_patch_path.is_file():
        raise UnderlayConfigurationError(
            f"D-ITG compatibility patch not found: {traffic_patch_path}"
        )

    return UnderlayConfig(
        repo_root=repo_root,
        source_path=config_path,
        topology_name=str(_required(topology, "name", "topology")),
        topology_format=topology_format,
        dataset_path=dataset_path,
        canonical_url=str(_required(topology, "canonical_url", "topology")),
        source_url=str(_required(topology, "source_url", "topology")),
        source_sha256=expected_sha256,
        expected_provenance=str(_required(topology, "provenance", "topology")),
        expected_source_note=str(_required(topology, "source_note", "topology")),
        expected_unit=str(_required(topology, "expected_unit", "topology")),
        link_model=link_model,
        parallel_link_policy=parallel_link_policy,
        traffic_matrix_path=traffic_matrix_path,
        traffic_matrix_archive_url=str(
            _required(traffic_matrix, "archive_url", "traffic_matrix")
        ),
        traffic_matrix_archive_sha256=str(
            _required(traffic_matrix, "archive_sha256", "traffic_matrix")
        ).lower(),
        traffic_matrix_archive_member=str(
            _required(traffic_matrix, "archive_member", "traffic_matrix")
        ),
        traffic_matrix_sha256=traffic_matrix_sha256,
        traffic_matrix_time=str(
            _required(traffic_matrix, "expected_time", "traffic_matrix")
        ),
        traffic_matrix_granularity=str(
            _required(traffic_matrix, "expected_granularity", "traffic_matrix")
        ),
        traffic_matrix_unit=str(
            _required(traffic_matrix, "expected_unit", "traffic_matrix")
        ),
        provenance_readme_path=provenance_readme_path,
        provenance_readme_url=str(
            _required(provenance_readme, "source_url", "provenance_readme")
        ),
        provenance_readme_sha256=provenance_readme_sha256,
        profiles=profiles,
        point_to_point_pool=point_to_point_pool,
        point_to_point_prefix=int(
            _required(addressing, "point_to_point_prefix", "addressing")
        ),
        loopback_pool=loopback_pool,
        loopback_prefix=int(
            _required(addressing, "loopback_prefix", "addressing")
        ),
        capacity_scale=capacity_scale,
        demand_scale=demand_scale,
        scaling_policy=scaling_policy,
        stretch_factor=float(
            _required(delay_model, "stretch_factor", "delay_model")
        ),
        fiber_speed_km_s=float(
            _required(delay_model, "fiber_speed_km_s", "delay_model")
        ),
        loss_percent=float(
            _required(
                link_defaults,
                "configured_random_loss_percent",
                "link_defaults",
            )
        ),
        max_queue_packets=int(
            _required(link_defaults, "max_queue_packets", "link_defaults")
        ),
        queue_profile=queue_profile,
        codel_target_ms=float(_required(codel, "target_ms", "codel")),
        codel_interval_ms=float(_required(codel, "interval_ms", "codel")),
        codel_ecn=bool(_required(codel, "ecn", "codel")),
        load_factors=load_factors,
        load_duration_seconds=int(
            _required(load_validation, "duration_seconds", "load_validation")
        ),
        load_settle_seconds=int(
            _required(load_validation, "settle_seconds", "load_validation")
        ),
        traffic_tool=traffic_tool,
        traffic_tool_version=str(
            _required(traffic_generation, "version", "traffic_generation")
        ),
        traffic_tool_url=str(
            _required(traffic_generation, "source_url", "traffic_generation")
        ),
        traffic_tool_sha256=str(
            _required(traffic_generation, "source_sha256", "traffic_generation")
        ).lower(),
        traffic_selection_policy=traffic_selection_policy,
        traffic_patch_path=traffic_patch_path,
        traffic_protocol=traffic_protocol,
        traffic_packet_size_bytes=int(
            _required(
                traffic_generation,
                "packet_size_bytes",
                "traffic_generation",
            )
        ),
        traffic_duration_seconds=int(
            _required(
                traffic_generation, "duration_seconds", "traffic_generation"
            )
        ),
        traffic_seed=traffic_seed,
        ospf_area=str(_required(routing, "area", "routing")),
        ospf_hello_seconds=int(
            _required(routing, "hello_interval_seconds", "routing")
        ),
        ospf_dead_seconds=int(
            _required(routing, "dead_interval_seconds", "routing")
        ),
        convergence_timeout_seconds=int(
            _required(routing, "convergence_timeout_seconds", "routing")
        ),
        router_image=str(_required(container, "image", "container")),
        router_command=str(_required(container, "command", "container")),
        container_capabilities=tuple(
            str(value)
            for value in _required(container, "capabilities", "container")
        ),
        container_sysctls={
            str(key): str(value)
            for key, value in _required(container, "sysctls", "container").items()
        },
    )


def _sndlib_text(
    parent: ET.Element,
    path: str,
    namespace: dict[str, str],
    context: str,
) -> str:
    value = parent.findtext(path, namespaces=namespace)
    if value is None or not value.strip():
        raise UnderlayConfigurationError(f"SNDlib {context} is missing '{path}'")
    return value.strip()


def _parse_sndlib_topology(path: Path, config: UnderlayConfig) -> _ParsedGraph:
    root = ET.parse(path).getroot()
    namespace = {"s": "http://sndlib.zib.de/network"}
    unit = _sndlib_text(root, "s:meta/s:unit", namespace, "topology metadata")
    origin = _sndlib_text(root, "s:meta/s:origin", namespace, "topology metadata")
    time_value = _sndlib_text(root, "s:meta/s:time", namespace, "topology metadata")
    if unit != config.expected_unit:
        raise UnderlayConfigurationError(
            f"Unexpected SNDlib topology unit: expected {config.expected_unit}, "
            f"got {unit}"
        )

    nodes: dict[str, _ParsedNode] = {}
    node_elements = root.findall(
        "s:networkStructure/s:nodes/s:node", namespace
    )
    for element in node_elements:
        node_id = str(element.attrib["id"])
        try:
            longitude = float(
                _sndlib_text(element, "s:coordinates/s:x", namespace, node_id)
            )
            latitude = float(
                _sndlib_text(element, "s:coordinates/s:y", namespace, node_id)
            )
        except ValueError as exc:
            raise UnderlayConfigurationError(
                f"SNDlib node {node_id} has invalid coordinates"
            ) from exc
        nodes[node_id] = _ParsedNode(
            node_id=node_id,
            label=node_id,
            latitude=latitude,
            longitude=longitude,
        )

    edges: list[_ParsedEdge] = []
    link_elements = root.findall(
        "s:networkStructure/s:links/s:link", namespace
    )
    for element in link_elements:
        link_id = str(element.attrib["id"])
        source = _sndlib_text(element, "s:source", namespace, link_id)
        target = _sndlib_text(element, "s:target", namespace, link_id)
        if source == target:
            raise UnderlayConfigurationError(
                f"SNDlib link {link_id} is a self-loop"
            )
        if source not in nodes or target not in nodes:
            raise UnderlayConfigurationError(
                f"SNDlib link {link_id} references an unknown node"
            )
        capacity_text = _sndlib_text(
            element,
            "s:preInstalledModule/s:capacity",
            namespace,
            link_id,
        )
        try:
            capacity_mbps = float(capacity_text)
        except ValueError as exc:
            raise UnderlayConfigurationError(
                f"SNDlib link {link_id} has invalid pre-installed capacity"
            ) from exc
        if capacity_mbps <= 0:
            raise UnderlayConfigurationError(
                f"SNDlib link {link_id} has no usable pre-installed capacity"
            )
        left, right = sorted((source, target), key=_node_sort_key)
        edges.append(
            _ParsedEdge(
                left=left,
                right=right,
                edge_key=link_id,
                attributes={
                    "CapacityMbps": str(capacity_mbps),
                    "LinkType": "SNDlib preInstalledModule",
                },
            )
        )

    edges.sort(
        key=lambda edge: (
            _node_sort_key(edge.left),
            _node_sort_key(edge.right),
            edge.edge_key,
        )
    )
    return _ParsedGraph(
        attributes={
            "Provenance": config.expected_provenance,
            "Note": config.expected_source_note,
            "Unit": unit,
            "Origin": origin,
            "Time": time_value,
        },
        nodes=nodes,
        edges=tuple(edges),
    )


def _parse_sndlib_traffic_matrix(
    path: Path,
    config: UnderlayConfig,
) -> _ParsedTrafficMatrix:
    root = ET.parse(path).getroot()
    namespace = {"s": "http://sndlib.zib.de/network"}
    time_value = _sndlib_text(
        root, "s:meta/s:time", namespace, "traffic matrix metadata"
    )
    granularity = _sndlib_text(
        root, "s:meta/s:granularity", namespace, "traffic matrix metadata"
    )
    unit = _sndlib_text(
        root, "s:meta/s:unit", namespace, "traffic matrix metadata"
    )
    origin = _sndlib_text(
        root, "s:meta/s:origin", namespace, "traffic matrix metadata"
    )
    expected = (
        (time_value, config.traffic_matrix_time, "time"),
        (granularity, config.traffic_matrix_granularity, "granularity"),
        (unit, config.traffic_matrix_unit, "unit"),
    )
    for actual, wanted, label in expected:
        if actual != wanted:
            raise UnderlayConfigurationError(
                f"Unexpected traffic matrix {label}: expected {wanted}, got {actual}"
            )

    demands: list[TrafficDemand] = []
    seen_ids: set[str] = set()
    for element in root.findall("s:demands/s:demand", namespace):
        demand_id = str(element.attrib["id"])
        if demand_id in seen_ids:
            raise UnderlayConfigurationError(
                f"Duplicate SNDlib demand id: {demand_id}"
            )
        seen_ids.add(demand_id)
        source = _sndlib_text(element, "s:source", namespace, demand_id)
        target = _sndlib_text(element, "s:target", namespace, demand_id)
        try:
            original_mbps = float(
                _sndlib_text(
                    element, "s:demandValue", namespace, demand_id
                )
            )
        except ValueError as exc:
            raise UnderlayConfigurationError(
                f"SNDlib demand {demand_id} has an invalid value"
            ) from exc
        if source == target or original_mbps <= 0:
            raise UnderlayConfigurationError(
                f"SNDlib demand {demand_id} is not a positive OD flow"
            )
        demands.append(
            TrafficDemand(
                demand_id=demand_id,
                source=source,
                target=target,
                original_mbps=round(original_mbps, 6),
                scaled_mbps=round(original_mbps / config.demand_scale, 9),
                source_kind="sndlib:measured_accounting_5min",
            )
        )

    demands.sort(
        key=lambda demand: (
            _node_sort_key(demand.source),
            _node_sort_key(demand.target),
            demand.demand_id,
        )
    )
    return _ParsedTrafficMatrix(
        time=time_value,
        granularity=granularity,
        unit=unit,
        origin=origin,
        demands=tuple(demands),
    )


def _node_sort_key(node_id: str) -> tuple[int, int | str]:
    try:
        return (0, int(node_id))
    except ValueError:
        return (1, node_id)


def _is_connected(nodes: Iterable[str], edges: Iterable[_ParsedEdge]) -> bool:
    node_set = set(nodes)
    if not node_set:
        return False
    adjacency = {node: set() for node in node_set}
    for edge in edges:
        if edge.left in node_set and edge.right in node_set:
            adjacency[edge.left].add(edge.right)
            adjacency[edge.right].add(edge.left)
    seen: set[str] = set()
    pending = [next(iter(node_set))]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(adjacency[node] - seen)
    return seen == node_set


def _usable_hosts(subnet: ipaddress.IPv4Network) -> tuple[str, str]:
    hosts = list(subnet.hosts())
    if len(hosts) < 2:
        raise UnderlayConfigurationError(f"Subnet has fewer than two hosts: {subnet}")
    return str(hosts[0]), str(hosts[1])


def _haversine_km(left: _ParsedNode, right: _ParsedNode) -> float:
    radius_km = 6371.0088
    latitude_1 = math.radians(left.latitude)
    latitude_2 = math.radians(right.latitude)
    delta_latitude = latitude_2 - latitude_1
    delta_longitude = math.radians(right.longitude - left.longitude)
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(haversine))


def _parse_bandwidth_mbps(
    edge: _ParsedEdge, config: UnderlayConfig
) -> tuple[float, str]:
    capacity_text = edge.attributes.get("CapacityMbps")
    try:
        capacity_mbps = float(capacity_text or "")
    except ValueError as exc:
        raise UnderlayConfigurationError(
            f"SNDlib link {edge.edge_key} has invalid capacity metadata"
        ) from exc
    if capacity_mbps <= 0:
        raise UnderlayConfigurationError(
            f"SNDlib link {edge.edge_key} has non-positive capacity"
        )
    return (
        capacity_mbps / config.capacity_scale,
        "sndlib:preInstalledModule.capacity",
    )


def _link_measurements(
    edge: _ParsedEdge,
    nodes: dict[str, _ParsedNode],
    config: UnderlayConfig,
) -> tuple[float, str, float, float, str]:
    bandwidth, bandwidth_source = _parse_bandwidth_mbps(edge, config)
    distance_km = _haversine_km(nodes[edge.left], nodes[edge.right])
    if distance_km <= 0:
        raise UnderlayConfigurationError(
            f"Edge {edge.left}-{edge.right} has invalid geodesic distance"
        )
    delay_ms = (
        config.stretch_factor * distance_km / config.fiber_speed_km_s * 1000
    )
    delay_source = "derived:haversine*stretch_factor/fiber_speed"
    return (
        bandwidth,
        bandwidth_source,
        distance_km,
        delay_ms,
        delay_source,
    )


def build_underlay_plan(config: UnderlayConfig, profile: str) -> UnderlayPlan:
    if profile not in config.profiles:
        choices = ", ".join(sorted(config.profiles))
        raise UnderlayConfigurationError(
            f"Unknown underlay profile '{profile}'. Choices: {choices}"
        )

    if config.topology_format == "sndlib_xml":
        parsed = _parse_sndlib_topology(config.dataset_path, config)
    else:
        raise UnderlayConfigurationError(
            f"Unsupported topology format: {config.topology_format}"
        )
    traffic_matrix = _parse_sndlib_traffic_matrix(
        config.traffic_matrix_path, config
    )
    provenance = parsed.attributes.get("Provenance", "")
    source_note = parsed.attributes.get("Note", "")
    if provenance != config.expected_provenance:
        raise UnderlayConfigurationError(
            f"Unexpected dataset provenance: {provenance!r}"
        )
    if source_note != config.expected_source_note:
        raise UnderlayConfigurationError(
            f"Unexpected dataset note: {source_note!r}"
        )
    traffic_nodes = {
        endpoint
        for demand in traffic_matrix.demands
        for endpoint in (demand.source, demand.target)
    }
    unknown_traffic_nodes = sorted(
        traffic_nodes - parsed.nodes.keys(), key=_node_sort_key
    )
    if unknown_traffic_nodes:
        raise UnderlayConfigurationError(
            "Traffic matrix references nodes absent from topology: "
            f"{unknown_traffic_nodes}"
        )

    selected_nodes = set(config.profiles[profile])
    missing = sorted(selected_nodes - parsed.nodes.keys(), key=_node_sort_key)
    if missing:
        raise UnderlayConfigurationError(
            f"Profile '{profile}' references SNDlib nodes that do not exist: {missing}"
        )
    selected_edges = tuple(
        edge
        for edge in parsed.edges
        if edge.left in selected_nodes and edge.right in selected_nodes
    )
    if not _is_connected(selected_nodes, selected_edges):
        raise UnderlayConfigurationError(
            f"Induced graph for profile '{profile}' is disconnected"
        )
    selected_demands = tuple(
        demand
        for demand in traffic_matrix.demands
        if demand.source in selected_nodes and demand.target in selected_nodes
    )

    node_ids = sorted(selected_nodes, key=_node_sort_key)
    loopback_subnets = list(
        config.loopback_pool.subnets(new_prefix=config.loopback_prefix)
    )
    if len(loopback_subnets) <= len(node_ids):
        raise UnderlayConfigurationError("Loopback pool is too small for the profile")
    nodes = tuple(
        UnderlayNode(
            node_id=node_id,
            container_name=f"r{node_id}",
            label=parsed.nodes[node_id].label,
            latitude=parsed.nodes[node_id].latitude,
            longitude=parsed.nodes[node_id].longitude,
            loopback=(
                f"{loopback_subnets[index].network_address}/"
                f"{config.loopback_prefix}"
            ),
        )
        for index, node_id in enumerate(node_ids, start=1)
    )

    p2p_subnets = list(
        config.point_to_point_pool.subnets(new_prefix=config.point_to_point_prefix)
    )
    if len(p2p_subnets) < len(selected_edges):
        raise UnderlayConfigurationError("P2P pool is too small for the profile")

    links: list[UnderlayLink] = []
    for index, edge in enumerate(selected_edges, start=1):
        subnet = p2p_subnets[index - 1]
        left_ip, right_ip = _usable_hosts(subnet)
        (
            bandwidth,
            bandwidth_source,
            distance_km,
            delay_ms,
            delay_source,
        ) = _link_measurements(edge, parsed.nodes, config)
        links.append(
            UnderlayLink(
                link_id=f"u{index:03d}",
                source_edge_key=edge.edge_key,
                left=edge.left,
                right=edge.right,
                subnet=str(subnet),
                left_ip=f"{left_ip}/{config.point_to_point_prefix}",
                right_ip=f"{right_ip}/{config.point_to_point_prefix}",
                link_type=edge.attributes.get("LinkType", "unknown"),
                bandwidth_mbps=round(bandwidth, 6),
                bandwidth_source=bandwidth_source,
                distance_km=round(distance_km, 6),
                delay_ms=round(delay_ms, 6),
                delay_source=delay_source,
                loss_percent=config.loss_percent,
                max_queue_packets=config.max_queue_packets,
                queue_profile=config.queue_profile,
            )
        )

    return UnderlayPlan(
        topology_name=config.topology_name,
        topology_format=config.topology_format,
        profile=profile,
        canonical_url=config.canonical_url,
        source_url=config.source_url,
        source_sha256=config.source_sha256,
        source_provenance=provenance,
        source_note=source_note,
        source_unit=parsed.attributes["Unit"],
        link_model=config.link_model,
        parallel_link_policy=config.parallel_link_policy,
        capacity_scale=config.capacity_scale,
        demand_scale=config.demand_scale,
        scaling_policy=config.scaling_policy,
        traffic_matrix_archive_url=config.traffic_matrix_archive_url,
        traffic_matrix_archive_sha256=config.traffic_matrix_archive_sha256,
        traffic_matrix_archive_member=config.traffic_matrix_archive_member,
        traffic_matrix_sha256=config.traffic_matrix_sha256,
        traffic_matrix_time=traffic_matrix.time,
        traffic_matrix_granularity=traffic_matrix.granularity,
        traffic_matrix_unit=traffic_matrix.unit,
        provenance_readme_url=config.provenance_readme_url,
        provenance_readme_sha256=config.provenance_readme_sha256,
        queue_profile=config.queue_profile,
        configured_random_loss_percent=config.loss_percent,
        max_queue_packets=config.max_queue_packets,
        codel_target_ms=config.codel_target_ms,
        codel_interval_ms=config.codel_interval_ms,
        codel_ecn=config.codel_ecn,
        load_factors=config.load_factors,
        load_duration_seconds=config.load_duration_seconds,
        load_settle_seconds=config.load_settle_seconds,
        traffic_tool=config.traffic_tool,
        traffic_tool_version=config.traffic_tool_version,
        traffic_tool_url=config.traffic_tool_url,
        traffic_tool_sha256=config.traffic_tool_sha256,
        traffic_selection_policy=config.traffic_selection_policy,
        traffic_patch_sha256=_sha256(config.traffic_patch_path),
        traffic_protocol=config.traffic_protocol,
        traffic_packet_size_bytes=config.traffic_packet_size_bytes,
        traffic_duration_seconds=config.traffic_duration_seconds,
        traffic_seed=config.traffic_seed,
        nodes=nodes,
        links=tuple(links),
        demands=selected_demands,
        ospf_area=config.ospf_area,
        convergence_timeout_seconds=config.convergence_timeout_seconds,
        router_image=config.router_image,
        router_command=config.router_command,
        container_capabilities=config.container_capabilities,
        container_sysctls=config.container_sysctls,
    )
