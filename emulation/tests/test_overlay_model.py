from pathlib import Path

from emulation.overlay.model import load_overlay_config


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_overlay_has_isolated_lans_dual_wan_and_unique_ofports() -> None:
    config = load_overlay_config(REPO_ROOT / "emulation/config/overlay.yaml")

    assert set(config.sites) == {"hr", "it", "fin", "dmz"}
    assert all(set(site.wans) == {"wan1", "wan2"} for site in config.sites.values())
    assert len({site.lan_subnet for site in config.sites.values()}) == 4
    assert len(config.tunnels) == 6


def test_policy_steers_hr_to_a_and_it_to_b() -> None:
    config = load_overlay_config(REPO_ROOT / "emulation/config/overlay.yaml")
    tunnels = config.tunnel_by_id
    selected = {policy.source: tunnels[policy.tunnel].path for policy in config.policies}

    assert selected["hr"] == "A"
    assert selected["it"] == "B"
    assert "dmz" not in selected
