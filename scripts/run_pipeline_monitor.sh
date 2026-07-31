#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"
set -a
# Keep the monitor's robot runtime settings aligned with the pipeline settings.
source "${PROJECT_ROOT}/config/default.env"
if [[ -f "${PROJECT_ROOT}/config/local.env" ]]; then
  source "${PROJECT_ROOT}/config/local.env"
fi
set +a
PYTHON_BIN="${PIPELINE_MONITOR_PYTHON:-${LLM_PYTHON:-${PYTHON:-python3}}}"
exec "${PYTHON_BIN}" -m pipeline_monitor.server "$@"
