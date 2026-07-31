# Configuration / 配置说明

> 中文摘要：`config/default.env` 只保留公开且与机器无关的默认值；
> `config/local.env` 保存 API key、Python 路径、IP 和网卡，已被 Git 忽略。默认组合是
> `LLM_REPLY_BACKEND=deepseek` + `UNITREE_BACKEND=relay`。

## Precedence and safety

Create the local file from the public template:

```bash
cp config/local.env.example config/local.env
```

Launch and check scripts load `config/default.env` and local overrides before
starting components. Do not put credentials or personal absolute paths into
`config/default.env`, service files, shell history committed to the repository,
or documentation examples.

## Minimum configuration for the recommended robot path

```bash
LLM_PYTHON="${HOME}/miniconda3/envs/llm/bin/python"
VOICE_PYTHON="${HOME}/miniconda3/envs/voice312/bin/python"

LLM_REPLY_BACKEND="deepseek"
OPENAI_BASE_URL="https://api.deepseek.com"
OPENAI_API_KEY="<your-api-key>"
CHAT_MODEL="deepseek-v4-pro"

VOICE_AUDIO_SOURCE="robot"
VOICE_ROBOT_MIC_IF="<this-host-ip-on-the-robot-network>"
VOICE_ROBOT_MIC_PORT="5556"

UNITREE_ENABLE="1"
UNITREE_BACKEND="relay"
ROBOT_RELAY_HOST="<jetson-or-relay-host>"
ROBOT_RELAY_PORT="9999"
```

On the Jetson relay process, also set:

```bash
UNITREE_NETWORK_INTERFACE="<jetson-interface-connected-to-g1>"
UNITREE_VOICE_PEER="<unitree-voice-peer-address>"
```

Machine endpoints intentionally default to empty. Entry points fail with an
actionable message when the active mode requires one. A non-robot audio source
or disabled Unitree output does not require unrelated relay settings.

## Backend selection

| Variable | Value | Meaning |
| --- | --- | --- |
| `LLM_REPLY_BACKEND` | `deepseek` | Default; direct DeepSeek-compatible HTTP API. |
|  | `rag` | Optional XJTLU retrieval service plus Ollama embeddings. |
|  | `local` | Legacy local Qwen-compatible path; local weights required. |
|  | `dashscope` | Optional DashScope-compatible path. |
| `UNITREE_BACKEND` | `relay` | Default; host sends commands to the Jetson relay. |
|  | `direct` | Host initializes Unitree DDS directly; requires `UNITREE_NETWORK_INTERFACE`. |

Convenience commands update the git-ignored local file:

```bash
./scripts/env_set.sh LLM_REPLY_BACKEND deepseek
./scripts/env_set.sh LLM_REPLY_BACKEND rag
```

## Conversation timing

Important public defaults include:

| Variable | Default | Role |
| --- | ---: | --- |
| `VOICE_VAD_SILENCE_FRAMES` | `40` | Base VAD silence count. |
| `VOICE_PAUSE_ENDPOINT_GRACE_SEC` | `0.8` | Extra grace for Monitor **Pause** mode. |
| `VOICE_ASR_MAX_RECORDING_SEC` | `20.0` | Recording safety limit. |
| `LLM_FIRST_TURN_MODE` | `standard` | Initial first-turn policy. |
| `LLM_FIRST_TURN_COMPAT_LISTEN_SEC` | `30` | Compatible first-turn listen limit. |
| `VOICE_FIRST_TURN_COMPAT_SILENCE_SEC` | `2.0` | Compatible first-turn silence confirmation. |
| `LLM_FOLLOWUP_ENABLE` | `1` | Enables continuous follow-up dialogue. |
| `LLM_FOLLOWUP_TIMEOUT_SEC` | `8` | Default follow-up wait. |

The Monitor persists turn and first-turn choices under `runtime/` and allows a
mode change only while the pipeline is stopped.

## Replies, acknowledgements, and actions

- `SURF_LLM_WAKE_ACK_TEXT_ZH` defaults to `我在`.
- `LLM_TERMINATE_ACK_TEXT` defaults to
  `小浦退下了，有问题随时叫小浦。`.
- `LLM_ACTION_ENABLE` and `LLM_ACTION_EXECUTE` control action selection and
  execution separately.
- `UNITREE_ENABLE=0` keeps the non-robot conversation services available while
  disabling G1 output/action execution.

The Monitor's **Silent end** uses the same immediate stop/close control path as
**End**, but requests no termination acknowledgement.

## Optional RAG variables

RAG-specific values (`SOURCE_DB`, `RAG_DB`, `MEMORY_DB`, `OLLAMA_BASE_URL`,
`OLLAMA_BIN`, `EMBED_MODEL`, `TOP_K`, and `SIMILARITY_THRESHOLD`) are ignored by
the default DeepSeek reply path. See [Optional RAG](OPTIONAL_RAG.md).

## Inspect resolved values

```bash
set -a
source config/default.env
source config/local.env
set +a
printf 'reply=%s unitree=%s relay=%s\n' \
  "$LLM_REPLY_BACKEND" "$UNITREE_BACKEND" "$ROBOT_RELAY_HOST"
```

Avoid printing the API key in logs or support requests.
