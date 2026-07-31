# Setup / 环境安装

> 中文摘要：本项目当前采用本机/WSL2 安装和 `config/local.env`，不以 Docker
> 作为真机部署入口。默认 DeepSeek 链路不需要 Ollama 或本地 Qwen 权重；唤醒词、
> ASR 和声纹模型需按下文在本机准备。

## 1. Supported deployment

The validated architecture expects:

- Ubuntu or WSL2 with ROS 2 Jazzy at `/opt/ros/jazzy`;
- two Python 3.12 conda environments (`llm` and `voice312`);
- a DeepSeek-compatible API key;
- a Jetson/robot-side relay reachable from the host;
- network access to the G1 and its external microphone path.

Docker is not the primary deployment method. ROS 2 DDS discovery, USB/audio
devices, WSL networking, SSH deployment, and the Jetson's native Unitree
libraries all need host integration. A container would still require privileged
device and network configuration, so the current reproducible path is a local
installation plus a git-ignored `config/local.env`.

## 2. System packages and ROS 2

```bash
sudo apt update
sudo apt install -y \
  build-essential cmake curl ffmpeg git \
  portaudio19-dev python3-dev python3-pip
```

Install ROS 2 Jazzy from the official ROS documentation and verify:

```bash
test -f /opt/ros/jazzy/setup.bash
```

## 3. Python environments

From the repository root:

```bash
./scripts/setup_conda_envs.sh
```

The script creates `llm` and `voice312` with Python 3.12 and installs
`requirements-llm.txt` and `requirements-voice.txt`. If PyTorch needs a
machine-specific CPU/CUDA wheel, install that wheel in the relevant environment
first, then install the remaining requirements.

## 4. External model assets

Downloaded model files and caches are deliberately excluded from Git.

### Wake-word KWS (required for voice wake-up)

The runtime expects these files under
`deps/SURF2026_VoiceModule-main/models/kws/`:

```text
encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx
decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx
joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx
tokens.txt
keywords.txt
```

Obtain the matching `sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01`
assets through the official sherpa-onnx pretrained KWS documentation linked in
[THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md). The repository does not
redistribute the ONNX weights or the model's `tokens.txt`; copy both from the
same official model archive so their vocabularies match. The project-specific
`keywords.txt` remains tracked. Verify the completed model directory with:

```bash
deps/SURF2026_VoiceModule-main/scripts/check_project.sh
```

### ASR (required)

The configured ModelScope model identifier/path is:

```text
iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
${HOME}/.cache/modelscope/hub/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
```

Acquire it using ModelScope/FunASR on the target machine. The official model
page is linked in [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md). Override
the path with `VOICE_ASR_MODEL` if the cache is elsewhere.

### Voiceprint (required when speaker recognition is enabled)

The configured Hugging Face model id is:

```text
pyannote/wespeaker-voxceleb-resnet34-LM
```

Let pyannote/Hugging Face download it into the local cache, or point
`VOICE_VOICEPRINT_MODEL` at an existing local copy. The model terms and official
page are listed in [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).

### Assets not required by the default backend

- Ollama and `nomic-embed-text` are needed only for `LLM_REPLY_BACKEND=rag`.
- `deps/Qwen3.5-0.8B/model/` is used only by the legacy/local backend.
- Neither Ollama nor local Qwen weights are required for direct DeepSeek.

## 5. Local configuration

```bash
cp config/local.env.example config/local.env
```

Fill the API key, Python paths, and machine-specific robot/relay addresses. See
[Configuration](CONFIGURATION.md). Never commit `config/local.env`.

## 6. Build/check native robot dependencies

The C++ action example is a generated local artifact:

```bash
cd deps/unitree_g1_action_classifier_package/unitree_sdk2
mkdir -p build && cd build
cmake ..
make -j
```

The expected binary is
`deps/unitree_g1_action_classifier_package/unitree_sdk2/build/bin/g1_arm_action_example`.
The Jetson relay also needs its machine-local Unitree/CycloneDDS installation;
see [G1 relay and operation](G1_RELAY.md).

## 7. Validate and start

```bash
./scripts/check_pipeline.sh
./scripts/check_robot_relay.sh
./scripts/run_pipeline.sh --mode wake
```

`check_pipeline.sh` validates RAG/Ollama assets only when the reply backend is
actually `rag`. Hardware readiness is still verified on the target machine.
