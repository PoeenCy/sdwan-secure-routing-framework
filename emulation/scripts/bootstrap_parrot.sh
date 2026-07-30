#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
VENDOR_DIR="${REPO_ROOT}/emulation/vendor"
CONTAINERNET_DIR="${VENDOR_DIR}/containernet"

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    if [[ "${ID:-}" != "parrot" && "${ID_LIKE:-}" != *"debian"* ]]; then
        echo "This bootstrap targets Parrot/Debian; detected ID=${ID:-unknown}." >&2
        exit 1
    fi
fi

if docker version 2>&1 | grep -qi "Emulate Docker CLI using podman"; then
    echo "The current docker command is provided by podman-docker." >&2
    echo "Containernet's Docker host API is not validated against that wrapper." >&2
    echo "Replace it explicitly, then rerun this script:" >&2
    echo "  sudo apt-get remove podman-docker" >&2
    echo "  sudo apt-get install docker.io" >&2
    exit 2
fi

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ansible \
    build-essential \
    docker.io \
    frr \
    git \
    iproute2 \
    mininet \
    openvswitch-switch \
    python3-dev \
    python3-venv \
    tcpdump

sudo systemctl enable --now docker
sudo systemctl enable --now openvswitch-switch
sudo modprobe openvswitch

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${REPO_ROOT}/emulation/requirements.txt"

mkdir -p "${VENDOR_DIR}"
if [[ ! -d "${CONTAINERNET_DIR}/.git" ]]; then
    git clone --depth 1 https://github.com/containernet/containernet.git \
        "${CONTAINERNET_DIR}"
fi
"${VENV_DIR}/bin/python" -m pip install --editable "${CONTAINERNET_DIR}"
"${VENV_DIR}/bin/python" \
    "${REPO_ROOT}/emulation/scripts/fetch_underlay_dataset.py"

echo "Bootstrap complete."
echo "Next: ${REPO_ROOT}/emulation/scripts/build_underlay_image.sh"
