from emulation.underlay.frr import (
    RouterInterface,
    ospf_vtysh_arguments,
    render_vtysh_command,
)


def test_ospf_commands_use_point_to_point_and_exact_loopback() -> None:
    arguments = ospf_vtysh_arguments(
        router_id="10.255.0.1/32",
        interfaces=[RouterInterface("r0-eth0", "10.64.0.0/30")],
        area="0.0.0.0",
        hello_interval_seconds=1,
        dead_interval_seconds=4,
    )
    rendered = render_vtysh_command(arguments)

    assert "ip ospf network point-to-point" in rendered
    assert "network 10.255.0.1/32 area 0.0.0.0" in rendered
    assert "network 10.64.0.0/30 area 0.0.0.0" in rendered


def test_ospf_commands_make_cpe_attachment_passive() -> None:
    arguments = ospf_vtysh_arguments(
        router_id="10.255.0.1/32",
        interfaces=[
            RouterInterface("r0-eth0", "10.64.0.0/30"),
            RouterInterface("r0-eth1", "10.65.0.0/30", passive=True),
        ],
        area="0.0.0.0",
        hello_interval_seconds=1,
        dead_interval_seconds=4,
    )
    rendered = render_vtysh_command(arguments)

    assert "network 10.65.0.0/30 area 0.0.0.0" in rendered
    assert "passive-interface r0-eth1" in rendered
    assert "interface r0-eth1" not in arguments
