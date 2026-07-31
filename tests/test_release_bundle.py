import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _tracked_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "repository"
    (fixture / "scripts").mkdir(parents=True)
    shutil.copy2(
        ROOT / "scripts/build_release_bundle.sh",
        fixture / "scripts/build_release_bundle.sh",
    )

    files = {
        "README.md": "public source\n",
        "src/main.py": "print('hello')\n",
        "xjtlu-rag-system/rag_index.db": "approved database\n",
        "xjtlu-rag-system/xjtlu_knowledge.db": "approved database\n",
        "config/local.env": "OPENAI_API_KEY=secret\n",
        "runtime/session.json": "runtime state\n",
        "logs/pipeline.log": "local log\n",
        ".cache/huggingface/model.bin": "download cache\n",
        "xjtlu-rag-system/chat_memory.db": "conversation memory\n",
        "models/local-model.onnx": "downloaded model\n",
        "docs/archive/internal-plan.md": "historical development note\n",
    }
    for relative_path, content in files.items():
        path = fixture / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=fixture, check=True)
    subprocess.run(["git", "add", "-f", "."], cwd=fixture, check=True)
    return fixture


def test_default_bundle_contains_only_auditable_public_source(tmp_path):
    fixture = _tracked_fixture(tmp_path)
    output = tmp_path / "output"

    result = subprocess.run(
        [
            "bash",
            str(fixture / "scripts/build_release_bundle.sh"),
            "--output",
            str(output),
            "--name",
            "release",
        ],
        cwd=fixture,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    bundle = output / "release"
    assert (bundle / "source/README.md").is_file()
    assert (bundle / "source/src/main.py").is_file()
    assert (bundle / "source/xjtlu-rag-system/rag_index.db").is_file()
    assert (bundle / "source/xjtlu-rag-system/xjtlu_knowledge.db").is_file()

    forbidden = (
        "source/config/local.env",
        "source/runtime/session.json",
        "source/logs/pipeline.log",
        "source/.cache/huggingface/model.bin",
        "source/xjtlu-rag-system/chat_memory.db",
        "source/models/local-model.onnx",
        "source/docs/archive/internal-plan.md",
    )
    for relative_path in forbidden:
        assert not (bundle / relative_path).exists(), relative_path

    manifest = (bundle / "MANIFEST.sha256").read_text(encoding="utf-8")
    assert "source/README.md" in manifest
    assert "source/xjtlu-rag-system/rag_index.db" in manifest
    for relative_path in forbidden:
        assert relative_path not in manifest

    bundle_readme = (bundle / "README.md").read_text(encoding="utf-8")
    assert "research/beamforming/teacher_reference_20260630/" in bundle_readme
    assert "redistribution permission" in bundle_readme.lower()


def test_packaging_notes_flag_teacher_reference_redistribution_decision():
    packaging = (ROOT / "PACKAGING.md").read_text(encoding="utf-8")

    assert "research/beamforming/teacher_reference_20260630/" in packaging
    assert "redistribution permission" in packaging.lower()
    assert "exclude" in packaging


def test_builder_refuses_to_replace_an_existing_target(tmp_path):
    fixture = _tracked_fixture(tmp_path)
    target = tmp_path / "output/release"
    target.mkdir(parents=True)
    sentinel = target / "keep.txt"
    sentinel.write_text("do not delete\n", encoding="utf-8")

    result = subprocess.run(
        [
            "bash",
            str(fixture / "scripts/build_release_bundle.sh"),
            "--output",
            str(target.parent),
            "--name",
            target.name,
        ],
        cwd=fixture,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "target already exists" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "do not delete\n"


def test_builder_rejects_a_traversal_bundle_name(tmp_path):
    fixture = _tracked_fixture(tmp_path)

    result = subprocess.run(
        [
            "bash",
            str(fixture / "scripts/build_release_bundle.sh"),
            "--output",
            str(tmp_path / "output"),
            "--name",
            "../escape",
        ],
        cwd=fixture,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "bundle name" in result.stderr
    assert not (tmp_path / "escape").exists()
