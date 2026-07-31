# Reproducibility Guide

The repository is intended to be a public, source-reproducible project, not a
clone-and-run robot image. Start with [README.md](README.md), then follow
[Setup](docs/SETUP.md) and [Configuration](docs/CONFIGURATION.md).

## Included in Git

- Core orchestration, session control, Monitor server/UI, and tests.
- SURF voice runtime source under `deps/SURF2026_VoiceModule-main/`.
- Unitree adapter/vendored SDK source currently required by established paths.
- Optional XJTLU RAG source plus the approved `xjtlu_knowledge.db` and
  `rag_index.db` databases.
- Safe defaults and a local configuration template.
- Research/experimental source, subject to the publication blockers below.

## Recreated on each machine

- `config/local.env`, API keys, IP addresses, interfaces, and Python paths.
- Python/conda environments and ROS 2 Jazzy installation.
- Wake-word ONNX assets, ModelScope ASR, and Hugging Face voiceprint caches.
- Optional Ollama and `nomic-embed-text` for RAG only.
- Optional local Qwen weights for the legacy/local backend only.
- Unitree C++ build output and Jetson-native libraries.
- Logs, runtime state, chat memory, generated TTS, and caches.

The default DeepSeek + Jetson relay path is:

```text
LLM_REPLY_BACKEND=deepseek
UNITREE_BACKEND=relay
```

Optional RAG/Ollama services and local Qwen weights are not required by this
path.

## Reproduction sequence

```bash
./scripts/setup_conda_envs.sh
cp config/local.env.example config/local.env
# edit config/local.env and install/download the documented external assets
./scripts/check_pipeline.sh
./scripts/check_robot_relay.sh
./scripts/run_pipeline.sh --mode wake
```

Start the operator UI separately:

```bash
./scripts/run_pipeline_monitor.sh              # http://127.0.0.1:8765/
./scripts/run_pipeline_monitor.sh --port 8766  # common robot-test port
```

## Evidence and limits

Automated tests and `check_pipeline.sh` verify source/configuration contracts.
They do not validate the target robot's USB microphone, physical network,
Jetson libraries, relay reachability, speaker, lights, or action safety. Record
the local environment, model revisions/checksums, and hardware test result for
each reproducibility claim.

## Publication blockers

- The project still needs a selected root `LICENSE`.
- Redistribution permission for
  `research/beamforming/teacher_reference_20260630/` is unresolved.
- The vendored Unitree Python SDK now includes its matching BSD-3-Clause notice,
  but its exact upstream base revision has not been recovered; treat it as a
  modified vendored copy as described in
  [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

Do not publish an artifact until these release checks are resolved or the
affected files are excluded. Use the source-only builder described in
[PACKAGING.md](PACKAGING.md); it deliberately excludes local models, secrets,
runtime state, and compiled output.
