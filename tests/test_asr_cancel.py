from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
ASR_ENGINE_PATH = ROOT / "deps/SURF2026_VoiceModule-main/asr/asr_engine.py"


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


def _load_asr_engine(monkeypatch, model):
    funasr = ModuleType("funasr")
    funasr.AutoModel = lambda **_kwargs: model
    monkeypatch.setitem(sys.modules, "funasr", funasr)

    config_package = ModuleType("config")
    config_module = ModuleType("config.voice_config")
    config_module.CONFIG = SimpleNamespace(
        asr_model="test-model",
        asr_vad_model="",
        asr_vad_max_single_segment_time=0,
    )
    monkeypatch.setitem(sys.modules, "config", config_package)
    monkeypatch.setitem(sys.modules, "config.voice_config", config_module)

    spec = importlib.util.spec_from_file_location("test_asr_engine_module", ASR_ENGINE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.ASREngine


def test_cancel_drops_transcription_that_is_already_running(monkeypatch) -> None:
    generate_started = threading.Event()
    release_generate = threading.Event()
    results = []

    class BlockingModel:
        def generate(self, **_kwargs):
            generate_started.set()
            assert release_generate.wait(timeout=2.0)
            return [{"text": "late old result"}]

    ASREngine = _load_asr_engine(monkeypatch, BlockingModel())
    engine = ASREngine(on_result=results.append)
    engine.start_recording(initial_audio=b"\x00\x00")
    worker = threading.Thread(target=engine.stop_and_transcribe)
    worker.start()
    assert generate_started.wait(timeout=2.0)

    engine.cancel_recording()
    release_generate.set()
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert results == []


def test_cancelled_old_result_cannot_replace_new_recording_result(monkeypatch) -> None:
    old_generate_started = threading.Event()
    release_old_generate = threading.Event()
    results = []

    class SequencedModel:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._calls = 0

        def generate(self, **_kwargs):
            with self._lock:
                self._calls += 1
                call = self._calls
            if call == 1:
                old_generate_started.set()
                assert release_old_generate.wait(timeout=2.0)
                return [{"text": "old result"}]
            return [{"text": "new result"}]

    ASREngine = _load_asr_engine(monkeypatch, SequencedModel())
    engine = ASREngine(on_result=results.append)
    engine.start_recording(initial_audio=b"\x00\x00")
    old_worker = threading.Thread(target=engine.stop_and_transcribe)
    old_worker.start()
    assert old_generate_started.wait(timeout=2.0)

    engine.cancel_recording()
    engine.start_recording(initial_audio=b"\x01\x00")
    engine.stop_and_transcribe()
    release_old_generate.set()
    old_worker.join(timeout=2.0)

    assert not old_worker.is_alive()
    assert results == ["new result"]


def test_normal_recording_still_publishes_one_transcription(monkeypatch) -> None:
    class ImmediateModel:
        def generate(self, **_kwargs):
            return [{"text": "normal result"}]

    results = []
    ASREngine = _load_asr_engine(monkeypatch, ImmediateModel())
    engine = ASREngine(on_result=results.append)
    recording_epoch = engine.start_recording(initial_audio=b"\x00\x00")

    stopped = engine.stop_and_transcribe(expected_epoch=recording_epoch)

    assert stopped is True
    assert results == ["normal result"]


def test_stale_stop_token_does_not_stop_new_recording(monkeypatch) -> None:
    class ImmediateModel:
        def generate(self, **_kwargs):
            return [{"text": "new result"}]

    results = []
    ASREngine = _load_asr_engine(monkeypatch, ImmediateModel())
    engine = ASREngine(on_result=results.append)
    old_epoch = engine.start_recording(initial_audio=b"\x00\x00")
    engine.cancel_recording()
    new_epoch = engine.start_recording(initial_audio=b"\x01\x00")

    assert engine.stop_and_transcribe(expected_epoch=old_epoch) is False
    assert engine.stop_and_transcribe(expected_epoch=new_epoch) is True
    assert results == ["new result"]


def test_result_callback_can_cancel_reentrantly_without_deadlock(monkeypatch) -> None:
    class ImmediateModel:
        def generate(self, **_kwargs):
            return [{"text": "result"}]

    callback_finished = threading.Event()
    engine_holder = {}

    def on_result(_text: str) -> None:
        engine_holder["engine"].cancel_recording()
        callback_finished.set()

    ASREngine = _load_asr_engine(monkeypatch, ImmediateModel())
    engine = ASREngine(on_result=on_result)
    engine_holder["engine"] = engine
    engine.start_recording(initial_audio=b"\x00\x00")
    worker = threading.Thread(target=engine.stop_and_transcribe, daemon=True)
    worker.start()

    assert callback_finished.wait(timeout=2.0)
    worker.join(timeout=2.0)
    assert not worker.is_alive()


def test_cancel_waits_for_callback_that_already_started(monkeypatch) -> None:
    class ImmediateModel:
        def generate(self, **_kwargs):
            return [{"text": "result"}]

    callback_started = threading.Event()
    release_callback = threading.Event()
    callback_finished = threading.Event()
    cancel_started = threading.Event()
    cancel_finished = threading.Event()
    order = []

    def on_result(_text: str) -> None:
        order.append("callback_started")
        callback_started.set()
        assert release_callback.wait(timeout=2.0)
        order.append("callback_finished")
        callback_finished.set()

    ASREngine = _load_asr_engine(monkeypatch, ImmediateModel())
    engine = ASREngine(on_result=on_result)
    publication_lock = AttemptTrackingLock(engine._publication_lock, "cancel-worker")
    engine._publication_lock = publication_lock
    engine.start_recording(initial_audio=b"\x00\x00")
    transcription = threading.Thread(target=engine.stop_and_transcribe)
    transcription.start()
    assert callback_started.wait(timeout=2.0)

    def cancel() -> None:
        cancel_started.set()
        engine.cancel_recording()
        order.append("cancel_returned")
        cancel_finished.set()

    cancellation = threading.Thread(target=cancel, name="cancel-worker")
    cancellation.start()
    assert cancel_started.wait(timeout=2.0)
    assert publication_lock.acquire_attempted.wait(timeout=2.0)
    assert not cancel_finished.is_set()

    release_callback.set()
    assert callback_finished.wait(timeout=2.0)
    assert cancel_finished.wait(timeout=2.0)
    transcription.join(timeout=2.0)
    cancellation.join(timeout=2.0)

    assert not transcription.is_alive()
    assert not cancellation.is_alive()
    assert order == ["callback_started", "callback_finished", "cancel_returned"]
