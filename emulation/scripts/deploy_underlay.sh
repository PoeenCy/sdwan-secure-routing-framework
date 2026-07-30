#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PROFILE="${1:-mini}"
shift || true
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
PLAN_DIR="${REPO_ROOT}/emulation/runtime/underlay/${PROFILE}"

if [[ ! -x "${VENV_PYTHON}" ]]; then
    echo "Missing ${VENV_PYTHON}; run bootstrap_parrot.sh first." >&2
    exit 1
fi

cd "${REPO_ROOT}"
mkdir -p "${PLAN_DIR}"
"${VENV_PYTHON}" -m emulation.underlay.validate \
    --profile "${PROFILE}" \
    --output "${PLAN_DIR}/underlay_plan.json"

if [[ "${EUID}" -eq 0 ]]; then
    "${VENV_PYTHON}" emulation/scripts/preflight_underlay.py
    exec "${VENV_PYTHON}" -m emulation.underlay.run \
        --profile "${PROFILE}" "$@"
else
    sudo "${VENV_PYTHON}" emulation/scripts/preflight_underlay.py
    exec sudo "${VENV_PYTHON}" -m emulation.underlay.run \
        --profile "${PROFILE}" "$@"
fi
