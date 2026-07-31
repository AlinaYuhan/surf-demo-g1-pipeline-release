from __future__ import annotations

import json
import importlib
import threading
import sys
from types import ModuleType, SimpleNamespace

from pipeline_log.pipeline_logger import SessionLog
from turn_detection.runtime_shadow import TurnShadowRuntime


def _stub_module(monkeypatch, name: str, symbol: str) -> None:
    package_name = name.split(".", 1)[0]
    monkeypatch.setitem(sys.modules, package_name, ModuleType(package_name))
    module = ModuleType(name)
    setattr(module, symbol, type(symbol, (), {}))
    monkeypatch.setitem(sys.modules, name, module)


def _load_voice_runtime(monkeypatch):
    dependencies = {
        "asr.asr_engine": "ASREngine",
        "audio.audio_bus": "AudioBus",
        "audio.mic_capture": "MicCapture",
        "vad.vad_engine": "VADEngine",
        "voice_id.speaker_database": "SpeakerDatabase",
        "voice_id.voiceprint_recognizer": "VoiceprintRecognizer",
        "wake_word.chinese_wake_word_detector": "ChineseWakeWordDetector",
        "wake_word.wake_word_detector": "WakeWordDetector",
        "wake_word.wakeup_dispatcher": "WakeupDispatcher",
    }
    for module_name, symbol in dependencies.items():
        _stub_module(monkeypatch, module_name, symbol)
    config_module = ModuleType("config.voice_config")
    config_module.CONFIG = SimpleNamespace(
        asr_max_recording_sec=10.0,
        vad_holdoff_sec=0.0,
    )
    monkeypatch.setitem(sys.modules, "config.voice_config", config_module)
    monkeypatch.delitem(sys.modules, "surf_voice_runtime", raising=False)
    return importlib.import_module("surf_voice_runtime").SurfVoiceRuntime


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def publish(self, topic, msg_type, data) -> None:
        self.events.append((topic, msg_type, data))


class RecordingShadow:
    def __init__(self) -> None:
        self.events = []

    def submit_vad(self, is_speech: bool, *, agent_playing: bool) -> None:
        self.events.append(("vad", is_speech, agent_playing))

    def submit_wake(self, word: str, *, agent_playing: bool) -> None:
        self.events.append(("wake", word, agent_playing))

    def submit_asr_final(self, text: str, *, agent_playing: bool) -> None:
        self.events.append(("asr_final", text, agent_playing))


class FakeASR:
    def start_recording(self, *, initial_audio: bytes) -> int:
        self.initial_audio = initial_audio
        return 1


class FakeVoiceprint:
    def start_capture(self, *, initial_audio: bytes) -> None:
        self.initial_audio = initial_audio


class ClosingShadow:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class SessionCommandControl:
    def __init__(self, command):
        self.command = command

    def read_session_command(self):
        return self.command


class RecordingWakeDispatcher:
    def __init__(self) -> None:
        self.words = []

    def on_detection(self, word: str) -> None:
        self.words.append(word)


class AttemptTrackingLock:
    def __init__(self, lock, watched_thread_name: str) -> None:
        self._lock = lock
        self._watched_thread_name = watched_thread_name
        self.acquire_attempted = threading.Event()

    def acquire(self, *args, **kwargs):
        if threading.current_thread().name == self._watched_thread_name:
            self.acquire_attempted.set()
        return self._lock.acquire(*args, **kwargs)

    def release(self) -> None:
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_args) -> None:
        self.release()


class FollowupControlASR:
    def __init__(self) -> None:
        self.cancel_count = 0
        self.start_count = 0

    def cancel_recording(self) -> None:
        self.cancel_count += 1

    def start_recording(self, *, initial_audio: bytes) -> int:
        self.start_count += 1
        return self.start_count


def _make_followup_control_runtime(SurfVoiceRuntime, control_path, command, *, lifecycle_lock=None):
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._session_lifecycle_lock = lifecycle_lock or threading.Lock()
    runtime._recording_lock = threading.Lock()
    runtime._recording = False
    runtime._asr_recording_epoch = None
    runtime._asr_deadline = 0.0
    runtime._asr_audio_frames = []
    runtime._asr = FollowupControlASR()
    runtime._followup_enable = True
    runtime._followup_session_id = ""
    runtime._followup_until = 0.0
    runtime._followup_guard_until = 0.0
    runtime._followup_control_path = control_path
    runtime._followup_control_mtime = 0.0
    runtime._followup_close_watermark = 100.0
    runtime._started_at = 100.0
    runtime._session_id = ""
    runtime._session_log = None
    runtime._turn_shadow = None
    runtime._last_session_command_request_id = ""
    runtime._interrupt_control = SessionCommandControl(command)
    runtime._vad = SimpleNamespace(reset=lambda: None)
    runtime._set_wake_light_red = lambda _reason: None
    runtime._set_wake_light_blue = lambda _reason: None
    return runtime


