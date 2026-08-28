from __future__ import annotations

import io
import sys
import threading
import wave
from types import SimpleNamespace

import numpy as np

from aris.voice.audio_playback import decode_wav_bytes, play_wav_bytes, stop_playback


def make_test_wav() -> bytes:
    """Tạo WAV PCM nhỏ trong RAM để kiểm tra giải mã mà không lưu audio xuống đĩa."""
    samples = np.array((-32768, -4096, 0, 4096, 32767), dtype="<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24_000)
        wav_file.writeframes(samples.tobytes())
    return buffer.getvalue()


def test_decode_wav_bytes_returns_normalized_pcm() -> None:
    """Đảm bảo WAV TTS chuẩn được giải mã đúng sample rate và biên độ float32."""
    samples, sample_rate = decode_wav_bytes(make_test_wav())

    assert sample_rate == 24_000
    assert samples.dtype == np.float32
    assert samples.shape == (5,)
    assert samples[0] == -1.0
    assert 0.99 < samples[-1] <= 1.0


def test_play_wav_bytes_uses_sounddevice_without_windows_sound(monkeypatch) -> None:
    """Đảm bảo audio RAM đi thẳng tới sounddevice và chờ phát xong."""
    captured: dict[str, object] = {}
    fake_sounddevice = SimpleNamespace(
        play=lambda data, rate, blocking: captured.update(
            data=data,
            rate=rate,
            blocking=blocking,
        ),
        wait=lambda: None,
        stop=lambda ignore_errors: captured.update(stopped=ignore_errors),
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sounddevice)

    play_wav_bytes(make_test_wav())

    assert captured["rate"] == 24_000
    assert captured["blocking"] is False
    assert captured["stopped"] is True
    assert isinstance(captured["data"], np.ndarray)


def test_play_wav_bytes_reports_speech_envelope(monkeypatch) -> None:
    """Đảm bảo bộ phát gửi mức WAV thật cho animation và kết thúc bằng mức 0."""
    captured: dict[str, object] = {}
    fake_sounddevice = SimpleNamespace(
        play=lambda data, rate, blocking: captured.update(
            data=data,
            rate=rate,
            blocking=blocking,
        ),
        wait=lambda: None,
        stop=lambda ignore_errors: captured.update(stopped=ignore_errors),
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sounddevice)
    levels: list[float] = []

    play_wav_bytes(make_test_wav(), levels.append)

    assert captured["blocking"] is False
    assert any(level > 0.0 for level in levels)
    assert levels[-1] == 0.0


def test_concurrent_playback_never_enters_sounddevice_twice(monkeypatch) -> None:
    """Kiểm tra cue và TTS đồng thời vẫn chỉ có một owner chạm vào PortAudio/CFFI."""
    lock = threading.Lock()
    active = 0
    maximum_active = 0

    def fake_play(_data, _rate, blocking) -> None:
        """Ghi số playback đang hoạt động trong backend giả."""
        nonlocal active, maximum_active
        assert blocking is False
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)

    def fake_stop(ignore_errors) -> None:
        """Kết thúc playback giả mà không để bộ đếm âm."""
        nonlocal active
        assert ignore_errors is True
        with lock:
            active = max(0, active - 1)

    fake_sounddevice = SimpleNamespace(
        play=fake_play,
        wait=lambda: None,
        stop=fake_stop,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sounddevice)
    payload = make_test_wav()
    workers = [threading.Thread(target=play_wav_bytes, args=(payload,)) for _ in range(2)]

    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=2.0)

    assert all(not worker.is_alive() for worker in workers)
    assert maximum_active == 1


def test_stop_playback_interrupts_sounddevice_player(monkeypatch) -> None:
    """Đảm bảo barge-in gọi đúng stop và không phát sinh lỗi khi audio vừa kết thúc."""
    captured: dict[str, object] = {}
    fake_sounddevice = SimpleNamespace(
        stop=lambda ignore_errors: captured.update(ignore_errors=ignore_errors)
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sounddevice)

    stop_playback()

    assert captured == {"ignore_errors": True}
