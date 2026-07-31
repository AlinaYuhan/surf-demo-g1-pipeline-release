#!/usr/bin/env bash
# Launch voice_pipeline_node.  Sources config/default.env for all settings.
# Usage: bash run_node.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

set -a
source "${SCRIPT_DIR}/config/default.env"
set +a

if [[ "${VOICE_AUDIO_SOURCE:-local}" == "robot" && -z "${VOICE_ROBOT_MIC_IF:-}" ]]; then
  echo "VOICE_ROBOT_MIC_IF is required when VOICE_AUDIO_SOURCE=robot" >&2
  exit 2
fi

export HF_HUB_OFFLINE=1
export ROS_DOMAIN_ID="${UNITREE_DOMAIN_ID}"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}"
if [[ -n "${UNITREE_VOICE_PEER:-}" ]]; then
  export CYCLONEDDS_URI="<CycloneDDS><Domain><General><AllowMulticast>false</AllowMulticast></General><Discovery><Peers><Peer address=\"${UNITREE_VOICE_PEER}\"/></Peers></Discovery></Domain></CycloneDDS>"
fi

set +u
source /opt/ros/jazzy/setup.bash
set -u

exec "${VOICE_PYTHON}" ros_nodes/voice_pipeline_node.py