def test_disabled_runtime_does_not_create_shadow_log(tmp_path) -> None:
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)

    runtime = TurnShadowRuntime(session_log=session_log, enabled=False)
    runtime.submit_wake("hello")
    runtime.submit_vad(True, agent_playing=False)
    runtime.submit_asr_final("hello there", agent_playing=False)
    runtime.submit_agent_playing(True)
    runtime.close()

    assert not (tmp_path / "turn_shadow.jsonl").exists()


def test_enabled_runtime_writes_both_detector_decisions(tmp_path) -> None:
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)
    runtime = TurnShadowRuntime(session_log=session_log, enabled=True)

    runtime.submit_wake("hello")
    runtime.close()

    lines = (tmp_path / "turn_shadow.jsonl").read_text(encoding="utf-8").splitlines()
    decisions = [json.loads(line) for line in lines]
    assert [decision["detector_name"] for decision in decisions] == [
        "baseline",
        "dynamic_v1",
    ]
    assert len({decision["event_id"] for decision in decisions}) == 2
    assert all(decision["session_id"] == "session-001" for decision in decisions)
    assert all(decision["turn_id"] == "turn-001" for decision in decisions)


def test_voice_runtime_mirrors_vad_without_changing_publish_path(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._sink = RecordingSink()
    runtime._turn_shadow = RecordingShadow()
    runtime._recording = True
    runtime._endpoint_controller = SimpleNamespace(on_vad=lambda *_args, **_kwargs: False)
    runtime._vad_holdoff_until = 0.0
    guard_calls = []

    def agent_playing() -> bool:
        guard_calls.append(True)
        return True

    runtime._is_tts_guard_active = agent_playing

    runtime._on_vad(True)

    assert runtime._sink.events == [("/vad_state", "bool", True)]
    assert guard_calls == []
    assert runtime._turn_shadow.events[0][:2] == ("vad", True)
    assert runtime._turn_shadow.events[0][2] is agent_playing


def test_voice_runtime_mirrors_wake_after_session_creation(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._sink = RecordingSink()
    runtime._turn_shadow = RecordingShadow()
    runtime._close_followup_window = lambda _reason: None
    runtime._new_session = lambda _word: "session-001"
    agent_playing = lambda: True
    runtime._is_tts_guard_active = agent_playing
    runtime._bus = SimpleNamespace(get_buffer=lambda: [])
    runtime._asr_preroll = lambda _snapshot: []
    runtime._asr = FakeASR()
    runtime._vprint = FakeVoiceprint()
    runtime._first_turn_mode_store = SimpleNamespace(read=lambda: "standard")
    runtime._turn_mode_store = SimpleNamespace(read=lambda: "basic")
    runtime._endpoint_controller = SimpleNamespace(begin=lambda *_args, **_kwargs: None)
    runtime._recording_lock = threading.Lock()
    runtime._vad_holdoff_until = 0.0
    runtime._arm_asr_max_recording_deadline = lambda: None
    runtime._session_log = None

    runtime._on_wake("hello")

    assert runtime._turn_shadow.events == [("wake", "hello", agent_playing)]
    assert runtime._recording is True
    assert runtime._sink.events[0][0] == "/wake_word_event"


def test_voice_runtime_mirrors_final_asr_text(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._sink = RecordingSink()
    runtime._turn_shadow = RecordingShadow()
    agent_playing = lambda: False
    runtime._is_tts_guard_active = agent_playing
    runtime._current_speaker = "speaker-001"
    runtime._session_id = "session-001"
    runtime._session_log = None

    runtime._on_asr("hello there")

    assert runtime._turn_shadow.events == [
        ("asr_final", "hello there", agent_playing)
    ]
    assert runtime._sink.events[0][0] == "/audio_msg"


def test_new_session_replaces_shadow_runtime_with_session_log(monkeypatch, tmp_path) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    module = sys.modules["surf_voice_runtime"]
    monkeypatch.setenv("TURN_SHADOW_ENABLE", "1")
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)
    created = []

    def create_shadow(*, session_log, enabled):
        created.append((session_log, enabled))
        return RecordingShadow()

    monkeypatch.setattr(module, "TurnShadowRuntime", create_shadow)
    runtime = object.__new__(SurfVoiceRuntime)
    previous = ClosingShadow()
    runtime._turn_shadow = previous
    runtime._pipeline_logger = SimpleNamespace(
        start_session=lambda _wake_word: session_log
    )

    assert runtime._new_session("hello") == "session-001"

    assert previous.closed is True
    assert created == [(session_log, True)]
    assert isinstance(runtime._turn_shadow, RecordingShadow)


def test_worker_continues_when_one_detector_fails_to_initialize(
    monkeypatch, tmp_path
) -> None:
    runtime_module = importlib.import_module("turn_detection.runtime_shadow")

    def broken_detector():
        raise RuntimeError("detector unavailable")

    monkeypatch.setattr(runtime_module, "BaselineDetector", broken_detector)
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)
    runtime = TurnShadowRuntime(session_log=session_log, enabled=True)

    runtime.submit_wake("hello")
    runtime.close()

    lines = (tmp_path / "turn_shadow.jsonl").read_text(encoding="utf-8").splitlines()
    decisions = [json.loads(line) for line in lines]
    assert [decision["detector_name"] for decision in decisions] == ["dynamic_v1"]


def test_vad_submission_never_waits_for_event_id_lock(tmp_path) -> None:
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)
    runtime = TurnShadowRuntime(session_log=session_log, enabled=False)
    runtime._enabled = True
    contended_lock = threading.Lock()
    contended_lock.acquire()
    runtime._sequence_lock = contended_lock
    submitter = threading.Thread(
        target=runtime.submit_vad,
        args=(True,),
        kwargs={"agent_playing": False},
    )

    try:
        submitter.start()
        submitter.join(timeout=0.05)
        assert not submitter.is_alive()
    finally:
        contended_lock.release()
        submitter.join(timeout=1.0)
        runtime.close()


