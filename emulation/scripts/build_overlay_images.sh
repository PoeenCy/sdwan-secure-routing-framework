#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DOCKER=(docker)
if [[ "${EUID}" -ne 0 ]]; then
    DOCKER=(sudo docker)
fi

"${DOCKER[@]}" build \
    -t zt-sdwan-cpe:local \
    "${REPO_ROOT}/emulation/images/cpe"
"${DOCKER[@]}" build \
    -t zt-sdwan-endpoint:local \
    "${REPO_ROOT}/emulation/images/endpoint"
"${DOCKER[@]}" build \
    -t zt-sdwan-controller:local \
    "${REPO_ROOT}/emulation/images/controller"
"${DOCKER[@]}" build \
    -t zt-sdwan-sensor:local \
    "${REPO_ROOT}/emulation/images/sensor"

"${DOCKER[@]}" image inspect \
    zt-sdwan-cpe:local \
    zt-sdwan-endpoint:local \
    zt-sdwan-controller:local \
    zt-sdwan-sensor:local \
    --format '{{.RepoTags}} {{.Id}}'
