# Voice-to-Robot Call Chain / 语音到机器人调用链

> **Current source of truth (2026-07-31).** The sequence below reflects the
> default `deepseek` reply backend and `relay` Unitree backend.
>
> **中文摘要：** 音频从 G1 外置麦克风进入 SURF，经唤醒/VAD/ASR 后发布到
> ROS 2；上下文节点调用本地 `llm_server.py`，默认直接请求 DeepSeek，再由
> Edge TTS 生成音频，通过 Jetson relay 交给 G1 播放并执行允许的灯光/动作。

## 1. Start and readiness

`scripts/run_pipeline.sh --mode wake`:

1. Loads `config/default.env` and the ignored `config/local.env`.
2. Validates endpoints required by the selected audio and Unitree modes.
3. Sources ROS 2 Jazzy.
4. Starts bridge, voice, LLM server, context node, and audio player services.
5. Starts Ollama/RAG services only if `LLM_REPLY_BACKEND=rag`.
6. Waits for the LLM health endpoint and audio-player service readiness.

The Monitor uses the same configuration and exposes service, relay, and robot
microphone readiness separately.

## 2. Audio and wake-up

With `VOICE_AUDIO_SOURCE=robot`, the robot-side microphone streamer sends audio
to `VOICE_ROBOT_MIC_IF:VOICE_ROBOT_MIC_PORT`. The SURF runtime performs:

```text
audio frames -> wake word -> VAD -> ASR -> optional speaker recognition
```

Wake-up may come from the spoken wake word or the Monitor's **Wake** command.
Both enter the same first-turn state. The configured acknowledgement is played
(`我在` by default), then the runtime listens for the first user utterance.

The independent timing controls are:

- **Fast / Pause:** how much silence ends a recorded turn;
- **Standard / Compatible:** first-turn listening policy. Compatible defaults to
  a 30-second listen limit and 2-second silence confirmation.

## 3. ROS 2 context

`surf_ros_bridge.py` publishes recognized input and context topics, including:

```text
/audio_msg
/wake_word_event
/vad_state
/speaker_id
```

`llm_surf_context_node.py` consumes `/audio_msg`, applies wake/session and
self-speech guards, adds speaker/session context when enabled, and calls the
local inference endpoint (default `http://127.0.0.1:8000/infer`).

The integrated workspace keeps `LLM_AUTOSTART_ASR_BRIDGE=0` because SURF is the
single ASR publisher.

## 4. Reply selection

`llm_server.py` selects the backend from `LLM_REPLY_BACKEND`:

```text
deepseek  -> direct DeepSeek-compatible HTTP API (default)
rag       -> local xjtlu-rag-system /chat, with Ollama embeddings
local     -> legacy local Qwen-compatible model path
dashscope -> optional DashScope-compatible API
```

For the default path, the service uses `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and
the configured DeepSeek model. No RAG database, Ollama process, embedding model,
or local Qwen weight is involved.

The reply contract carries the spoken reply plus optional action information.
Action execution remains bounded by project allow-lists and execution toggles.

## 5. TTS and robot output

The context node requests TTS from the local LLM service. Edge TTS produces a
runtime audio file, and `unitree_audio_player.py` coordinates:

1. playback status and self-speech guard;
2. G1 light state;
3. TTS audio delivery;
4. optional allow-listed action execution;
5. transition back to follow-up listening or standby.

With `UNITREE_BACKEND=relay`, commands go to `RobotRelayClient`, then across TCP
to `robot_relay/jetson_robot_relay.py`. The Jetson uses its Unitree-native
libraries and robot-network interface to perform the physical operation.

## 6. Multi-turn and manual controls

After a reply finishes, follow-up listening remains open for the configured
timeout. Termination phrases or Monitor controls close the conversation.

- **Interrupt:** invalidates in-flight generation, requests robot audio stop and
  arm release, then opens listening.
- **End:** performs the same immediate output stop/release, closes the session,
  and plays the configured termination acknowledgement.
- **Silent end:** performs the same output stop/release and close, with no
  termination acknowledgement.

The generation/request protocol prevents stale LLM, TTS, or action work from
being accepted after an interrupt. A partial Monitor result means a robot relay
operation failed and requires physical/operator verification.

## 7. Logs and observation

`pipeline_log/` writes structured events beneath `logs/<session>/pipeline.log`.
The Monitor reads this data for:

- latest ASR, reply, and action;
- completed-turn latency;
- live event timeline;
- session state and component readiness.

`runtime/` contains ephemeral control/status files and generated TTS. Neither
directory belongs in a public source bundle.

## 8. Optional RAG branch

When explicitly set to `LLM_REPLY_BACKEND=rag`, orchestration inserts:

```text
llm_server.py -> xjtlu-rag-system /chat
              -> SQLite vector/knowledge DB
              -> Ollama nomic-embed-text
              -> DeepSeek-compatible generation
```

This branch is retained for experimentation and is disabled by default due to
latency and limited observed benefit. See [Optional RAG](OPTIONAL_RAG.md).

## Related documentation

- [Current architecture](project_architecture.md)
- [Configuration](CONFIGURATION.md)
- [G1 relay and operation](G1_RELAY.md)
- [Troubleshooting](TROUBLESHOOTING.md)
