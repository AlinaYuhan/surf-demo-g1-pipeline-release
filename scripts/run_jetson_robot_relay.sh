#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELAY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export LD_LIBRARY_PATH="/home/unitree/cyclonedds_ws/install/cyclonedds/lib:/home/unitree/unitree_sdk2-main/thirdparty/lib/aarch64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
: "${UNITREE_NETWORK_INTERFACE:?UNITREE_NETWORK_INTERFACE is required; set the Jetson robot-network interface}"
export UNITREE_NETWORK_INTERFACE
export UNITREE_DOMAIN_ID="${UNITREE_DOMAIN_ID:-0}"
: "${UNITREE_VOICE_PEER:?UNITREE_VOICE_PEER is required; set the Unitree voice peer address}"
export UNITREE_VOICE_PEER
export ROBOT_RELAY_BIND_HOST="${ROBOT_RELAY_BIND_HOST:-0.0.0.0}"
export ROBOT_RELAY_PORT="${ROBOT_RELAY_PORT:-9999}"

exec /usr/bin/python3 -u "${RELAY_ROOT}/robot_relay/jetson_robot_relay.py"
