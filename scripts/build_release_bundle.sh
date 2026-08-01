#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: build_release_bundle.sh [--output DIR] [--name NAME] [--tar]

Build an auditable source-only release bundle from Git-tracked files.

The default bundle does not include downloaded models, caches, chat memory,
logs, API keys, config/local.env, or internal development archives. Models and
Python environments must be installed on the target machine as documented in
the repository.
EOF
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${WORKSPACE_ROOT}/release-output"
NAME="surf_llm_source"
MAKE_TAR=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || fail "--output requires a directory."
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --output=*)
      OUTPUT_DIR="${1#*=}"
      shift
      ;;
    --name)
      [[ $# -ge 2 ]] || fail "--name requires a value."
      NAME="$2"
      shift 2
      ;;
    --name=*)
      NAME="${1#*=}"
      shift
      ;;
    --tar)
      MAKE_TAR=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

command -v git >/dev/null 2>&1 || fail "git is required to build the bundle."
command -v rsync >/dev/null 2>&1 || fail "rsync is required to build the bundle."
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required to build the manifest."
git -C "${WORKSPACE_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail "the workspace must be a Git worktree."

[[ -n "${OUTPUT_DIR}" ]] || fail "output directory must not be empty."
[[ "${NAME}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
  || fail "bundle name may contain only letters, numbers, dot, underscore, and hyphen."
[[ "${NAME}" != "." && "${NAME}" != ".." ]] || fail "invalid bundle name."

mkdir -p "${OUTPUT_DIR}"
OUTPUT_DIR_REAL="$(cd "${OUTPUT_DIR}" && pwd -P)"
TARGET_ROOT="${OUTPUT_DIR_REAL}/${NAME}"
TARBALL="${TARGET_ROOT}.tar"

# Refuse to overwrite anything. This avoids recursive deletion and makes a
# repeated invocation explicit to the operator.
[[ ! -e "${TARGET_ROOT}" && ! -L "${TARGET_ROOT}" ]] \
  || fail "target already exists: ${TARGET_ROOT}"
if [[ "${MAKE_TAR}" == "1" ]]; then
  [[ ! -e "${TARBALL}" && ! -L "${TARBALL}" ]] \
    || fail "tarball already exists: ${TARBALL}"
fi

is_public_bundle_path() {
  local path="$1"

  case "${path}" in
    config/local.env|*/config/local.env|*.local.env|.env|*/.env|.env.*|*/.env.*)
      return 1
      ;;
    runtime/*|*/runtime/*|logs/*|*/logs/*|cache/*|*/cache/*|.cache/*|*/.cache/*|__pycache__/*|*/__pycache__/*|.pytest_cache/*|*/.pytest_cache/*)
      return 1
      ;;
    docs/plans/*|docs/superpowers/*|docs/work_logs/*|docs/work_reports/*|*/docs/plans/*|*/docs/superpowers/*|*/docs/work_logs/*|*/docs/work_reports/*)
      return 1
      ;;
    xjtlu-rag-system/chat_memory.db|*/chat_memory.db)
      return 1
      ;;
    deps/SURF2026_VoiceModule-main/models/kws/tokens.txt)
      return 1
      ;;
    *.onnx|*.safetensors|*.gguf|*.ckpt|*.pt|*.pth)
      return 1
      ;;
    *.pem|*.key|*.p12|*.pfx|*credentials.json|*credentials.yaml|*credentials.yml|*secrets.json|*secrets.yaml|*secrets.yml)
      return 1
      ;;
    *.a|*.so|*.so.*|*.dll|*.dylib|*.exe|*.lib|*.o|*.obj)
      return 1
      ;;
    *.log|*.wav|*.mp3)
      case "${path}" in
        research/beamforming/teacher_reference_20260630/mixture.wav|research/beamforming/teacher_reference_20260630/out0.wav)
          ;;
        *)
          return 1
          ;;
      esac
      ;;
    *.db|*.sqlite|*.sqlite3)
      case "${path}" in
        xjtlu-rag-system/rag_index.db|xjtlu-rag-system/xjtlu_knowledge.db)
          ;;
        *)
          return 1
          ;;
      esac
      ;;
  esac
  return 0
}

tracked_public_paths() {
  local entry metadata mode path
  while IFS= read -r -d '' entry; do
    metadata="${entry%%$'\t'*}"
    mode="${metadata%% *}"
    path="${entry#*$'\t'}"
    # A tracked symlink can point outside the source snapshot, while rsync's
    # default behavior would copy the link without adding it to the manifest.
    [[ "${mode}" != "120000" ]] || continue
    if is_public_bundle_path "${path}"; then
      printf '%s\0' "${path}"
    fi
  done < <(git -C "${WORKSPACE_ROOT}" ls-files --stage -z)
}

mkdir -p "${TARGET_ROOT}/source"
tracked_public_paths | rsync -a --from0 --files-from=- \
  "${WORKSPACE_ROOT}/" "${TARGET_ROOT}/source/"

(
  cd "${TARGET_ROOT}"
  find source -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
) > "${TARGET_ROOT}/MANIFEST.sha256"

cat > "${TARGET_ROOT}/README.md" <<'EOF'
# Source release bundle

This archive contains an auditable snapshot of the repository's public,
Git-tracked source files. Verify it with:

```bash
sha256sum --check MANIFEST.sha256
```

Downloaded models, Python environments, caches, runtime/session data, local
configuration, API keys, logs, and internal development archives are not
included. Follow `source/README.md` and the focused setup documentation to
install dependencies and models on the target machine.

The optional XJTLU RAG source and its approved knowledge databases may be
present, but RAG is not the default reply backend.

## Teacher reference assets

The provider confirmed permission to publish the MATLAB scripts, filter data,
and reference audio under
`source/research/beamforming/teacher_reference_20260630/` on 2026-08-01. They
are intentionally retained so the fixed-beamforming path remains reproducible.
EOF

if [[ "${MAKE_TAR}" == "1" ]]; then
  tar -cf "${TARBALL}" -C "${OUTPUT_DIR_REAL}" "${NAME}"
  echo "Created source bundle: ${TARGET_ROOT}"
  echo "Created tarball: ${TARBALL}"
else
  echo "Created source bundle: ${TARGET_ROOT}"
fi
