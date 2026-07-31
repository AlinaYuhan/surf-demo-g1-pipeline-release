# Current Project Architecture / 当前项目架构

> **Current source of truth (2026-07-31).** This document describes the active
> DeepSeek + Jetson relay deployment. Older architecture notes are retained only
> under [`docs/archive/`](archive/README.md).
>
> **中文摘要：** 当前默认主链是 SURF 语音感知、DeepSeek 直连回复、Edge TTS
> 和 Jetson 机器人中继。XJTLU RAG 是保留的可选实验后端，不是默认主链。

## System boundary

```text
Robot side                                Host / WSL2

G1 external microphone -- UDP audio ---> SURF voice runtime
                                          | wake / VAD / ASR / speaker
                                          v
                                     surf_ros_bridge.py
                                          | ROS 2 /audio_msg + context topics
                                          v
                                   llm_surf_context_node.py
                                          | HTTP /infer, /tts
                                          v
                                       llm_server.py
                                          | direct DeepSeek-compatible API
                                          v
                                    unitree_audio_player.py
                                          | relay protocol over TCP
                                          v
Jetson relay ------------------------- robot_relay/jetson_robot_relay.py
  | Unitree DDS / native SDK
  +-------------------------------> G1 audio, lights, predefined actions
```

The host owns conversation state, language-model calls, TTS generation, logging,
and operator controls. The Jetson owns the machine-local Unitree SDK/DDS boundary
for the recommended deployment.

## Runtime components

| Layer | Main implementation | Responsibility |
| --- | --- | --- |
| Audio input and perception | `surf_voice_runtime.py`, `deps/SURF2026_VoiceModule-main/` | Robot microphone input, wake word, VAD, ASR, speaker identity. |
| ROS bridge | `surf_ros_bridge.py` | Publishes SURF results into ROS 2 topics. |
| Conversation orchestration | `llm_surf_context_node.py`, `pipeline_control/`, `first_turn/`, `turn_detection/` | Wake/session state, filtering, multi-turn timing, interrupt/end commands, prompt context. |
| Reply/TTS service | `llm_server.py` | Direct DeepSeek reply by default; TTS endpoint; optional backends. |
| Robot output | `unitree_audio_player.py`, `scripts/g1_robot_skill_command.py` | TTS playback, lights, allow-listed actions/skills. |
| Relay boundary | `robot_relay/` | Host client and Jetson TCP service for Unitree-native operations. |
| Observability/operator UI | `pipeline_log/`, `pipeline_monitor/`, `ui/pipeline_monitor/` | Structured events, latency, readiness, start/stop and session controls. |

## Process orchestration

`scripts/run_pipeline.sh --mode wake` loads configuration and starts user
services through `systemd-run`:

```text
surf-ros-bridge.service
surf-voice-runtime.service
surf-llm-server.service
surf-llm-node.service
surf-llm-audio-player.service
```

When and only when `LLM_REPLY_BACKEND=rag`, it additionally starts:

```text
surf-llm-ollama.service
surf-llm-rag.service
```

`scripts/stop_pipeline.sh` stops the managed services. `scripts/check_pipeline.sh`
checks paths and syntax, and gates Ollama/RAG checks on the selected backend.

## Configuration boundary

- `config/default.env`: safe, machine-independent public defaults.
- `config/local.env.example`: template for each target machine.
- `config/local.env`: ignored secrets, paths, host addresses, and interfaces.
- `project_config.py`: Python-side normalized view of the same contract.
- `deps/SURF2026_VoiceModule-main/config/default.env`: voice-runtime defaults.

The public defaults are `LLM_REPLY_BACKEND=deepseek` and
`UNITREE_BACKEND=relay`. Robot/Jetson endpoint values are intentionally empty
until configured locally. See [Configuration](CONFIGURATION.md).

## State and data

```text
runtime/    Ephemeral control files, status, chat memory, and generated TTS
logs/       Per-session structured pipeline logs
config/local.env
            Local secret and machine configuration
```

These locations are not public release content. Turn mode and first-turn mode
are persisted under `runtime/`; the Monitor only changes them while the pipeline
is stopped.

## Optional, compatibility, and research areas

- `xjtlu-rag-system/`: optional RAG service and approved small databases. It is
  disabled by default due to observed latency and limited benefit.
- `deps/qwen_ros_node_edg_tts/`: a legacy-named compatibility directory. The
  current path still uses its vendored Unitree Python adapter, but not its older
  Qwen reply implementation by default.
- `deps/unitree_g1_action_classifier_package/`: current action adapter plus
  vendored Unitree SDK source.
- `research/`: experiments and analysis, not a dependency of the default reply
  path. Teacher beamforming assets remain publication-blocked pending permission.
- `docs/archive/`: historical information only.

These paths have not been reorganized because launchers and deployment scripts
depend on their established locations.

## Deployment decisions

1. **Direct DeepSeek is the supported default.** It removes local chat-model and
   RAG embedding services from the normal latency path.
2. **Jetson relay is preferred over direct WSL Unitree initialization.** The
   Jetson has the robot-network interface and native SDK libraries; WSL retains
   the application and development environment.
3. **Downloaded models stay outside Git.** KWS, ASR, voiceprint, Ollama, and local
   Qwen assets are installed or cached on the target machine.
4. **Markdown is the documentation front door.** The only project HTML is the
   runtime Monitor UI.

## Related documentation

- [Voice-to-robot call chain](voice_to_robot_call_chain.md)
- [Setup](SETUP.md)
- [G1 relay and operation](G1_RELAY.md)
- [Optional RAG](OPTIONAL_RAG.md)
- [Third-party notices](../THIRD_PARTY_LICENSES.md)
