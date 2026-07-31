# G1 Relay and Operation / G1 中继与操作

> 中文摘要：推荐链路由 WSL/主机运行语音和 LLM，Jetson 在 G1 网络上
> 运行 `robot_relay/jetson_robot_relay.py`，代理音频、灯光和动作。这样可避免 WSL 直接
> 初始化 Unitree 音频/DDS 时的网卡、组播和原生库问题。

## Topology

```text
G1 external microphone --UDP--> host/WSL SURF voice runtime
host/WSL LLM + TTS ----TCP----> Jetson relay :9999
Jetson relay --------Unitree--> G1 audio, lights, arm actions
```

`UNITREE_BACKEND=relay` is the recommended public configuration. Direct DDS is
retained as an advanced compatibility mode, not the default.

## Host configuration

Set these in `config/local.env`:

```bash
VOICE_AUDIO_SOURCE="robot"
VOICE_ROBOT_MIC_IF="<host robot-network IP>"
VOICE_ROBOT_MIC_PORT="5556"
ROBOT_RELAY_HOST="<Jetson host or IP>"
ROBOT_RELAY_PORT="9999"
UNITREE_BACKEND="relay"
```

Check connectivity before starting the full pipeline:

```bash
./scripts/check_robot_relay.sh
```

## Jetson relay

On the Jetson, use its installed Unitree SDK/CycloneDDS runtime and set the
machine-specific values explicitly:

```bash
export UNITREE_NETWORK_INTERFACE="<interface-connected-to-g1>"
export UNITREE_VOICE_PEER="<unitree-voice-peer-address>"
export ROBOT_RELAY_BIND_HOST="0.0.0.0"
export ROBOT_RELAY_PORT="9999"
./scripts/run_jetson_robot_relay.sh
```

The launcher uses the current deployment's native library locations under
`/home/unitree/`. If another Jetson image uses different locations, adjust the
launcher locally rather than committing one machine's paths as universal
defaults.

The relay port is an unauthenticated control endpoint intended for a trusted,
isolated robot network. Do not expose it to the public Internet.

## Robot microphone runtime

`scripts/deploy_robot_mic_runtime.sh` deploys the microphone streamer over SSH.
It expects a machine-local key (default `~/.ssh/surf_robot_ed25519`) and the
`unitree` account. The Monitor checks and starts this path as part of robot
readiness.

The current beamforming deployment script references
`research/beamforming/teacher_reference_20260630/DCF_Targ7_runtime.npz`.
Redistribution permission for that teacher-provided filter is unresolved, so it
is a release blocker. Do not publish or deploy that asset to a new recipient
until permission is documented. A local operator may select a non-beamforming
processing mode where supported, or provide an independently licensed filter.

## Monitor operation

Start locally:

```bash
./scripts/run_pipeline_monitor.sh --host 127.0.0.1 --port 8766
```

Then open [http://127.0.0.1:8766/](http://127.0.0.1:8766/). The server default
without arguments is port 8765.

Recommended operator sequence:

1. Confirm relay and microphone components report `ready`.
2. Choose turn and first-turn modes while Pipeline is stopped.
3. Click **Start**, then wait for Pipeline and components to become ready.
4. Use voice wake-up or **Wake**. After the robot says “我在”, speak normally.
5. Use **Interrupt** to stop current output and immediately listen.
6. Use **End** for an acknowledged close, or **Silent end** for no spoken close.
7. Use **Stop** before changing modes or shutting down the host.

Controls that stop robot output also request arm release. A partial/failure
state means the operator must verify the robot and relay directly; do not assume
the physical action was stopped merely because the browser request returned.

## Direct DDS fallback

For advanced deployments only:

```bash
UNITREE_BACKEND="direct"
UNITREE_NETWORK_INTERFACE="<host-interface-connected-to-g1>"
```

Direct mode requires the host's Unitree Python/C++ SDK and CycloneDDS routing to
match the robot network. It does not remove the microphone input requirements.
