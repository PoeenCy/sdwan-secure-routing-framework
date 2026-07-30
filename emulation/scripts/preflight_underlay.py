from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


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
    parser = argparse.ArgumentParser(description="Check underlay host requirements.")
    parser.add_argument(
        "--runtime",
        choices=("docker", "podman"),
        default="docker",
        help="Containernet is validated with Docker; Podman is diagnostic only.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    failures: list[str] = []
    warnings: list[str] = []

    if not (repo_root / ".venv/bin/python").exists():
        failures.append("Missing .venv; run: python3 -m venv .venv")

    required_commands = ["ip", "tc", "ovs-vsctl", "mn", args.runtime]
    for command in required_commands:
        resolved = shutil.which(command)
        if resolved:
            print(f"OK command {command}: {resolved}")
        else:
            failures.append(f"Missing command: {command}")

    for module in ("yaml", "docker", "mininet"):
        if importlib.util.find_spec(module):
            print(f"OK Python module: {module}")
        else:
            failures.append(f"Missing Python module in active venv: {module}")

    docker = shutil.which("docker")
    if docker:
        status, output = command_output([docker, "version"])
        lowered = output.lower()
        if "emulate docker cli using podman" in lowered:
            failures.append(
                "The docker command is the podman-docker wrapper. "
                "Containernet requires a Docker-compatible daemon/socket."
            )
        elif status != 0:
            failures.append(f"Docker daemon unavailable: {output}")
        else:
            print("OK Docker client and daemon")
            image_status, image_output = command_output(
                [docker, "image", "inspect", "zt-sdwan-router:local"]
            )
            if image_status != 0:
                failures.append(
                    "Missing image zt-sdwan-router:local; run "
                    "emulation/scripts/build_underlay_image.sh"
                )
            else:
                print("OK router image: zt-sdwan-router:local")

    if shutil.which("ovs-vsctl"):
        status, output = command_output(["ovs-vsctl", "show"])
        if status != 0:
            failures.append(f"Open vSwitch database unavailable: {output}")
        else:
            print("OK Open vSwitch database")

    if os.geteuid() != 0:
        warnings.append(
            "Topology is not running as root yet. The deploy script will use sudo."
        )

    for warning in warnings:
        print(f"WARN {warning}")
    for failure in failures:
        print(f"FAIL {failure}")

    if failures:
        print(f"PREFLIGHT FAILED: {len(failures)} blocking issue(s)")
        return 1
    print("PREFLIGHT PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
