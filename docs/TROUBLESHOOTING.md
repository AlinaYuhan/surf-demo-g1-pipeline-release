# Troubleshooting / 故障排查

> 中文摘要：先运行 `./scripts/check_pipeline.sh`，再查看 Monitor 的组件状态和
> `journalctl --user`日志。不要用仓库公开默认值猜 IP，真机网卡和地址必须写入
> `config/local.env`。

## First checks

```bash
./scripts/check_pipeline.sh
./scripts/check_robot_relay.sh
./scripts/tail_pipeline_logs.sh all
```

For service-specific logs:

```bash
journalctl --user -u surf-voice-runtime -f
journalctl --user -u surf-ros-bridge -f
journalctl --user -u surf-llm-server -f
journalctl --user -u surf-llm-node -f
journalctl --user -u surf-llm-audio-player -f
```

## Missing `ROBOT_RELAY_HOST` or `VOICE_ROBOT_MIC_IF`

These values intentionally have no public machine default. Set them in
`config/local.env` when `UNITREE_BACKEND=relay` or
`VOICE_AUDIO_SOURCE=robot`. If testing without robot output, explicitly disable
the irrelevant path instead of supplying a fake address.

## Pipeline starts but a component is `not ready`

- **Voice runtime:** verify the `voice312` Python path, ASR/KWS model assets,
  microphone UDP destination, and ROS 2 environment.
- **LLM node/server:** verify the `llm` Python path, API key, DNS/HTTPS access,
  and `/opt/ros/jazzy/setup.bash`.
- **Audio/action player:** verify relay health and, for direct mode, Unitree DDS
  interface/library setup.
- **Robot microphone streamer:** verify SSH key permissions, remote account,
  USB device visibility, and the destination address.

## DeepSeek request failures

Confirm the active settings without printing the secret:

```bash
source config/default.env
printf '%s\n' "$LLM_REPLY_BACKEND" "$OPENAI_BASE_URL" "$CHAT_MODEL"
test -n "$OPENAI_API_KEY" && echo 'API key is set'
```

The default path should report `deepseek`. Ollama status is irrelevant unless
the backend is `rag`.

## Wake-up says “我在” but speech is not recognized

- Wait for the wake acknowledgement to finish, then speak within the configured
  first-turn window.
- Use Monitor **Compatible** first-turn mode for slower starts (30-second window
  and 2-second silence confirmation by default).
- Check the microphone stream and the ASR log, not only the LLM log.
- **Wake** uses the same first-turn listening flow as voice wake-up; if both
  fail, investigate input/VAD/ASR rather than the button itself.

## Speech is cut off at a pause

Stop Pipeline, switch turn mode from **Fast** to **Pause**, and start again.
Tune `VOICE_PAUSE_ENDPOINT_GRACE_SEC` only in `config/local.env` after observing
real audio; larger values make every turn slower.

## Interrupt or session close is partial

The controls request robot audio stop and arm release before continuing. A
partial result means one of those relay calls failed. Check relay health and the
physical robot state before retrying. **Silent end** suppresses only the spoken
acknowledgement; it is not a weaker stop request.

## DDS or network discovery fails

- Verify the named interface exists: `ip -o link show`.
- Keep the host and Jetson robot-network routes distinct from WSL's virtual
  adapter.
- In direct mode, confirm CycloneDDS and Unitree native libraries resolve.
- Use an explicit `CYCLONEDDS_URI` peer only when multicast discovery is not
  available.
- Prefer the Jetson relay path when WSL cannot reliably initialize Unitree
  audio/DDS.

## RAG checks fail on a DeepSeek setup

Confirm `LLM_REPLY_BACKEND=deepseek` in `config/local.env`. The check script
requires Ollama and RAG databases only when `LLM_REPLY_BACKEND=rag`.

## Monitor cannot open

The default address is `http://127.0.0.1:8765/`. If using the current robot
operator example, start with `--port 8766` and open
`http://127.0.0.1:8766/`. Binding to `127.0.0.1` is local-only; use another bind
address only on a trusted network and with appropriate host firewall controls.
