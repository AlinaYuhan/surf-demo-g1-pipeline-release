# Dependency Manifest

Use [Setup](docs/SETUP.md) for installation and
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for license/status details.

## Repository roles

| Path | Classification | Current role |
| --- | --- | --- |
| `deps/SURF2026_VoiceModule-main/` | Core runtime source | Wake word, VAD, ASR, speaker context, microphone input. |
| `deps/qwen_ros_node_edg_tts/` | Compatibility + vendored third party | Legacy-named package that still supplies the Unitree Python SDK adapter; older Qwen code is not the default reply path. |
| `deps/unitree_g1_action_classifier_package/` | Adapter + vendored third party | G1 action classification/runner and Unitree SDK2 C++ source. |
| `xjtlu-rag-system/` | Optional | XJTLU retrieval service and approved small DBs; disabled by default. |
| `research/` | Research/experimental | Not required by the default conversation path; publication permission varies by asset. |
| `docs/archive/` | Historical | Earlier notes, not current runtime truth. |

## Python environments

- `requirements-llm.txt`: main orchestration, HTTP, TTS, ML/action, and Unitree
  Python adapter dependencies for the `llm` Python 3.12 environment.
- `requirements-voice.txt`: audio, ASR, wake word, VAD, and voiceprint
  dependencies for the `voice312` Python 3.12 environment.

Default external interpreter paths:

```text
${HOME}/miniconda3/envs/llm/bin/python
${HOME}/miniconda3/envs/voice312/bin/python
```

ROS 2 Python packages are provided by ROS 2 Jazzy, not by these pip files.
Install machine-specific PyTorch CPU/CUDA wheels as needed.

## Native DDS/Unitree dependencies

```text
deps/qwen_ros_node_edg_tts/third_party/unitree_sdk2_python/
    Unitree Python adapter; declares cyclonedds==0.10.2

deps/unitree_g1_action_classifier_package/unitree_sdk2/
    Unitree SDK2 C++; bundles its own nested third-party license tree
```

Generated CMake output and Jetson native libraries are not tracked. Build or
install them for the target architecture.

## External/download-on-install assets

| Asset | Required when |
| --- | --- |
| sherpa-onnx KWS ONNX files | Voice wake-up is used. |
| ModelScope Paraformer ASR | Voice ASR is used. |
| Hugging Face WeSpeaker cache | Speaker recognition is enabled. |
| Ollama + `nomic-embed-text` | `LLM_REPLY_BACKEND=rag` only. |
| Local Qwen model | `LLM_REPLY_BACKEND=local` only. |

The default `deepseek` reply backend does not require Ollama or local Qwen.
Downloaded assets, environments, build output, runtime state, and
`config/local.env` are intentionally excluded from Git and public release
bundles.
