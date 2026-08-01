# G1 语音交互 Pipeline

[中文](README.zh-CN.md) | [English](README.md)

这是一套面向 Unitree G1 机器人的集成语音交互系统，包含唤醒词、VAD、ASR、
说话人上下文、DeepSeek 对话、TTS、机器人音频、灯光和预设动作。浏览器
Monitor 用于展示实时状态并提供安全的操作控件。

当前推荐部署链路为：

```text
LLM_REPLY_BACKEND=deepseek
UNITREE_BACKEND=relay
```

```text
G1 外置麦克风 -> SURF 语音运行时 -> ROS 2 /audio_msg
-> 上下文节点 -> 本地 LLM HTTP 服务 -> DeepSeek API
-> Edge TTS -> Jetson 中继 -> G1 音频 / 灯光 / 动作
```

XJTLU RAG 源码和已确认可公开的小型数据库仍保留在仓库中，但默认不启用。
原因是它在目标演示中增加了较明显的延迟，且效果收益不足。

## 主要能力

- 中文唤醒词、VAD 端点检测、ASR 和可选的说话人上下文。
- 支持首轮策略和轮次端点模式的连续对话。
- 默认直接调用 DeepSeek-compatible API。
- 通过 Jetson 中继执行 TTS 播放、状态灯和白名单内的 G1 动作。
- Monitor 展示组件就绪度、延迟、事件和会话控件。
- 可选 XJTLU RAG/Ollama 后端，与默认链路隔离。

## 快速开始

完整真机链路面向 Ubuntu 或 WSL2 + ROS 2 Jazzy，需要两个 Python 3.12 环境、
可达的 Jetson 中继服务以及 G1 机器人网络。

```bash
git clone <repository-url>
cd <repository-directory>
./scripts/setup_conda_envs.sh
cp config/local.env.example config/local.env
```

编辑 `config/local.env`，至少填写 DeepSeek API key、Python 路径、本机的机器人麦克风
接收地址和 Jetson 中继地址。公开默认配置不包含任何机器专属 IP。

```bash
./scripts/check_pipeline.sh
./scripts/run_pipeline.sh --mode wake
```

停止 Pipeline：

```bash
./scripts/stop_pipeline.sh
```

唤醒词 ONNX 文件、ASR 和声纹模型缓存不会提交到 Git。新机器需先完成
[环境安装](docs/SETUP.md)，再按[配置说明](docs/CONFIGURATION.md)填写本机参数。

## Pipeline Monitor

服务默认监听 `127.0.0.1:8765`：

```bash
./scripts/run_pipeline_monitor.sh
```

当前真机调试常用 8766 端口：

```bash
./scripts/run_pipeline_monitor.sh --host 127.0.0.1 --port 8766
```

打开 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)，或者对应第二条命令打开
[http://127.0.0.1:8766/](http://127.0.0.1:8766/)。

Monitor 会展示 Pipeline、Session、连接与组件就绪状态，以及最新 ASR、回复、
动作、每轮延迟和实时事件。控件语义如下：

| 分组 | 控件 | 效果 |
| --- | --- | --- |
| Pipeline | **启动 / 停止** | 启动或停止受管理的服务。 |
| 轮次模式 | **快速** | 普通 VAD 静音后尽快结束录音。 |
| 轮次模式 | **停顿** | 在结束轮次前多保留一段可配置的停顿时间。 |
| 首轮模式 | **标准** | 使用常规的首轮等待策略。 |
| 首轮模式 | **兼容** | 默认给首轮最多 30 秒，并以 2 秒连续静音确认输入结束。 |
| 会话 | **唤醒** | 模拟唤醒词，说“我在”后进入与语音唤醒相同的首轮等待。 |
| 会话 | **打断** | 停止当前机器人输出、安全释放动作，并立即开始听取。 |
| 会话 | **结束** | 立即打断输出并关闭会话，然后播放配置的“小浦退下了…”结束语。 |
| 会话 | **静默结束** | 执行相同的立即停止和会话关闭，但不播放结束语。 |

轮次和首轮模式只能在 Pipeline 停止时修改；会话控件只在 Pipeline 运行时启用。
真机链路和安全说明见 [G1 中继与操作](docs/G1_RELAY.md)。

## 仓库结构

```text
config/                         核心：公开默认配置和本地模板
pipeline_control/               核心：会话/打断控制协议
pipeline_log/                   核心：结构化日志和延迟统计
pipeline_monitor/               核心：Monitor HTTP 服务和 API
ui/pipeline_monitor/            核心：浏览器 UI
first_turn/, turn_detection/    核心：对话时序策略
robot_relay/                    核心：Jetson 侧中继服务
scripts/                        核心：安装、启停、检查和部署工具

deps/SURF2026_VoiceModule-main/ 核心：SURF 唤醒/VAD/ASR/说话人运行时
deps/qwen_ros_node_edg_tts/     兼容目录：名称源于历史，现含 Unitree Python
                                适配和旧 LLM 代码
deps/unitree_g1_action_classifier_package/
                                G1 动作适配与 vendored 第三方 SDK
xjtlu-rag-system/               可选：RAG 源码和已批准数据库，默认关闭
research/                       研究/实验：默认对话链路不依赖
docs/                           当前专题文档
docs/archive/                   历史说明，不代表当前运行事实
tests/                          自动化契约和回归测试
```

为了不破坏既有路径和部署假设，运行代码保留在原位置，通过文档分类而不是为了
目录外观做大规模搬移。

## 文档导航

- [环境安装](docs/SETUP.md)：系统、Python、模型和首次验证。
- [配置说明](docs/CONFIGURATION.md)：默认值、密钥和后端模式。
- [G1 中继与操作](docs/G1_RELAY.md)：Jetson/G1 网络和 Monitor 操作。
- [可选 RAG](docs/OPTIONAL_RAG.md)：默认关闭的检索链路。
- [故障排查](docs/TROUBLESHOOTING.md)：常见启动和真机问题。
- [系统架构](docs/project_architecture.md)与[语音到机器人调用链](docs/voice_to_robot_call_chain.md)。
- [依赖](DEPENDENCIES.md)、[可复现性](REPRODUCIBILITY.md)和[打包](PACKAGING.md)。
- [历史文档](docs/archive/README.md)。

无需额外搭建 HTML 文档站：GitHub 可直接渲染这些互相链接的 Markdown，仓库中的 HTML
仅用于运行时 Monitor UI。

## 验证与打包

```bash
pytest -q
./scripts/check_pipeline.sh
./scripts/build_release_bundle.sh --output ./release-output --name surf_g1_source --tar
```

发布构建器只产生源码快照，排除密钥、运行状态、下载模型和编译产物。发布前请阅读
[打包说明](PACKAGING.md)。

## 公开状态与许可

- 项目自有代码采用 [Apache License 2.0](LICENSE)；第三方组件和已获准公开的
  参考资料仍遵循 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) 中的说明。
- `research/beamforming/teacher_reference_20260630/` 中的教师波束形成代码、
  滤波器和参考录音已于 2026-08-01 确认允许在本仓库公开，为保证功能可复现而完整保留。
- 第三方组件、模型和服务说明见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。
- 真机验证与本地网络绑定；本地测试通过不代表 G1 网络、麦克风或中继已就绪。
