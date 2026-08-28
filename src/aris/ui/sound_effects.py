from __future__ import annotations

import io
import threading
import wave
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from aris.voice.audio_playback import play_wav_bytes, stop_playback


class SoundEffectPlayer(QObject):
    """Phát cue WAV local ở worker và gửi biên độ cho HUD mà không chặn giao diện."""

    level_changed = Signal(float)
    effect_started = Signal(str, int)
    effect_finished = Signal(str)

    def __init__(self, effects: dict[str, Path], parent: QObject | None = None) -> None:
        """Nhận ánh xạ tên cue sang file WAV; file thiếu sẽ trở thành fallback im lặng."""
        super().__init__(parent)
        self._effects = {name: Path(path) for name, path in effects.items()}
        self._generation = 0
        self._lock = threading.Lock()

    def duration_ms(self, name: str) -> int:
        """Đọc thời lượng WAV theo mili giây hoặc trả 0 nếu cue không khả dụng."""
        source = self._effects.get(name)
        if source is None or not source.is_file():
            return 0
        try:
            with wave.open(str(source), "rb") as wav_file:
                return round(wav_file.getnframes() / wav_file.getframerate() * 1000)
        except (OSError, ValueError, wave.Error, ZeroDivisionError):
            return 0

    def play(self, name: str, *, reverse: bool = False) -> int:
        """Phát cue trên worker, tùy chọn đảo thời gian trong RAM cho hiệu ứng đóng."""
        duration_ms = self.duration_ms(name)
        source = self._effects.get(name)
        if duration_ms <= 0 or source is None:
            return 0
        with self._lock:
            self._generation += 1
            generation = self._generation
        threading.Thread(
            target=self._play_worker,
            args=(name, source, generation, duration_ms, reverse),
            name=f"aris-sfx-{name}",
            daemon=True,
        ).start()
        return duration_ms

    def stop(self) -> None:
        """Dừng cue hiện tại và vô hiệu signal muộn của worker cũ."""
        with self._lock:
            self._generation += 1
        stop_playback()
        self.level_changed.emit(0.0)

    def _is_current(self, generation: int) -> bool:
        """Kiểm tra worker còn sở hữu kênh hiệu ứng trước khi phát signal UI."""
        with self._lock:
            return generation == self._generation

    def _emit_level(self, generation: int, level: float) -> None:
        """Loại signal âm lượng cũ để cue trước không làm logo tụt sáng cue mới."""
        if self._is_current(generation):
            self.level_changed.emit(level)

    def _play_worker(
        self,
        name: str,
        source: Path,
        generation: int,
        duration_ms: int,
        reverse: bool,
    ) -> None:
        """Đọc file local trong worker rồi dùng backend sounddevice không phát tiếng Windows."""
        try:
            payload = source.read_bytes()
            if reverse:
                payload = reverse_wav_bytes(payload)
            if not self._is_current(generation):
                return
            self.effect_started.emit(name, duration_ms)
            play_wav_bytes(
                payload,
                lambda level: self._emit_level(generation, level),
            )
        except Exception:
            # Hiệu ứng là tùy chọn; lỗi audio không được biến thành âm báo Windows hoặc lỗi HUD.
            pass
        finally:
            if self._is_current(generation):
                self.level_changed.emit(0.0)
                self.effect_finished.emit(name)


def reverse_wav_bytes(payload: bytes) -> bytes:
    """Đảo thứ tự frame PCM trong RAM để tạo cue de-materialize mà không sinh file mới."""
    source = io.BytesIO(payload)
    with wave.open(source, "rb") as wav_file:
        parameters = wav_file.getparams()
        frame_width = wav_file.getnchannels() * wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())
    if frame_width <= 0 or len(frames) % frame_width != 0:
        raise ValueError("Invalid PCM frame width.")
    reversed_frames = b"".join(
        frames[index : index + frame_width]
        for index in range(len(frames) - frame_width, -1, -frame_width)
    )
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setparams(parameters)
        wav_file.writeframes(reversed_frames)
    return output.getvalue()
