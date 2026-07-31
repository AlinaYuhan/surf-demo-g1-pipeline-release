import os
import subprocess
import sys
from pathlib import Path

import pytest

import project_config
from pipeline_monitor import server


ROOT = Path(__file__).resolve().parents[1]


def test_first_party_defaults_leave_machine_endpoints_empty(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.env").write_text(
        (ROOT / "config/default.env").read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = subprocess.run(
        [
            "bash",
            "-lc",
            "unset ROBOT_RELAY_HOST UNITREE_NETWORK_INTERFACE; "
            f"source {config_dir / 'default.env'}; "
            "printf '%s|%s' \"$ROBOT_RELAY_HOST\" \"$UNITREE_NETWORK_INTERFACE\"",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout == "|"


def test_python_config_preserves_explicit_endpoints_and_has_portable_empty_defaults(monkeypatch):
    monkeypatch.delenv("ROBOT_RELAY_HOST", raising=False)
    monkeypatch.delenv("UNITREE_NETWORK_INTERFACE", raising=False)
    config = project_config.ProjectConfig()
    assert config.robot_relay_host == ""
    assert config.unitree_network_interface == ""

    env = os.environ.copy()
    env.update(ROBOT_RELAY_HOST="relay.example", UNITREE_NETWORK_INTERFACE="robot0")
    result = subprocess.run(
        [sys.executable, "-c", "from project_config import CONFIG; print(CONFIG.robot_relay_host, CONFIG.unitree_network_interface)"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "relay.example robot0"


def test_monitor_reports_missing_relay_host_without_connecting(monkeypatch):
    monkeypatch.delenv("ROBOT_RELAY_HOST", raising=False)
    monkeypatch.setitem(server.PIPELINE_ENV_DEFAULTS, "ROBOT_RELAY_HOST", "")
    monkeypatch.setattr(
        "socket.create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network attempted")),
    )
    status = server.robot_relay_status()
    assert status["state"] == "configuration_not_ready"
    assert "ROBOT_RELAY_HOST" in status["error"]
    assert status["endpoint"] == ""


def test_monitor_reports_missing_robot_mic_config_without_ssh(monkeypatch):
    monkeypatch.delenv("ROBOT_RELAY_HOST", raising=False)
    monkeypatch.delenv("VOICE_ROBOT_MIC_IF", raising=False)
    monkeypatch.setitem(server.PIPELINE_ENV_DEFAULTS, "ROBOT_RELAY_HOST", "")
    monkeypatch.setitem(server.PIPELINE_ENV_DEFAULTS, "VOICE_ROBOT_MIC_IF", "")
    status = server.robot_mic_status(
        command_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("SSH attempted"))
    )
    assert status["state"] == "configuration_not_ready"
    assert "ROBOT_RELAY_HOST" in status["error"]
    assert "VOICE_ROBOT_MIC_IF" in status["error"]
    assert status["endpoint"] == ""


def test_monitor_start_fails_before_runtime_or_shell_when_required_config_missing(monkeypatch):
    for name in ("ROBOT_RELAY_HOST", "VOICE_ROBOT_MIC_IF"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setitem(server.PIPELINE_ENV_DEFAULTS, name, "")
    result = server.run_pipeline_command(
        "start",
        command_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("shell attempted")),
        robot_runtime_starter=lambda: (_ for _ in ()).throw(AssertionError("runtime attempted")),
    )
    assert not result["ok"]
    assert "ROBOT_RELAY_HOST" in result["error"]
    assert "VOICE_ROBOT_MIC_IF" in result["error"]


def test_monitor_local_non_unitree_start_skips_robot_runtime(monkeypatch):
    monkeypatch.setenv("VOICE_AUDIO_SOURCE", "local")
    monkeypatch.setenv("UNITREE_ENABLE", "0")
    monkeypatch.delenv("ROBOT_RELAY_HOST", raising=False)
    monkeypatch.delenv("VOICE_ROBOT_MIC_IF", raising=False)
    result = server.run_pipeline_command(
        "start",
        command_runner=lambda *_args, **_kwargs: type(
            "Result", (), {"returncode": 0, "stdout": "started", "stderr": ""}
        )(),
        robot_runtime_starter=lambda: (_ for _ in ()).throw(AssertionError("runtime attempted")),
        services_ready_checker=lambda: True,
    )
    assert result["ok"]


def test_launchers_source_local_config_and_validate_jetson_network_values():
    monitor = (ROOT / "scripts/run_pipeline_monitor.sh").read_text(encoding="utf-8")
    assert 'source "${PROJECT_ROOT}/config/default.env"' in monitor
    assert 'source "${PROJECT_ROOT}/config/local.env"' in monitor

    env = {"PATH": os.environ["PATH"]}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/run_jetson_robot_relay.sh")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "UNITREE_NETWORK_INTERFACE" in result.stderr


def test_direct_relay_python_and_action_cli_fail_before_sdk_or_network_when_config_missing():
    env = {"PATH": os.environ["PATH"]}
    relay = subprocess.run(
        [sys.executable, str(ROOT / "robot_relay/jetson_robot_relay.py")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert relay.returncode != 0
    assert "UNITREE_NETWORK_INTERFACE" in relay.stderr
    assert "unitree_sdk2py" not in relay.stderr

    action_env = {**env, "UNITREE_BACKEND": "relay"}
    action = subprocess.run(
        [sys.executable, str(ROOT / "scripts/g1_arm_action_runner.py"), "--id", "25"],
        cwd=ROOT,
        env=action_env,
        text=True,
        capture_output=True,
    )
    assert action.returncode == 2
    assert "ROBOT_RELAY_HOST" in action.stderr


@pytest.mark.parametrize(
    ("audio_source", "unitree_enable", "unitree_backend", "expected_checks"),
    [
        ("local", "0", "relay", []),
        ("local", "1", "relay", ["relay"]),
        ("robot", "0", "relay", ["mic"]),
        ("robot", "1", "direct", ["mic"]),
    ],
)
def test_pipeline_status_checks_only_components_required_by_runtime_mode(
    monkeypatch, audio_source, unitree_enable, unitree_backend, expected_checks
):
    monkeypatch.setenv("VOICE_AUDIO_SOURCE", audio_source)
    monkeypatch.setenv("UNITREE_ENABLE", unitree_enable)
    monkeypatch.setenv("UNITREE_BACKEND", unitree_backend)
    checks = []

    def active_service(_command, **_kwargs):
        return type("Result", (), {"returncode": 0, "stdout": "active\n", "stderr": ""})()

    def relay_checker():
        checks.append("relay")
        return {"ready": True, "state": "ready"}

    def mic_checker():
        checks.append("mic")
        return {"ready": True, "state": "ready"}

    status = server.pipeline_status(
        command_runner=active_service,
        relay_checker=relay_checker,
        mic_checker=mic_checker,
    )

    assert checks == expected_checks
    assert status["state"] == "running"


@pytest.mark.parametrize(
    ("script", "extra_args"),
    [
        ("g1_robot_skill_command.py", ["--command", "forward_step", "--loco_client", "/bin/true"]),
        ("restore_ai_sport_mode.py", []),
    ],
)
def test_direct_robot_clis_require_explicit_network_interface_before_client_setup(script, extra_args):
    env = os.environ.copy()
    env.pop("UNITREE_NETWORK_INTERFACE", None)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *extra_args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "UNITREE_NETWORK_INTERFACE" in result.stderr


@pytest.mark.parametrize(
    "source_name",
    ["g1_agv_command.cpp", "g1_loco_walkrun_command.cpp", "g1_wireless_teleop_command.cpp"],
)
def test_first_party_cpp_robot_tools_have_no_machine_interface_default(source_name):
    source = (ROOT / "scripts" / source_name).read_text(encoding="utf-8")
    assert '"enp8s0"' not in source
    assert "UNITREE_NETWORK_INTERFACE" in source
    assert source.index("if (iface.empty())") < source.index("ChannelFactory::Instance()->Init")


def test_local_voice_mode_does_not_require_robot_destination(monkeypatch):
    voice_root = ROOT / "deps/SURF2026_VoiceModule-main"
    sys.path.insert(0, str(voice_root))
    try:
        from config.voice_config import VoiceConfig

        monkeypatch.setenv("VOICE_AUDIO_SOURCE", "local")
        monkeypatch.delenv("VOICE_ROBOT_MIC_IF", raising=False)
        config = VoiceConfig()
        assert config.audio_source == "local"
        assert config.robot_mic_interface == ""
    finally:
        sys.path.remove(str(voice_root))


def test_robot_audio_tools_require_explicit_interface_or_destination():
    voice_root = ROOT / "deps/SURF2026_VoiceModule-main"
    env = os.environ.copy()
    env.pop("VOICE_ROBOT_MIC_IF", None)
    stream = subprocess.run(
        [sys.executable, str(voice_root / "tools/stream_usb_mic.py")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert stream.returncode != 0
    assert "--dest" in stream.stderr

    record_code = (
        "import importlib.util; "
        f"s=importlib.util.spec_from_file_location('record_robot_mic', {str(voice_root / 'tools/record_robot_mic.py')!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.open_socket()"
    )
    record = subprocess.run(
        [sys.executable, "-c", record_code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert record.returncode != 0
    assert "VOICE_ROBOT_MIC_IF" in record.stderr
