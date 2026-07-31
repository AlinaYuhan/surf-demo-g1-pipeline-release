# G1 Voice Interaction Pipeline

[English](README.md) | [中文](README.zh-CN.md)

An integrated voice interaction stack for the Unitree G1 robot. It combines
wake-word detection, VAD, ASR, speaker context, direct DeepSeek replies, TTS,
robot audio, lights, and predefined actions. A browser Monitor provides runtime
status and safe operator controls.

The current recommended deployment is:

```text
LLM_REPLY_BACKEND=deepseek
UNITREE_BACKEND=relay
```

```text
G1 external microphone -> SURF voice runtime -> ROS 2 /audio_msg
-> context node -> local LLM HTTP service -> DeepSeek API
-> Edge TTS -> Jetson relay -> G1 audio / lights / actions
```

The XJTLU RAG implementation and its approved small databases remain in the
repository for optional experiments. RAG is disabled by default because it
added latency without improving the target demonstration enough.

## Features

- Chinese wake word, VAD endpointing, ASR, and optional speaker context.
- Multi-turn conversation with first-turn and turn-endpoint modes.
- Direct DeepSeek-compatible API replies by default.
- TTS playback, status lights, and allow-listed G1 actions through a Jetson
  relay.
- Browser Monitor for component readiness, latency, events, and session control.
- Optional XJTLU RAG/Ollama backend, kept separate from the default path.

## Quick start

The full robot path is designed for Ubuntu or WSL2 with ROS 2 Jazzy, two Python
3.12 environments, a reachable Jetson relay, and access to the G1 network.

```bash
git clone <repository-url>
cd <repository-directory>
./scripts/setup_conda_envs.sh
cp config/local.env.example config/local.env
```

Edit `config/local.env`. At minimum, set the DeepSeek API key, Python paths,
local robot-microphone address, and Jetson relay address. Machine-specific
addresses are intentionally not public defaults.

```bash
./scripts/check_pipeline.sh
./scripts/run_pipeline.sh --mode wake
```

Stop the pipeline with:

```bash
./scripts/stop_pipeline.sh
```

Wake-word ONNX files and the ASR/voiceprint model caches are not stored in Git.
Complete [Setup](docs/SETUP.md) before expecting a fresh clone to run on a
robot. See [Configuration](docs/CONFIGURATION.md) for the required values.

## Pipeline Monitor

The server defaults to `127.0.0.1:8765`:

```bash
./scripts/run_pipeline_monitor.sh
```

For the port used by the current robot setup:

```bash
./scripts/run_pipeline_monitor.sh --host 127.0.0.1 --port 8766
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) or, for the second
example, [http://127.0.0.1:8766/](http://127.0.0.1:8766/).

The Monitor shows pipeline, session, connection, and component readiness plus
the latest ASR, reply, action, per-turn latency, and event stream. Its controls
are:

| Group | Control | Behavior |
| --- | --- | --- |
| Pipeline | **Start / Stop** | Starts or stops the managed services. |
| Turn mode | **Fast** | Ends recording promptly after normal VAD silence. |
| Turn mode | **Pause** | Allows an extra configured pause before ending a turn. |
| First turn | **Standard** | Uses the normal first-turn listening policy. |
| First turn | **Compatible** | Allows up to 30 seconds for the first turn and confirms 2 seconds of silence by default. |
| Session | **Wake** | Simulates the wake word, says “我在”, then opens the same first-turn listening flow used by voice wake-up. |
| Session | **Interrupt** | Stops current robot output, safely releases the action, and immediately listens. |
| Session | **End** | Interrupts current output, closes the session, and plays the configured “小浦退下了…” acknowledgement. |
| Session | **Silent end** | Performs the same immediate stop and session close without the spoken acknowledgement. |

Turn and first-turn modes can be changed only while the pipeline is stopped.
Session controls are enabled only while it is running. See
[G1 relay and operation](docs/G1_RELAY.md) for the hardware path and safety
notes.

## Repository map

```text
config/                         Core public defaults and local template
pipeline_control/               Core session/interrupt control protocol
pipeline_log/                   Core structured logging and latency tracking
pipeline_monitor/               Core Monitor HTTP server and API
ui/pipeline_monitor/            Core browser UI
first_turn/, turn_detection/    Core conversation timing policies
robot_relay/                    Core Jetson-side relay service
scripts/                        Core setup, run, stop, check, and deploy tools

deps/SURF2026_VoiceModule-main/ Core SURF wake/VAD/ASR/speaker runtime
deps/qwen_ros_node_edg_tts/     Compatibility package; legacy name, contains
                                current Unitree Python adapter plus older LLM code
deps/unitree_g1_action_classifier_package/
                                G1 action adapter and vendored third-party SDK
xjtlu-rag-system/               Optional RAG source and approved databases;
                                disabled by default
research/                       Research and experimental material; not required
                                by the default conversation path
docs/                           Current focused documentation
docs/archive/                   Historical notes; not runtime truth
tests/                          Automated contracts and regression tests
```

Runtime code remains in its established locations to avoid breaking path and
deployment assumptions. The tree is classified in documentation instead of
being reorganized for appearance.

## Documentation

- [Setup](docs/SETUP.md) — system, Python, models, and first validation.
- [Configuration](docs/CONFIGURATION.md) — defaults, secrets, and backend modes.
- [G1 relay and operation](docs/G1_RELAY.md) — Jetson/G1 network and Monitor use.
- [Optional RAG](docs/OPTIONAL_RAG.md) — disabled-by-default retrieval path.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common startup and hardware issues.
- [Architecture](docs/project_architecture.md) and
  [voice-to-robot call chain](docs/voice_to_robot_call_chain.md).
- [Dependencies](DEPENDENCIES.md), [reproducibility](REPRODUCIBILITY.md), and
  [packaging](PACKAGING.md).
- [Historical archive](docs/archive/README.md).

No additional HTML documentation site is required: GitHub renders these linked
Markdown documents directly, while the existing HTML is the runtime Monitor UI.

## Validation and packaging

```bash
pytest -q
./scripts/check_pipeline.sh
./scripts/build_release_bundle.sh --output ./release-output --name surf_g1_source --tar
```

The release builder creates a source-only snapshot and excludes secrets,
runtime state, downloaded models, and compiled output. Read [Packaging](PACKAGING.md)
before publishing any artifact.

## Publication status and license

- A root project `LICENSE` has not yet been selected. Choose and add one before
  announcing a public release.
- Redistribution permission for
  `research/beamforming/teacher_reference_20260630/` is still unresolved. Do
  not publish those teacher-provided assets without documented permission.
- Third-party components and model/service notes are listed in
  [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
- Hardware validation remains machine-specific; a passing local test suite does
  not prove G1 network, microphone, or relay readiness.