def test_full_queue_drops_event_without_raising(tmp_path) -> None:
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)
    runtime = TurnShadowRuntime(
        session_log=session_log,
        enabled=False,
        queue_size=1,
    )
    runtime._enabled = True

    runtime.submit_wake("hello")
    runtime.submit_vad(True, agent_playing=False)
    runtime.close()

    assert runtime.dropped_count == 1


def test_final_asr_is_first_dynamic_end_of_turn_and_records_latency(
    monkeypatch, tmp_path
) -> None:
    runtime_module = importlib.import_module("turn_detection.runtime_shadow")
    timestamps = iter((1000.0, 1000.1, 1000.2, 1000.9))
    monkeypatch.setattr(runtime_module.time, "time", lambda: next(timestamps))
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)
    runtime = TurnShadowRuntime(session_log=session_log, enabled=True)

    runtime.submit_wake("hello")
    runtime.submit_vad(True, agent_playing=False)
    runtime.submit_vad(False, agent_playing=False)
    runtime.submit_asr_final("hello there", agent_playing=False)
    runtime.close()

    decisions = [
        json.loads(line)
        for line in (tmp_path / "turn_shadow.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    dynamic = [
        decision for decision in decisions if decision["detector_name"] == "dynamic_v1"
    ]
    assert [decision["decision"] for decision in dynamic] == [
        "UNCERTAIN",
        "CONTINUE_SPEAKING",
        "UNCERTAIN",
        "END_OF_TURN",
    ]
    assert dynamic[-1]["final_text"] == "hello there"
    assert dynamic[-1]["detector_latency_ms"] >= 0.0


def test_agent_playing_provider_runs_on_worker_not_submission_thread(tmp_path) -> None:
    session_log = SessionLog(session_id="session-001", session_dir=tmp_path)
    runtime = TurnShadowRuntime(session_log=session_log, enabled=True)
    submitting_thread = threading.get_ident()
    provider_threads = []

    def agent_playing() -> bool:
        provider_threads.append(threading.get_ident())
        return True

    runtime.submit_vad(True, agent_playing=agent_playing)
    runtime.close()

    decisions = [
        json.loads(line)
        for line in (tmp_path / "turn_shadow.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert provider_threads
    assert all(thread_id != submitting_thread for thread_id in provider_threads)
    assert all(decision["agent_playing"] is True for decision in decisions)


def test_voice_runtime_dispatches_each_new_manual_wake_request_once(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._session_lifecycle_lock = threading.Lock()
    runtime._dispatch = RecordingWakeDispatcher()
    runtime._interrupt_control = SessionCommandControl(
        {"command": "simulate_wake", "request_id": "manual-1", "wake_word": "你好小浦"}
    )
    runtime._last_session_command_request_id = ""

    runtime._poll_session_command()
    runtime._poll_session_command()

    assert runtime._dispatch.words == ["你好小浦"]


def test_voice_runtime_does_not_replay_session_command_present_at_startup(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._session_lifecycle_lock = threading.Lock()
    runtime._dispatch = RecordingWakeDispatcher()
    runtime._interrupt_control = SessionCommandControl(
        {"command": "simulate_wake", "request_id": "startup-request", "wake_word": "你好小浦"}
    )
    runtime._last_session_command_request_id = "startup-request"

    runtime._poll_session_command()

    assert runtime._dispatch.words == []


def test_voice_runtime_cancels_recording_when_session_close_command_arrives(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    for command_name in ("silent_end", "end_session"):
        calls = []

        class CancellableASR:
            def cancel_recording(self) -> None:
                calls.append("cancel")

            def stop_and_transcribe(self, expected_epoch=None) -> None:
                calls.append("transcribe")

        runtime = object.__new__(SurfVoiceRuntime)
        runtime._interrupt_control = SessionCommandControl(
            {"command": command_name, "request_id": f"{command_name}-1"}
        )
        runtime._last_session_command_request_id = ""
        runtime._session_lifecycle_lock = threading.Lock()
        runtime._recording_lock = threading.Lock()
        runtime._recording = True
        runtime._asr_deadline = 123.0
        runtime._asr_audio_frames = [b"cancel me"]
        runtime._asr = CancellableASR()
        runtime._sink = RecordingSink()
        runtime._followup_session_id = "session-001"
        runtime._followup_until = 456.0
        runtime._session_id = "session-001"
        runtime._session_log = SimpleNamespace(record=lambda *_args, **_kwargs: None)
        shadow = ClosingShadow()
        runtime._turn_shadow = shadow
        runtime._set_wake_light_blue = lambda _reason: None
        runtime._save_audio = lambda: calls.append("save")

        runtime._poll_session_command()
        finalized = runtime._finalize_recording("late_endpoint")

        assert calls == ["cancel"]
        assert finalized is False
        assert runtime._recording is False
        assert runtime._asr_deadline == 0.0
        assert runtime._asr_audio_frames == []
        assert runtime._followup_session_id == ""
        assert runtime._followup_until == 0.0
        assert runtime._session_id == ""
        assert runtime._session_log is None
        assert runtime._turn_shadow is None
        assert shadow.closed is True
        assert runtime._last_session_command_request_id == f"{command_name}-1"
        assert runtime._sink.events == []


def test_voice_runtime_serializes_wake_then_close_lifecycle(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    asr_start_entered = threading.Event()
    release_asr_start = threading.Event()
    close_started = threading.Event()
    close_finished = threading.Event()

    class BlockingASR:
        def start_recording(self, *, initial_audio: bytes) -> int:
            asr_start_entered.set()
            assert release_asr_start.wait(timeout=2.0)
            return 1

        def cancel_recording(self) -> None:
            return None

    runtime = object.__new__(SurfVoiceRuntime)
    lifecycle_lock = AttemptTrackingLock(threading.Lock(), "close-worker")
    runtime._session_lifecycle_lock = lifecycle_lock
    runtime._recording_lock = threading.Lock()
    runtime._followup_session_id = ""
    runtime._followup_until = 0.0
    runtime._session_id = ""
    runtime._session_log = None
    runtime._turn_shadow = None
    runtime._new_session = lambda _word: "new-session"
    runtime._is_tts_guard_active = lambda: False
    runtime._sink = RecordingSink()
    runtime._bus = SimpleNamespace(get_buffer=lambda: [])
    runtime._asr_preroll = lambda _snapshot: []
    runtime._first_turn_mode_store = SimpleNamespace(read=lambda: "standard")
    runtime._first_turn_compat_silence_sec = 0.0
    runtime._turn_mode_store = SimpleNamespace(read=lambda: "basic")
    runtime._endpoint_controller = SimpleNamespace(begin=lambda *_args, **_kwargs: None)
    runtime._asr_audio_frames = []
    runtime._recording = False
    runtime._asr = BlockingASR()
    runtime._vprint = FakeVoiceprint()
    runtime._vad_holdoff_until = 0.0
    runtime._asr_deadline = 0.0
    runtime._set_wake_light_blue = lambda _reason: None
    runtime._dispatch = SimpleNamespace(on_detection=runtime._on_wake)

    wake_worker = threading.Thread(target=runtime._submit_wake_detection, args=("hello",))

    def close_session() -> None:
        close_started.set()
        runtime._handle_session_close("silent_end")
        close_finished.set()

    close_worker = threading.Thread(target=close_session, name="close-worker")
    wake_worker.start()
    assert asr_start_entered.wait(timeout=2.0)
    close_worker.start()
    assert close_started.wait(timeout=2.0)
    close_attempted_lock = lifecycle_lock.acquire_attempted.wait(timeout=2.0)
    close_was_blocked = not close_finished.is_set()
    release_asr_start.set()
    wake_worker.join(timeout=2.0)
    close_worker.join(timeout=2.0)

    assert close_attempted_lock
    assert close_was_blocked
    assert not wake_worker.is_alive()
    assert not close_worker.is_alive()
    assert close_finished.is_set()
    assert runtime._recording is False
    assert runtime._asr_deadline == 0.0
    assert runtime._session_id == ""


def test_voice_runtime_close_then_wake_creates_clean_new_recording(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    calls = []

    class RecordingASR:
        def cancel_recording(self) -> None:
            calls.append("cancel")

        def start_recording(self, *, initial_audio: bytes) -> int:
            calls.append(("start", initial_audio))
            return 1

    runtime = object.__new__(SurfVoiceRuntime)
    runtime._session_lifecycle_lock = threading.Lock()
    runtime._recording_lock = threading.Lock()
    runtime._followup_session_id = "old-session"
    runtime._followup_until = 1.0
    runtime._session_id = "old-session"
    runtime._session_log = SimpleNamespace(record=lambda *_args, **_kwargs: None)
    runtime._turn_shadow = None
    runtime._set_wake_light_blue = lambda _reason: None
    runtime._recording = True
    runtime._asr_deadline = 1.0
    runtime._asr_audio_frames = [b"old"]
    runtime._asr = RecordingASR()
    runtime._new_session = lambda _word: "new-session"
    runtime._is_tts_guard_active = lambda: False
    runtime._sink = RecordingSink()
    runtime._bus = SimpleNamespace(get_buffer=lambda: [b"new"])
    runtime._asr_preroll = lambda snapshot: snapshot
    runtime._first_turn_mode_store = SimpleNamespace(read=lambda: "standard")
    runtime._first_turn_compat_silence_sec = 0.0
    runtime._turn_mode_store = SimpleNamespace(read=lambda: "basic")
    runtime._endpoint_controller = SimpleNamespace(begin=lambda *_args, **_kwargs: None)
    runtime._vprint = FakeVoiceprint()
    runtime._vad_holdoff_until = 0.0
    runtime._dispatch = SimpleNamespace(on_detection=runtime._on_wake)

    runtime._handle_session_close("end_session")
    runtime._submit_wake_detection("hello")

    assert calls == ["cancel", ("start", b"new")]
    assert runtime._recording is True
    assert runtime._asr_deadline > 0.0
    assert runtime._session_id == "new-session"
    assert runtime._asr_audio_frames == [b"new"]


def test_voice_runtime_serializes_followup_start_then_close(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    followup_start_paused = threading.Event()
    release_followup_start = threading.Event()
    close_finished = threading.Event()
    calls = []

    class RecordingASR:
        def start_recording(self, *, initial_audio: bytes) -> int:
            calls.append("start")
            return 7

        def cancel_recording(self) -> None:
            calls.append("cancel")

    class BlockingVoiceprint:
        def start_capture(self, *, initial_audio: bytes) -> None:
            followup_start_paused.set()
            assert release_followup_start.wait(timeout=2.0)

    runtime = object.__new__(SurfVoiceRuntime)
    lifecycle_lock = AttemptTrackingLock(threading.Lock(), "close-followup-worker")
    runtime._session_lifecycle_lock = lifecycle_lock
    runtime._recording_lock = threading.Lock()
    runtime._recording = False
    runtime._asr_recording_epoch = None
    runtime._asr_deadline = 0.0
    runtime._asr_audio_frames = []
    runtime._asr = RecordingASR()
    runtime._followup_session_id = "followup-session"
    runtime._followup_until = 100.0
    runtime._session_id = ""
    runtime._session_log = None
    runtime._turn_shadow = None
    runtime._is_tts_guard_active = lambda: False
    runtime._set_wake_light_blue = lambda _reason: None
    runtime._pipeline_logger = SimpleNamespace(
        attach_session=lambda _session_id: SimpleNamespace(record=lambda *_args, **_kwargs: None)
    )
    runtime._bus = SimpleNamespace(get_buffer=lambda: [b"followup"])
    runtime._asr_preroll = lambda snapshot: snapshot
    runtime._endpoint_controller = SimpleNamespace(begin=lambda *_args, **_kwargs: None)
    runtime._turn_mode_store = SimpleNamespace(read=lambda: "basic")
    runtime._vprint = BlockingVoiceprint()
    runtime._vad_holdoff_until = 0.0

    followup_worker = threading.Thread(target=runtime._start_followup_recording)

    def close_session() -> None:
        runtime._handle_session_close("silent_end")
        close_finished.set()

    close_worker = threading.Thread(target=close_session, name="close-followup-worker")
    followup_worker.start()
    assert followup_start_paused.wait(timeout=2.0)
    close_worker.start()
    close_attempted_lock = lifecycle_lock.acquire_attempted.wait(timeout=2.0)
    close_was_blocked = not close_finished.is_set()
    release_followup_start.set()
    followup_worker.join(timeout=2.0)
    close_worker.join(timeout=2.0)

    assert close_attempted_lock
    assert close_was_blocked
    assert not followup_worker.is_alive()
    assert not close_worker.is_alive()
    assert calls == ["start", "cancel"]
    assert runtime._recording is False
    assert runtime._asr_recording_epoch is None
    assert runtime._asr_deadline == 0.0
    assert runtime._session_id == ""
    assert runtime._followup_session_id == ""


def test_voice_runtime_close_then_followup_start_is_clean_noop(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    calls = []

    class RecordingASR:
        def cancel_recording(self) -> None:
            calls.append("cancel")

        def start_recording(self, *, initial_audio: bytes) -> int:
            calls.append("start")
            return 1

    runtime = object.__new__(SurfVoiceRuntime)
    lifecycle_lock = AttemptTrackingLock(threading.Lock(), "followup-after-close-worker")
    runtime._session_lifecycle_lock = lifecycle_lock
    runtime._recording_lock = threading.Lock()
    runtime._recording = True
    runtime._asr_recording_epoch = 1
    runtime._asr_deadline = 1.0
    runtime._asr_audio_frames = [b"old"]
    runtime._asr = RecordingASR()
    runtime._followup_session_id = "old-session"
    runtime._followup_until = 100.0
    runtime._session_id = "old-session"
    runtime._session_log = SimpleNamespace(record=lambda *_args, **_kwargs: None)
    runtime._turn_shadow = None
    runtime._set_wake_light_blue = lambda _reason: None

    runtime._handle_session_close("end_session")
    followup_worker = threading.Thread(
        target=runtime._start_followup_recording,
        name="followup-after-close-worker",
    )
    followup_worker.start()
    followup_attempted_lock = lifecycle_lock.acquire_attempted.wait(timeout=2.0)
    followup_worker.join(timeout=2.0)

    assert followup_attempted_lock
    assert not followup_worker.is_alive()
    assert calls == ["cancel"]
    assert runtime._recording is False
    assert runtime._asr_recording_epoch is None
    assert runtime._asr_deadline == 0.0
    assert runtime._session_id == ""
    assert runtime._followup_session_id == ""


def test_session_close_watermark_rejects_unconsumed_older_followup_open(monkeypatch, tmp_path) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    control_path = tmp_path / "followup_control.json"
    control_path.write_text(
        json.dumps(
            {
                "command": "open",
                "session_id": "old-session",
                "timeout_sec": 20.0,
                "updated_at": 150.0,
            }
        ),
        encoding="utf-8",
    )
    runtime = _make_followup_control_runtime(
        SurfVoiceRuntime,
        control_path,
        {"command": "silent_end", "request_id": "close-1", "updated_at": 200.0},
    )

    runtime._poll_session_command()
    runtime._poll_followup_control()

    assert runtime._followup_close_watermark == 200.0
    assert runtime._followup_session_id == ""
    assert runtime._followup_until == 0.0
    assert runtime._recording is False
    runtime._start_followup_recording()
    assert runtime._asr.start_count == 0


def test_followup_open_then_session_close_is_serialized_and_closed(monkeypatch, tmp_path) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    open_paused = threading.Event()
    release_open = threading.Event()
    close_finished = threading.Event()
    lifecycle_lock = AttemptTrackingLock(threading.Lock(), "close-control-worker")
    control_path = tmp_path / "followup_control.json"
    control_path.write_text(
        json.dumps(
            {
                "command": "open",
                "session_id": "session-1",
                "timeout_sec": 20.0,
                "updated_at": 150.0,
            }
        ),
        encoding="utf-8",
    )
    runtime = _make_followup_control_runtime(
        SurfVoiceRuntime,
        control_path,
        {"command": "end_session", "request_id": "close-1", "updated_at": 200.0},
        lifecycle_lock=lifecycle_lock,
    )

    def reset_vad() -> None:
        open_paused.set()
        assert release_open.wait(timeout=2.0)

    runtime._vad = SimpleNamespace(reset=reset_vad)
    open_worker = threading.Thread(target=runtime._poll_followup_control)

    def close_session() -> None:
        runtime._poll_session_command()
        close_finished.set()

    close_worker = threading.Thread(target=close_session, name="close-control-worker")
    open_worker.start()
    assert open_paused.wait(timeout=2.0)
    close_worker.start()
    close_attempted_lock = lifecycle_lock.acquire_attempted.wait(timeout=2.0)
    close_was_blocked = not close_finished.is_set()
    release_open.set()
    open_worker.join(timeout=2.0)
    close_worker.join(timeout=2.0)

    assert close_attempted_lock
    assert close_was_blocked
    assert not open_worker.is_alive()
    assert not close_worker.is_alive()
    assert runtime._followup_session_id == ""
    assert runtime._followup_until == 0.0


def test_session_close_then_older_followup_open_is_serialized_and_rejected(monkeypatch, tmp_path) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    close_paused = threading.Event()
    release_close = threading.Event()
    lifecycle_lock = AttemptTrackingLock(threading.Lock(), "open-after-close-worker")
    control_path = tmp_path / "followup_control.json"
    control_path.write_text(
        json.dumps(
            {
                "command": "open",
                "session_id": "old-session",
                "timeout_sec": 20.0,
                "updated_at": 150.0,
            }
        ),
        encoding="utf-8",
    )
    runtime = _make_followup_control_runtime(
        SurfVoiceRuntime,
        control_path,
        {"command": "silent_end", "request_id": "close-1", "updated_at": 200.0},
        lifecycle_lock=lifecycle_lock,
    )

    def cancel_recording() -> None:
        close_paused.set()
        assert release_close.wait(timeout=2.0)

    runtime._asr.cancel_recording = cancel_recording
    close_worker = threading.Thread(target=runtime._poll_session_command)
    open_worker = threading.Thread(
        target=runtime._poll_followup_control,
        name="open-after-close-worker",
    )
    close_worker.start()
    assert close_paused.wait(timeout=2.0)
    open_worker.start()
    open_attempted_lock = lifecycle_lock.acquire_attempted.wait(timeout=0.5)
    open_was_blocked = runtime._followup_session_id == ""
    release_close.set()
    close_worker.join(timeout=2.0)
    open_worker.join(timeout=2.0)

    assert open_attempted_lock
    assert open_was_blocked
    assert not close_worker.is_alive()
    assert not open_worker.is_alive()
    assert runtime._followup_session_id == ""
    assert runtime._followup_until == 0.0


def test_followup_open_newer_than_session_close_is_accepted(monkeypatch, tmp_path) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    control_path = tmp_path / "followup_control.json"
    control_path.write_text(
        json.dumps(
            {
                "command": "open",
                "session_id": "new-session",
                "timeout_sec": 20.0,
                "updated_at": 201.0,
            }
        ),
        encoding="utf-8",
    )
    runtime = _make_followup_control_runtime(
        SurfVoiceRuntime,
        control_path,
        {"command": "end_session", "request_id": "close-1", "updated_at": 200.0},
    )

    runtime._poll_session_command()
    runtime._poll_followup_control()

    assert runtime._followup_close_watermark == 200.0
    assert runtime._followup_session_id == "new-session"
    assert runtime._followup_until > 0.0


def test_delayed_newer_open_for_terminally_closed_session_is_rejected(monkeypatch, tmp_path) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    control_path = tmp_path / "followup_control.json"
    control_path.write_text(
        json.dumps(
            {
                "command": "open",
                "session_id": "old-session",
                "timeout_sec": 20.0,
                "updated_at": 201.0,
            }
        ),
        encoding="utf-8",
    )
    runtime = _make_followup_control_runtime(
        SurfVoiceRuntime,
        control_path,
        {
            "command": "silent_end",
            "request_id": "close-1",
            "session_id": "old-session",
            "updated_at": 200.0,
        },
    )

    runtime._poll_session_command()
    runtime._poll_followup_control()

    assert runtime._followup_session_id == ""
    assert "old-session" in runtime._closed_session_ids


def test_new_wake_session_can_open_followup_after_older_session_closed(monkeypatch, tmp_path) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    control_path = tmp_path / "followup_control.json"
    runtime = _make_followup_control_runtime(
        SurfVoiceRuntime,
        control_path,
        {
            "command": "end_session",
            "request_id": "close-1",
            "session_id": "old-session",
            "updated_at": 200.0,
        },
    )
    runtime._new_session = lambda _word: "new-session"
    runtime._is_tts_guard_active = lambda: False
    runtime._sink = RecordingSink()
    runtime._bus = SimpleNamespace(get_buffer=lambda: [])
    runtime._asr_preroll = lambda _snapshot: []
    runtime._first_turn_mode_store = SimpleNamespace(read=lambda: "standard")
    runtime._first_turn_compat_silence_sec = 0.0
    runtime._turn_mode_store = SimpleNamespace(read=lambda: "basic")
    runtime._endpoint_controller = SimpleNamespace(begin=lambda *_args, **_kwargs: None)
    runtime._vprint = FakeVoiceprint()
    runtime._vad_holdoff_until = 0.0
    runtime._dispatch = SimpleNamespace(on_detection=runtime._on_wake)

    runtime._poll_session_command()
    runtime._submit_wake_detection("hello")
    control_path.write_text(
        json.dumps(
            {
                "command": "open",
                "session_id": "new-session",
                "timeout_sec": 20.0,
                "updated_at": 201.0,
            }
        ),
        encoding="utf-8",
    )
    runtime._poll_followup_control()

    assert "old-session" in runtime._closed_session_ids
    assert "new-session" not in runtime._closed_session_ids
    assert runtime._followup_session_id == "new-session"


def test_close_without_command_session_tombstones_runtime_and_followup_sessions(
    monkeypatch, tmp_path
) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    runtime = _make_followup_control_runtime(
        SurfVoiceRuntime,
        tmp_path / "followup_control.json",
        {"command": "silent_end", "request_id": "close-1", "updated_at": 200.0},
    )
    runtime._session_id = "runtime-session"
    runtime._followup_session_id = "followup-session"
    runtime._followup_until = 100.0

    runtime._poll_session_command()

    assert set(runtime._closed_session_ids) == {"runtime-session", "followup-session"}
    assert runtime._session_id == ""
    assert runtime._followup_session_id == ""


def test_stale_finalizer_cannot_stop_recording_started_after_close(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    old_save_started = threading.Event()
    release_old_save = threading.Event()

    class TokenASR:
        def __init__(self) -> None:
            self.epoch = 0
            self.recording = False
            self.stop_attempts = []

        def start_recording(self, *, initial_audio: bytes) -> int:
            self.epoch += 1
            self.recording = True
            return self.epoch

        def cancel_recording(self) -> None:
            self.epoch += 1
            self.recording = False

        def stop_and_transcribe(self, expected_epoch=None) -> bool:
            self.stop_attempts.append(expected_epoch)
            if not self.recording or expected_epoch != self.epoch:
                return False
            self.recording = False
            return True

    asr = TokenASR()
    old_token = asr.start_recording(initial_audio=b"old")
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._session_lifecycle_lock = threading.Lock()
    runtime._recording_lock = threading.Lock()
    runtime._recording = True
    runtime._asr_recording_epoch = old_token
    runtime._asr_deadline = 1.0
    runtime._asr_audio_frames = [b"old"]
    runtime._asr = asr
    runtime._followup_session_id = ""
    runtime._followup_until = 0.0
    runtime._session_id = "old-session"
    runtime._session_log = None
    runtime._turn_shadow = None
    runtime._set_wake_light_blue = lambda _reason: None
    runtime._new_session = lambda _word: "new-session"
    runtime._is_tts_guard_active = lambda: False
    runtime._sink = RecordingSink()
    runtime._bus = SimpleNamespace(get_buffer=lambda: [b"new"])
    runtime._asr_preroll = lambda snapshot: snapshot
    runtime._first_turn_mode_store = SimpleNamespace(read=lambda: "standard")
    runtime._first_turn_compat_silence_sec = 0.0
    runtime._turn_mode_store = SimpleNamespace(read=lambda: "basic")
    runtime._endpoint_controller = SimpleNamespace(begin=lambda *_args, **_kwargs: None)
    runtime._vprint = FakeVoiceprint()
    runtime._vad_holdoff_until = 0.0
    runtime._dispatch = SimpleNamespace(on_detection=runtime._on_wake)
    save_count = 0

    def save_audio() -> None:
        nonlocal save_count
        save_count += 1
        if save_count == 1:
            old_save_started.set()
            assert release_old_save.wait(timeout=2.0)

    runtime._save_audio = save_audio
    old_finalizer = threading.Thread(target=runtime._finalize_recording, args=("old",))
    old_finalizer.start()
    assert old_save_started.wait(timeout=2.0)

    runtime._handle_session_close("silent_end")
    runtime._submit_wake_detection("hello")
    new_token = asr.epoch
    release_old_save.set()
    old_finalizer.join(timeout=2.0)

    assert not old_finalizer.is_alive()
    assert asr.stop_attempts == [old_token]
    assert asr.recording is True
    assert runtime._recording is True
    assert runtime._asr_recording_epoch == new_token
    assert runtime._session_id == "new-session"
    assert runtime._asr_deadline > 0.0

    assert runtime._finalize_recording("new") is True
    assert asr.stop_attempts == [old_token, new_token]
    assert asr.recording is False


def test_voice_runtime_serializes_real_and_manual_wake_for_dispatcher_dedup(monkeypatch) -> None:
    SurfVoiceRuntime = _load_voice_runtime(monkeypatch)
    runtime = object.__new__(SurfVoiceRuntime)
    runtime._session_lifecycle_lock = threading.Lock()
    runtime._interrupt_control = SessionCommandControl(
        {"command": "simulate_wake", "request_id": "manual-race", "wake_word": "你好小浦"}
    )
    runtime._last_session_command_request_id = ""
    barrier = threading.Barrier(2)
    sessions = []

    class RacingDedupDispatcher:
        def __init__(self) -> None:
            self.seen = set()

        def on_detection(self, word: str) -> None:
            should_fire = word not in self.seen
            try:
                barrier.wait(timeout=0.05)
            except threading.BrokenBarrierError:
                pass
            if should_fire:
                self.seen.add(word)
                sessions.append(f"session-{len(sessions) + 1}")

    runtime._dispatch = RacingDedupDispatcher()
    real = threading.Thread(target=runtime._submit_wake_detection, args=("你好小浦",))
    manual = threading.Thread(target=runtime._poll_session_command)

    real.start()
    manual.start()
    real.join(timeout=1.0)
    manual.join(timeout=1.0)

    assert not real.is_alive()
    assert not manual.is_alive()
    assert sessions == ["session-1"]
