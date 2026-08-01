from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = (
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "ENVIRONMENT.md",
    ROOT / "REPRODUCIBILITY.md",
    ROOT / "DEPENDENCIES.md",
    ROOT / "PACKAGING.md",
    ROOT / "THIRD_PARTY_LICENSES.md",
    ROOT / "docs" / "SETUP.md",
    ROOT / "docs" / "CONFIGURATION.md",
    ROOT / "docs" / "G1_RELAY.md",
    ROOT / "docs" / "OPTIONAL_RAG.md",
    ROOT / "docs" / "TROUBLESHOOTING.md",
    ROOT / "docs" / "project_architecture.md",
    ROOT / "docs" / "voice_to_robot_call_chain.md",
    ROOT / "docs" / "archive" / "README.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_document_internal_links_resolve() -> None:
    link_pattern = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
    missing: list[str] = []
    for document in PUBLIC_DOCS:
        for raw_target in link_pattern.findall(_read(document)):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^(?:https?://|mailto:)", target):
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{document.relative_to(ROOT)} -> {raw_target}")
    assert not missing, "Broken public documentation links:\n" + "\n".join(missing)


def test_bilingual_readmes_share_the_public_entry_points() -> None:
    english = _read(ROOT / "README.md")
    chinese = _read(ROOT / "README.zh-CN.md")
    expected_links = (
        "README.md",
        "README.zh-CN.md",
        "docs/SETUP.md",
        "docs/CONFIGURATION.md",
        "docs/G1_RELAY.md",
        "docs/OPTIONAL_RAG.md",
        "docs/TROUBLESHOOTING.md",
        "docs/project_architecture.md",
        "docs/voice_to_robot_call_chain.md",
        "DEPENDENCIES.md",
        "REPRODUCIBILITY.md",
        "PACKAGING.md",
        "THIRD_PARTY_LICENSES.md",
    )
    for target in expected_links:
        assert target in english
        assert target in chinese


def test_documented_default_backends_match_public_config() -> None:
    defaults = _read(ROOT / "config" / "default.env")
    readmes = _read(ROOT / "README.md") + _read(ROOT / "README.zh-CN.md")
    assert 'LLM_REPLY_BACKEND="${LLM_REPLY_BACKEND:-${QWEN_REPLY_BACKEND:-deepseek}}"' in defaults
    assert 'UNITREE_BACKEND="${UNITREE_BACKEND:-relay}"' in defaults
    assert 'ROBOT_RELAY_HOST="${ROBOT_RELAY_HOST:-}"' in defaults
    assert "LLM_REPLY_BACKEND=deepseek" in readmes
    assert "UNITREE_BACKEND=relay" in readmes


def test_monitor_controls_and_port_are_documented_from_the_ui_contract() -> None:
    html = _read(ROOT / "ui" / "pipeline_monitor" / "index.html")
    server = _read(ROOT / "pipeline_monitor" / "server.py")
    chinese = _read(ROOT / "README.zh-CN.md")
    for label in ("启动", "停止", "快速", "停顿", "标准", "兼容", "唤醒", "打断", "结束", "静默结束"):
        assert re.search(rf">\s*{label}\s*<", html)
        assert f"**{label}**" in chinese or label in ("启动", "停止")
    assert 'parser.add_argument("--port", type=int, default=8765)' in server
    assert "127.0.0.1:8765" in chinese
    assert "--port 8766" in chinese
    assert "我在" in chinese
    assert "小浦退下了" in chinese


def test_public_docs_mark_optional_and_blocked_material() -> None:
    readmes = _read(ROOT / "README.md") + _read(ROOT / "README.zh-CN.md")
    assert "RAG is disabled by default" in readmes
    assert "RAG 是保留的可选实验后端" in _read(
        ROOT / "docs" / "project_architecture.md"
    )
    assert "teacher_reference_20260630" in readmes
    assert "confirmed on" in readmes
    assert "root project `LICENSE` has not yet been selected" in readmes


def test_third_party_notice_matches_safe_bundle_and_ships_unitree_python_license() -> None:
    notice = _read(ROOT / "THIRD_PARTY_LICENSES.md")
    unitree_license = (
        ROOT
        / "deps"
        / "qwen_ros_node_edg_tts"
        / "third_party"
        / "unitree_sdk2_python"
        / "LICENSE"
    )
    assert unitree_license.is_file()
    assert "BSD 3-Clause License" in _read(unitree_license)
    assert "filtered Git-tracked\nsource snapshot" in notice
    assert "currently copies the local Qwen" not in notice


def test_active_first_party_docs_do_not_publish_machine_specific_robot_ips() -> None:
    active_docs = PUBLIC_DOCS + (
        ROOT / "deps" / "SURF2026_VoiceModule-main" / "README.md",
    )
    forbidden = re.compile(r"192\.168\.123\.(?:164|222|225)")
    leaks = [str(path.relative_to(ROOT)) for path in active_docs if forbidden.search(_read(path))]
    assert not leaks, "Machine-specific robot IPs in active docs: " + ", ".join(leaks)
