from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

from emulation.overlay.model import load_overlay_config


IMAGES = (
    "zt-sdwan-router:local",
    "zt-sdwan-cpe:local",
    "zt-sdwan-endpoint:local",
    "zt-sdwan-controller:local",
    "zt-sdwan-sensor:local",
)


def command_output(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.returncode, completed.stdout.strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    failures: list[str] = []
    warnings: list[str] = []

    try:
        config = load_overlay_config(repo_root / "emulation/config/overlay.yaml")
        print(
            f"OK overlay config: {len(config.sites)} sites, "
            f"{len(config.tunnels)} tunnels"
        )
    except (OSError, ValueError) as exc:
        failures.append(f"Invalid overlay config: {exc}")

    required_commands = [
        "docker",
        "ip",
        "mn",
        "modprobe",
        "ovs-vsctl",
        "tc",
    ]
    for command in required_commands:
        resolved = shutil.which(command)
        if resolved:
            print(f"OK command {command}: {resolved}")
        else:
            failures.append(f"Missing command: {command}")

    for module in ("docker", "mininet", "yaml"):
        if importlib.util.find_spec(module):
            print(f"OK Python module: {module}")
        else:
            failures.append(f"Missing Python module in active venv: {module}")

    if os.geteuid() != 0:
        warnings.append("Run this preflight through the deploy script so it uses root")
    elif shutil.which("modprobe"):
        for module in ("openvswitch", "ip_gre"):
            status, output = command_output(["modprobe", module])
            if status != 0:
                failures.append(f"Cannot load kernel module {module}: {output}")
            else:
                print(f"OK kernel module: {module}")

    docker = shutil.which("docker")
    if docker:
        status, output = command_output([docker, "version"])
        if status != 0:
            failures.append(f"Docker daemon unavailable: {output}")
        else:
            print("OK Docker client and daemon")
            for image in IMAGES:
                image_status, _ = command_output(
                    [docker, "image", "inspect", image]
                )
                if image_status != 0:
                    failures.append(f"Missing image: {image}")
                else:
                    print(f"OK image: {image}")

    if shutil.which("ovs-vsctl"):
        status, output = command_output(["ovs-vsctl", "show"])
        if status != 0:
            failures.append(f"Open vSwitch database unavailable: {output}")
        else:
            print("OK host Open vSwitch database")

    for warning in warnings:
        print(f"WARN {warning}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"OVERLAY PREFLIGHT FAILED: {len(failures)} blocking issue(s)")
        return 1
    print("OVERLAY PREFLIGHT PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
