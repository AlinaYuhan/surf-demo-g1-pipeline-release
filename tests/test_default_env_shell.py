import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DefaultEnvShellTests(unittest.TestCase):
    def test_default_env_can_be_sourced_by_bash(self):
        result = subprocess.run(
            ["bash", "-lc", "set -a; source config/default.env; set +a"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_default_env_has_natural_session_termination_commands(self):
        env = (ROOT / "config" / "default.env").read_text(encoding="utf-8")

        for phrase in ("再见", "拜拜", "我没有问题了", "你退下吧", "bye", "nothing else"):
            self.assertIn(phrase, env)
        self.assertIn("小浦退下了", env)

    def test_first_turn_mode_is_forwarded_to_llm_service_environment(self):
        script = (ROOT / "scripts" / "run_pipeline.sh").read_text(encoding="utf-8")
        match = re.search(r"^SYSTEMD_ENV=\(\n(?P<body>.*?)^\)", script, re.MULTILINE | re.DOTALL)

        self.assertIsNotNone(match)
        systemd_env = match.group("body")
        self.assertIn("--setenv=LLM_FIRST_TURN_MODE=", systemd_env)
        self.assertIn("--setenv=LLM_FIRST_TURN_COMPAT_LISTEN_SEC=", systemd_env)

    def test_compatible_first_turn_window_defaults_to_thirty_seconds(self):
        result = subprocess.run(
            [
                "bash",
                "-lc",
                "source config/default.env; printf '%s' \"$LLM_FIRST_TURN_COMPAT_LISTEN_SEC\"",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "30")

    def test_runtime_defaults_use_deepseek_and_jetson_relay(self):
        default_env = (ROOT / "config" / "default.env").read_text(encoding="utf-8")
        local_example = (ROOT / "config" / "local.env.example").read_text(encoding="utf-8")

        self.assertIn('LLM_REPLY_BACKEND="${LLM_REPLY_BACKEND:-${QWEN_REPLY_BACKEND:-deepseek}}"', default_env)
        self.assertIn('UNITREE_BACKEND="${UNITREE_BACKEND:-relay}"', default_env)
        self.assertIn('LLM_REPLY_BACKEND="deepseek"', local_example)
        self.assertIn('UNITREE_BACKEND="relay"', local_example)

    def test_python_config_fallbacks_match_runtime_defaults(self):
        result = subprocess.run(
            [
                "env",
                "-u",
                "LLM_REPLY_BACKEND",
                "-u",
                "QWEN_REPLY_BACKEND",
                "-u",
                "UNITREE_BACKEND",
                "python3",
                "-c",
                (
                    "from project_config import ProjectConfig; "
                    "config = ProjectConfig(); "
                    "print(config.reply_backend, config.unitree_backend)"
                ),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "deepseek relay")

    def test_monitor_fallback_matches_relay_runtime_default(self):
        from pipeline_monitor.server import PIPELINE_ENV_DEFAULTS

        self.assertEqual(PIPELINE_ENV_DEFAULTS["UNITREE_BACKEND"], "relay")

    def test_setup_creates_voice312_with_python_312(self):
        setup_script = (ROOT / "scripts" / "setup_conda_envs.sh").read_text(encoding="utf-8")
        default_env = (ROOT / "config" / "default.env").read_text(encoding="utf-8")
        local_example = (ROOT / "config" / "local.env.example").read_text(encoding="utf-8")

        self.assertIn('VOICE_ENV="${VOICE_ENV:-voice312}"', setup_script)
        self.assertIn('VOICE_PYTHON_VERSION="${VOICE_PYTHON_VERSION:-3.12}"', setup_script)
        self.assertIn("/envs/voice312/bin/python", default_env)
        self.assertIn("/envs/voice312/bin/python", local_example)
        self.assertIn('VOICE_PYTHON_VERSION="${VOICE_PYTHON_VERSION:-3.12}"', default_env)
        self.assertIn('VOICE_PYTHON_VERSION="3.12"', local_example)

    def test_example_uses_current_thinking_ack_cache_version(self):
        local_example = (ROOT / "config" / "local.env.example").read_text(encoding="utf-8")

        self.assertIn('LLM_THINKING_ACK_CACHE_VERSION="v2"', local_example)

    def test_active_operator_docs_match_runtime_defaults(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        reproducibility = (ROOT / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
        environment = (ROOT / "ENVIRONMENT.md").read_text(encoding="utf-8")
        dependencies = (ROOT / "DEPENDENCIES.md").read_text(encoding="utf-8")

        for guide in (readme, reproducibility):
            self.assertIn("LLM_REPLY_BACKEND=deepseek", guide)
            self.assertIn("UNITREE_BACKEND=relay", guide)
            self.assertRegex(guide, r"(?is)optional.{0,120}(?:RAG|Ollama)")
        self.assertIn("conda create -n voice312 python=3.12 -y", environment)
        self.assertIn("/envs/voice312/bin/python", environment)
        self.assertIn("/envs/voice312/bin/python", dependencies)

    def test_rag_preflight_dependencies_are_guarded_by_backend(self):
        script = (ROOT / "scripts" / "check_pipeline.sh").read_text(encoding="utf-8")
        rag_guard_depth = 0
        guarded_dependencies = []

        for line_number, line in enumerate(script.splitlines(), start=1):
            stripped = line.strip()
            if stripped == 'if [[ "${LLM_REPLY_BACKEND}" == "rag" ]]; then':
                rag_guard_depth += 1
                continue
            if stripped == "fi" and rag_guard_depth:
                rag_guard_depth -= 1
                continue
            if "xjtlu-rag-system/" in stripped or 'test -x "${OLLAMA_BIN}"' in stripped:
                self.assertGreater(
                    rag_guard_depth,
                    0,
                    f"RAG dependency outside backend guard at line {line_number}: {stripped}",
                )
                guarded_dependencies.append(stripped)

        joined_dependencies = "\n".join(guarded_dependencies)
        for dependency in (
            "app.py",
            "chat_engine.py",
            "rag_config.py",
            "ollama_client.py",
            "vector_store.py",
            "memory_store.py",
            "rag_index.db",
            "xjtlu_knowledge.db",
            "OLLAMA_BIN",
        ):
            self.assertIn(dependency, joined_dependencies)


if __name__ == "__main__":
    unittest.main()
