#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE_DIR="${REPO_ROOT}/emulation/images/router"

if [[ "${EUID}" -eq 0 ]]; then
    docker build --tag zt-sdwan-router:local "${IMAGE_DIR}"
else
    sudo docker build --tag zt-sdwan-router:local "${IMAGE_DIR}"
fi
