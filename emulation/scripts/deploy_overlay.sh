#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
    echo "Missing ${VENV_PYTHON}; run bootstrap_parrot.sh first." >&2
    exit 1
fi

cd "${REPO_ROOT}"
"${VENV_PYTHON}" -c \
    "from pathlib import Path; from emulation.overlay.model import load_overlay_config; load_overlay_config(Path('emulation/config/overlay.yaml'))"

if [[ "${EUID}" -eq 0 ]]; then
    "${VENV_PYTHON}" emulation/scripts/preflight_overlay.py
    exec "${VENV_PYTHON}" -m emulation.overlay.run "$@"
else
    sudo "${VENV_PYTHON}" emulation/scripts/preflight_overlay.py
    exec sudo "${VENV_PYTHON}" -m emulation.overlay.run "$@"
fi
