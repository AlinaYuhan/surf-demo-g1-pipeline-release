# Packaging Notes

## Recommended public artifact

The release builder creates a source-only, auditable snapshot from Git-tracked
files:

```bash
cd <repo-root>
./scripts/build_release_bundle.sh \
  --output ./release-output \
  --name surf_llm_source \
  --tar
```

The resulting directory contains:

- `source/`: the public source snapshot;
- `MANIFEST.sha256`: checksums for every bundled source file;
- `README.md`: verification and installation guidance.

Verify an unpacked artifact before using it:

```bash
cd surf_llm_source
sha256sum --check MANIFEST.sha256
```

The optional `xjtlu-rag-system/` source and the approved
`rag_index.db`/`xjtlu_knowledge.db` knowledge databases are allowed in the
snapshot. Their presence does not enable RAG; the default reply backend remains
DeepSeek.

## Deliberate exclusions

The public artifact does **not** copy local machine state or downloaded assets,
even if one of those files was accidentally added to Git. Exclusions include:

- `config/local.env`, `.env` variants, API-key/credential files and private
  keys (the safe `config/local.env.example` template is retained);
- runtime/session state, logs, caches, chat memory and generated audio;
- downloaded model weights such as ONNX, SafeTensors, GGUF and PyTorch files;
- Git-tracked symbolic links, because they may escape the snapshot and are not
  representable as regular files in the checksum manifest;
- compiled objects and prebuilt native libraries/executables (`.a`, `.so`,
  versioned `.so.*`, `.dll`, `.dylib`, `.exe`, `.lib`, `.o` and `.obj`);
- internal plans, work logs and work reports. Curated historical notes under
  `docs/archive/` remain included because the public README links to them.

Third-party SDKs and native components must therefore be installed or built
locally on the target machine from their documented upstream sources.

### Teacher reference assets

The tracked directory `research/beamforming/teacher_reference_20260630/`
contains teacher-provided MATLAB scripts, filter data, and reference audio.
Permission to publish these assets in the repository was confirmed by their
provider on 2026-08-01. The builder intentionally retains the complete directory
so users can reproduce the current fixed-beamforming path. Other local recordings
and generated audio remain excluded.

## Install on the target machine

This is not an offline or ready-to-run binary bundle. After unpacking, follow
`source/README.md` and the focused setup documentation to create the Python
environments, install ROS 2 and Unitree prerequisites, and download models from
their official sources. Set API keys and machine-specific network values only
in the target machine's local environment.

Model bundling is intentionally unsupported at this stage. This avoids unclear
redistribution rights, oversized releases and stale local caches. Anyone
creating a separate private offline artifact is responsible for the licenses
and redistribution terms of every included model and dataset.

## Safe output behavior

The builder validates the bundle name and refuses to overwrite an existing
directory or tarball. Remove or rename an old artifact explicitly before
building another one; the script never recursively deletes the selected target.
