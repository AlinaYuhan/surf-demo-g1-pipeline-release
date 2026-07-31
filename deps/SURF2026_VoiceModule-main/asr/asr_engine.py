from __future__ import annotations

import contextlib
import io
import logging
import os
import threading
from typing import Callable

import numpy as np
from funasr import AutoModel

from config.voice_config import CONFIG

logger = logging.getLogger(__name__)


class ASREngine:
    """FunASR paraformer-zh 封装，实现唤醒触发 → 录音 → 转写状态机。

    状态机：IDLE ──start_recording()──► RECORDING ──stop_and_transcribe()──► IDLE
    """

    def __init__(
        self,
        on_result: Callable[[str], None],
        model_name: str = CONFIG.asr_model,
    ) -> None:
        self._on_result = on_result
        model_kwargs = {
            "model": model_name,
            "disable_update": True,
        }
        if CONFIG.asr_vad_model:
            model_kwargs["vad_model"] = CONFIG.asr_vad_model
            model_kwargs["vad_kwargs"] = {
                "max_single_segment_time": CONFIG.asr_vad_max_single_segment_time,
            }
        with self._suppress_model_output():
            self._model = AutoModel(**model_kwargs)
        self._publication_lock = threading.RLock()
        self._lock = threading.Lock()
        self._recording = False
        self._buffer = b""
        self._recording_epoch = 0

    def start_recording(self, initial_audio: bytes = b"") -> int:
        with self._publication_lock:
            with self._lock:
                self._recording_epoch += 1
                self._recording = True
                self._buffer = initial_audio
                return self._recording_epoch

    def cancel_recording(self) -> None:
        with self._publication_lock:
            with self._lock:
                self._recording_epoch += 1
                self._recording = False
                self._buffer = b""

    def push_audio(self, pcm: bytes) -> None:
        with self._lock:
            if not self._recording:
                return
            self._buffer += pcm

    def stop_and_transcribe(self, expected_epoch: int | None = None) -> bool:
        with self._lock:
            if not self._recording:
                return False
            if expected_epoch is not None and expected_epoch != self._recording_epoch:
                return False
            self._recording = False
            audio_data = self._buffer
            self._buffer = b""
            recording_epoch = self._recording_epoch

        if not audio_data:
            return True

        audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        with self._suppress_model_output():
            result = self._model.generate(input=audio, batch_size_s=300)
        text = result[0].get("text", "").strip() if result else ""
        with self._publication_lock:
            with self._lock:
                if recording_epoch != self._recording_epoch:
                    return True
            self._on_result(text)
        return True

    @staticmethod
    @contextlib.contextmanager
    def _suppress_model_output():
        if os.environ.get("VOICE_ASR_VERBOSE", "").strip().lower() in ("1", "true", "yes", "on"):
            yield
            return

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            yield

        captured = (stdout.getvalue() + stderr.getvalue()).strip()
        if captured:
            logger.debug("suppressed ASR model output: %s", captured[:500])
