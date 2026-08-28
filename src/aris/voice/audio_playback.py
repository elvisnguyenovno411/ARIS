from __future__ import annotations

import io
import threading
import wave
from collections.abc import Callable

import numpy as np

_PLAYBACK_STATE_LOCK = threading.Lock()
_PLAYBACK_DEVICE_LOCK = threading.Lock()
_ACTIVE_STOP_EVENT: threading.Event | None = None
_LEVEL_WINDOW_SECONDS = 0.04


def decode_wav_bytes(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Giải mã WAV PCM trong RAM thành mảng float32 và sample rate để phát local."""
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        compression = wav_file.getcomptype()
        frames = wav_file.readframes(wav_file.getnframes())
    if compression != "NONE":
        raise ValueError("Compressed WAV playback is not supported.")
    if sample_width == 1:
        samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 3:
        packed = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = packed[:, 0] | (packed[:, 1] << 8) | (packed[:, 2] << 16)
        signed = (values ^ 0x800000) - 0x800000
        samples = signed.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width} bytes.")
    if channels > 1:
        samples = samples.reshape(-1, channels)
    return samples, sample_rate


def play_wav_bytes(
    audio_bytes: bytes,
    level_callback: Callable[[float], None] | None = None,
) -> None:
    """Phát WAV trong RAM và tùy chọn phát phong bì âm lượng đồng bộ cho HUD."""
    samples, sample_rate = decode_wav_bytes(audio_bytes)
    stop_event = threading.Event()
    global _ACTIVE_STOP_EVENT
    with _PLAYBACK_STATE_LOCK:
        previous = _ACTIVE_STOP_EVENT
        _ACTIVE_STOP_EVENT = stop_event
    if previous is not None:
        previous.set()

    mono = samples if samples.ndim == 1 else samples.mean(axis=1)
    window_frames = max(1, round(sample_rate * _LEVEL_WINDOW_SECONDS))
    try:
        # sounddevice convenience playback dùng state CFFI toàn cục. Giữ đúng một owner
        # để cue, cloud TTS và barge-in không gọi PortAudio chồng nhau trên Windows.
        with _PLAYBACK_DEVICE_LOCK:
            if stop_event.is_set():
                return
            import sounddevice as sd

            try:
                sd.play(samples, sample_rate, blocking=False)
                for start in range(0, len(mono), window_frames):
                    if stop_event.is_set():
                        break
                    block = mono[start : start + window_frames]
                    if level_callback is not None:
                        rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
                        level_callback(max(0.0, min(1.0, rms * 4.8)))
                    duration = len(block) / sample_rate
                    if stop_event.wait(duration):
                        break
                if not stop_event.is_set():
                    sd.wait()
            finally:
                # Đóng convenience stream trước khi worker khác được chạm vào CFFI backend.
                sd.stop(ignore_errors=True)
    finally:
        if level_callback is not None:
            level_callback(0.0)
        with _PLAYBACK_STATE_LOCK:
            if _ACTIVE_STOP_EVENT is stop_event:
                _ACTIVE_STOP_EVENT = None


def stop_playback() -> None:
    """Dừng ngay audio do sounddevice convenience player đang phát, nếu có."""
    with _PLAYBACK_STATE_LOCK:
        stop_event = _ACTIVE_STOP_EVENT
    if stop_event is not None:
        stop_event.set()
    # Worker đang phát sẽ thấy event trong tối đa một cửa sổ 40 ms rồi nhả device lock.
    with _PLAYBACK_DEVICE_LOCK:
        import sounddevice as sd

        sd.stop(ignore_errors=True)
