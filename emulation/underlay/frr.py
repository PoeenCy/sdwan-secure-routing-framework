from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouterInterface:
    name: str
    subnet: str


def ospf_vtysh_arguments(
    router_id: str,
    interfaces: list[RouterInterface],
    area: str,
    hello_interval_seconds: int,
    dead_interval_seconds: int,
) -> list[str]:
    """Return deterministic vtysh -c arguments for one underlay router."""
    commands = ["configure terminal"]
    for interface in interfaces:
        commands.extend(
            [
                f"interface {interface.name}",
                "ip ospf network point-to-point",
                f"ip ospf hello-interval {hello_interval_seconds}",
                f"ip ospf dead-interval {dead_interval_seconds}",
                "exit",
            ]
        )

    commands.extend(
        [
            "router ospf",
            f"ospf router-id {router_id.split('/')[0]}",
            f"network {router_id} area {area}",
        ]
    )
    commands.extend(
        f"network {interface.subnet} area {area}" for interface in interfaces
    )
    commands.extend(["passive-interface lo", "end", "write memory"])
    return commands


def render_vtysh_command(arguments: list[str]) -> str:
    """Render commands without permitting shell metacharacters from config."""
    for argument in arguments:
        if "'" in argument or "\n" in argument or "\r" in argument:
            raise ValueError(f"Unsafe vtysh argument: {argument!r}")
    return "vtysh " + " ".join(f"-c '{argument}'" for argument in arguments)
