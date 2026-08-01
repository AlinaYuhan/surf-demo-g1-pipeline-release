# Third-Party Licenses and Release Notes

This document is an engineering inventory, not legal advice or a guarantee that every use or distribution is permitted. It distinguishes material shipped in this source tree from software, models, and services obtained separately at runtime. First-party project code uses the root Apache-2.0 license; the separate terms and permission notes below are not replaced by that license.

## Bundled vendored material

### Unitree SDK2 (C++)

- **Path:** `deps/unitree_g1_action_classifier_package/unitree_sdk2/`
- **License/status:** BSD-3-Clause. The vendored copy includes `deps/unitree_g1_action_classifier_package/unitree_sdk2/LICENSE`, which must be retained with source distributions and reproduced as required for binary distributions. The vendored revision still needs to be recorded.
- **Official source:** [Unitree SDK2](https://github.com/unitreerobotics/unitree_sdk2)

The SDK also ships its own nested third-party license tree. Keep these files with the corresponding material; they are not replaced by any eventual project license:

| Bundled path | Stated license | Official source |
| --- | --- | --- |
| `deps/unitree_g1_action_classifier_package/unitree_sdk2/licenses/eclipse-cyclonedds/cyclonedds/LICENSE` | EPL-2.0 or EDL-1.0 | [Eclipse Cyclone DDS](https://github.com/eclipse-cyclonedds/cyclonedds) |
| `deps/unitree_g1_action_classifier_package/unitree_sdk2/licenses/eclipse-cyclonedds/cyclonedds-cxx/LICENSE` | EPL-2.0 or EDL-1.0 | [Eclipse Cyclone DDS C++](https://github.com/eclipse-cyclonedds/cyclonedds-cxx) |
| `deps/unitree_g1_action_classifier_package/unitree_sdk2/licenses/eclipse-iceoryx/iceoryx/LICENSE` | Apache-2.0 | [Eclipse iceoryx](https://github.com/eclipse-iceoryx/iceoryx) |
| `deps/unitree_g1_action_classifier_package/unitree_sdk2/licenses/Tencent/rapidjson/LICENSE` | MIT, with the exceptions described in that file | [Tencent RapidJSON](https://github.com/Tencent/rapidjson) |
| `deps/unitree_g1_action_classifier_package/unitree_sdk2/thirdparty/include/ddscxx/dds/LICENSE` | Apache-2.0 | [Eclipse Cyclone DDS C++](https://github.com/eclipse-cyclonedds/cyclonedds-cxx) |

### Unitree SDK2 Python

- **Path:** `deps/qwen_ros_node_edg_tts/third_party/unitree_sdk2_python/`
- **License/status:** BSD-3-Clause. The vendored `setup.py` declares version
  `1.0.1`, and the matching official license text is retained as
  `deps/qwen_ros_node_edg_tts/third_party/unitree_sdk2_python/LICENSE`.
- **Revision status:** the copy contains local integration changes and does not
  preserve an exact upstream commit identifier. Record the upstream base if it
  can be recovered; until then, treat this directory as a modified vendored
  copy rather than claiming it matches a specific upstream revision.
- **Official source:** [Unitree SDK2 Python](https://github.com/unitreerobotics/unitree_sdk2_python)

## Runtime software, models, and services

These items should be obtained from official, pinned sources during installation rather than bundled in a public source or release archive. Record the downloaded revision or digest and checksum. If any model is later redistributed, review and satisfy the terms for the exact bytes being shipped.

The current `scripts/build_release_bundle.sh` creates a filtered Git-tracked
source snapshot. It excludes downloaded model weights, caches, generated audio,
runtime data, secrets, symbolic links, and prebuilt libraries. Models remain
download-on-install items. If a separate offline artifact is ever created, each
exact model or binary must be cleared and packaged with its required license,
notice, attribution, revision, and checksum.

| Component and repository location/reference | Published terms and official source | Current release treatment |
| --- | --- | --- |
| Edge TTS, installed from `requirements-llm.txt` and used by `llm_server.py` and `deps/qwen_ros_node_edg_tts/qwen_server.py` | The client is LGPLv3, except `src/edge_tts/srt_composer.py`, which its [official license](https://github.com/rany2/edge-tts/blob/master/LICENSE) identifies as MIT. [Official repository](https://github.com/rany2/edge-tts). | **Install-only; do not vendor.** Microsoft-hosted TTS service and voice terms are separate from the client license. |
| Paraformer, normally cached at `${HOME}/.cache/modelscope/hub/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | Apache-2.0 as stated by the [official ModelScope model page](https://modelscope.cn/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch). | **Download-on-install preferred.** Bundling would require an exact revision, license/notice, provenance, and checksum. |
| WeSpeaker `pyannote/wespeaker-voxceleb-resnet34-LM`, normally cached under `${HOME}/.cache/huggingface/hub/models--pyannote--wespeaker-voxceleb-resnet34-LM` | CC-BY-4.0 on the [official model page](https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM). | **Download-on-install preferred.** Bundling would require exact revision, attribution, license link/text, and a change indication. |
| Ollama `nomic-embed-text`, referenced by `EMBED_MODEL` | The [official Ollama entry](https://ollama.com/library/nomic-embed-text) links the source model; [Nomic's official model page](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) states Apache-2.0. | **Optional, download-only** via `ollama pull nomic-embed-text`. Do not redistribute a blob without pinning its digest and matching it to the licensed source artifact. |
| Qwen model expected at `deps/Qwen3.5-0.8B/model/` | The [official `Qwen/Qwen3.5-0.8B` model page](https://huggingface.co/Qwen/Qwen3.5-0.8B) states Apache-2.0, but the local path does not establish that its bytes came from that model or identify a revision. | **Do not bundle the local directory.** Prefer a pinned official download; origin and hash are unresolved for any existing local copy. |
| sherpa-onnx KWS files expected under `deps/SURF2026_VoiceModule-main/models/kws/` | [Official pretrained KWS documentation](https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html) identifies the expected `sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01` archive. [sherpa-onnx software](https://github.com/k2-fsa/sherpa-onnx) is Apache-2.0, but that does not establish a license for separately trained weights or the token table. | **License unresolved; no bundling.** The ONNX weights and `tokens.txt` are excluded from the public tree/bundle; users must obtain the matching files from the official model archive. |

## Permission-confirmed material and project licensing boundaries

The provider confirmed permission on 2026-08-01 to publish the following
fixed-beamforming reference assets in this repository. They remain together so
the current beamforming implementation and reference verification are usable:

- `research/beamforming/teacher_reference_20260630/Fixed_Mini_Beamformer.m`
- `research/beamforming/teacher_reference_20260630/test.m`
- `research/beamforming/teacher_reference_20260630/DCF_Targ7.mat`
- `research/beamforming/teacher_reference_20260630/DCF_Targ7_runtime.npz`
- `research/beamforming/teacher_reference_20260630/mixture.wav`
- `research/beamforming/teacher_reference_20260630/out0.wav`

The following project-associated wrapper directories have no separate local license. Their surrounding code requires confirmed contributor/owner authority and coverage by the eventual root project license; a nested third-party license does not license the wrapper:

- `deps/SURF2026_VoiceModule-main/`
- `deps/qwen_ros_node_edg_tts/` (excluding its separately listed vendored Unitree SDK2 Python copy)
- `deps/unitree_g1_action_classifier_package/` (excluding its separately listed vendored Unitree SDK2 C++ copy)
