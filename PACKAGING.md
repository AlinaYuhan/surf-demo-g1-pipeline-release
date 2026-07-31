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

- `config/local.env`, `.env`, API-key/credential files and private keys;
- runtime/session state, logs, caches, chat memory and generated audio;
- downloaded model weights such as ONNX, SafeTensors, GGUF and PyTorch files;
- internal plans, work logs/reports and archived development notes.

`config/local.env.example` remains in the source snapshot as the safe
configuration template.

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
