# Environment Setup

This compatibility entry points to the maintained setup documentation:

- [Setup / 环境安装](docs/SETUP.md)
- [Configuration / 配置说明](docs/CONFIGURATION.md)
- [G1 relay and operation / G1 中继与操作](docs/G1_RELAY.md)
- [Troubleshooting / 故障排查](docs/TROUBLESHOOTING.md)

Current baseline:

```text
Ubuntu or WSL2
ROS 2 Jazzy (/opt/ros/jazzy/setup.bash)
Python 3.12: llm + voice312 conda environments
LLM_REPLY_BACKEND=deepseek
UNITREE_BACKEND=relay
```

Start a fresh installation with:

```bash
# Equivalent manual environment creation:
conda create -n llm python=3.12 -y
conda create -n voice312 python=3.12 -y

./scripts/setup_conda_envs.sh
cp config/local.env.example config/local.env
./scripts/check_pipeline.sh
```

The default interpreter paths are:

```text
${HOME}/miniconda3/envs/llm/bin/python
${HOME}/miniconda3/envs/voice312/bin/python
```

`config/local.env` is git-ignored and must contain the target machine's API key,
Python paths, robot-microphone address, Jetson relay address, and any required
network interfaces. Public defaults intentionally contain no machine-specific
IP or interface.

DeepSeek is the default reply backend and does not require Ollama or local Qwen
weights. Ollama and `nomic-embed-text` are required only for the optional RAG
backend. Wake-word ONNX files, ModelScope ASR, Hugging Face voiceprint caches,
compiled Unitree artifacts, logs, and local environments are not stored in Git.

Docker is not the current recommended robot deployment because ROS 2 DDS, WSL
networking, USB/audio devices, SSH, and Jetson native libraries require
host-specific integration. The supported path is a local installation plus
`config/local.env`.
