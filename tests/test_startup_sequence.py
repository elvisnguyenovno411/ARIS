from __future__ import annotations

import wave
from pathlib import Path

from aris.ui.sound_effects import SoundEffectPlayer, reverse_wav_bytes
from aris.ui.startup_sequence import ShutdownSequence, StartupSequence


def _write_silent_wav(path: Path, duration_ms: int = 100) -> None:
    """Tạo WAV PCM nhỏ cho test mà không cần giữ audio fixture trong repository."""
    sample_rate = 8000
    frame_count = round(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def test_startup_sequence_reaches_one_and_finishes(qtbot) -> None:
    """Kiểm tra timeline dùng thời gian thật và kết thúc đúng frame sáng hoàn chỉnh."""
    sequence = StartupSequence(duration_ms=250)
    progress_values: list[float] = []
    sequence.progress_changed.connect(progress_values.append)

    with qtbot.waitSignal(sequence.finished, timeout=1000):
        sequence.start()

    assert progress_values[0] == 0.0
    assert progress_values[-1] == 1.0
    assert all(
        first <= second
        for first, second in zip(progress_values, progress_values[1:], strict=False)
    )
    assert not sequence.is_running


def test_shutdown_sequence_reaches_dark_frame_before_finish(qtbot) -> None:
    """Kiểm tra power-down giảm về 0 rồi mới phát tín hiệu đóng cửa sổ."""
    sequence = ShutdownSequence(duration_ms=300)
    progress_values: list[float] = []
    sequence.progress_changed.connect(progress_values.append)

    with qtbot.waitSignal(sequence.finished, timeout=1200):
        sequence.start()

    assert progress_values[0] == 1.0
    assert progress_values[-1] == 0.0
    assert all(
        first >= second
        for first, second in zip(progress_values, progress_values[1:], strict=False)
    )
    assert not sequence.is_running


def test_sound_effect_player_runs_optional_wav_off_ui_thread(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """Kiểm tra cue hợp lệ phát biên độ còn cue thiếu dùng fallback im lặng."""
    source = tmp_path / "startup.wav"
    _write_silent_wav(source, 120)
    levels: list[float] = []

    def fake_play(payload: bytes, callback) -> None:
        """Giả lập backend audio và phát hai mức năng lượng cho signal HUD."""
        assert payload.startswith(b"RIFF")
        callback(0.7)
        callback(0.0)

    monkeypatch.setattr("aris.ui.sound_effects.play_wav_bytes", fake_play)
    player = SoundEffectPlayer({"startup": source, "missing": tmp_path / "missing.wav"})
    player.level_changed.connect(levels.append)

    with qtbot.waitSignal(player.effect_finished, timeout=1000):
        duration_ms = player.play("startup")

    assert duration_ms == 120
    assert max(levels) == 0.7
    assert player.play("missing") == 0


def test_reverse_wav_bytes_reverses_complete_pcm_frames(tmp_path: Path) -> None:
    """Kiểm tra cue đóng đảo theo frame âm thanh, không đảo byte làm hỏng PCM."""
    source = tmp_path / "cue.wav"
    with wave.open(str(source), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8_000)
        wav_file.writeframes(b"\x01\x00\x02\x00\x03\x00")

    reversed_payload = reverse_wav_bytes(source.read_bytes())

    output = tmp_path / "reversed.wav"
    output.write_bytes(reversed_payload)
    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.readframes(3) == b"\x03\x00\x02\x00\x01\x00"
