from __future__ import annotations

import ipaddress
from pathlib import Path

from emulation.underlay.model import build_underlay_plan, load_underlay_config


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "emulation/config/underlay.yaml"


def test_mini_plan_is_three_router_chain() -> None:
    config = load_underlay_config(REPO_ROOT, CONFIG_PATH)
    plan = build_underlay_plan(config, "mini")

    assert [node.node_id for node in plan.nodes] == [
        "ATLAng",
        "CHINng",
        "IPLSng",
    ]
    assert len(plan.links) == 2
    assert {
        frozenset((link.left, link.right)) for link in plan.links
    } == {
        frozenset(("ATLAng", "IPLSng")),
        frozenset(("CHINng", "IPLSng")),
    }
    assert all(
        link.bandwidth_source == "sndlib:preInstalledModule.capacity"
        for link in plan.links
    )
    assert all(
        link.delay_source.startswith("derived:haversine")
        for link in plan.links
    )
    assert all(link.queue_profile == "htb_netem_codel" for link in plan.links)
    assert len(plan.demands) == 6
    assert plan.container_capabilities == ("NET_ADMIN", "NET_RAW", "SYS_ADMIN")
    assert plan.topology_format == "sndlib_xml"
    assert plan.traffic_matrix_time == "20040301-0010"


def test_abilene_plan_has_pinned_scaled_data_and_disjoint_addresses() -> None:
    config = load_underlay_config(REPO_ROOT, CONFIG_PATH)
    plan = build_underlay_plan(config, "abilene")

    assert len(plan.nodes) == 12
    assert len(plan.links) == 15
    assert len(plan.demands) == 131
    assert plan.source_provenance == "SNDlib"
    assert plan.source_unit == "MBITPERSEC"
    assert plan.link_model == "bidirected"
    assert plan.capacity_scale == plan.demand_scale == 100.0
    assert plan.scaling_policy == "preserve_utilization"
    assert {link.bandwidth_mbps for link in plan.links} == {24.8, 99.2}
    assert all(
        demand.scaled_mbps
        == round(demand.original_mbps / plan.demand_scale, 9)
        for demand in plan.demands
    )

    subnets = [ipaddress.ip_network(link.subnet) for link in plan.links]
    assert len(subnets) == len(set(subnets))
    for index, left in enumerate(subnets):
        for right in subnets[index + 1 :]:
            assert not left.overlaps(right)

    loopbacks = [ipaddress.ip_interface(node.loopback).ip for node in plan.nodes]
    assert len(loopbacks) == len(set(loopbacks))
    assert all(link.distance_km > 0 for link in plan.links)
    assert all(link.delay_ms > 0 for link in plan.links)

    expected_sndlib_edges = {
        "ATLAM5_ATLAng": frozenset(("ATLAM5", "ATLAng")),
        "ATLAng_HSTNng": frozenset(("ATLAng", "HSTNng")),
        "ATLAng_IPLSng": frozenset(("ATLAng", "IPLSng")),
        "ATLAng_WASHng": frozenset(("ATLAng", "WASHng")),
        "CHINng_IPLSng": frozenset(("CHINng", "IPLSng")),
        "CHINng_NYCMng": frozenset(("CHINng", "NYCMng")),
        "DNVRng_KSCYng": frozenset(("DNVRng", "KSCYng")),
        "DNVRng_SNVAng": frozenset(("DNVRng", "SNVAng")),
        "DNVRng_STTLng": frozenset(("DNVRng", "STTLng")),
        "HSTNng_KSCYng": frozenset(("HSTNng", "KSCYng")),
        "HSTNng_LOSAng": frozenset(("HSTNng", "LOSAng")),
        "IPLSng_KSCYng": frozenset(("IPLSng", "KSCYng")),
        "LOSAng_SNVAng": frozenset(("LOSAng", "SNVAng")),
        "NYCMng_WASHng": frozenset(("NYCMng", "WASHng")),
        "SNVAng_STTLng": frozenset(("SNVAng", "STTLng")),
    }
    observed_edges = {
        link.source_edge_key: frozenset((link.left, link.right))
        for link in plan.links
    }
    assert observed_edges == expected_sndlib_edges


def test_plan_serialization_records_research_provenance() -> None:
    config = load_underlay_config(REPO_ROOT, CONFIG_PATH)
    plan = build_underlay_plan(config, "mini")
    payload = plan.to_dict()

    assert payload["profile"] == "mini"
    assert payload["links"][0]["subnet"].endswith("/30")
    assert payload["traffic_tool"] == "D-ITG"
    assert payload["traffic_tool_version"] == "2.8.1-r1023"
    assert (
        payload["traffic_selection_policy"]
        == "maximum_scaled_demand_in_selected_profile"
    )
    assert len(payload["traffic_tool_sha256"]) == 64
    assert len(payload["traffic_patch_sha256"]) == 64
    assert payload["load_factors"] == (0.8, 1.0, 1.1)
