#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${WORKSPACE_ROOT}"

set -a
source "${WORKSPACE_ROOT}/config/default.env"
if [[ -f "${WORKSPACE_ROOT}/config/local.env" ]]; then
  source "${WORKSPACE_ROOT}/config/local.env"
fi
set +a

: "${ROBOT_RELAY_HOST:?ROBOT_RELAY_HOST is required; set it in config/local.env or the environment}"

"${LLM_PYTHON}" - <<'PY'
import os
import time

from robot_relay.robot_relay_client import RobotRelayClient

host = os.environ["ROBOT_RELAY_HOST"]
port = int(os.environ.get("ROBOT_RELAY_PORT", "9999"))
timeout = float(os.environ.get("ROBOT_RELAY_TIMEOUT_SEC", "5"))

client = RobotRelayClient(host, port, timeout_sec=timeout)
t0 = time.time()
response = client.health()
dt = (time.time() - t0) * 1000
print(f"robot relay health ok endpoint={host}:{port} round_trip_ms={dt:.1f} response={response}")
PY
