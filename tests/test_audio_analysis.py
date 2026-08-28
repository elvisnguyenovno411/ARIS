from __future__ import annotations

import numpy as np

from aris.voice.audio_analysis import AudioBlockAnalyzer


def test_audio_analyzer_returns_level_peak_and_24_bands() -> None:
    """Kiểm tra analyzer dùng chung tạo đủ dữ liệu VAD và spectrum từ một FFT."""
    timeline = np.arange(1024, dtype=np.float32) / 16_000
    block = (0.08 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)
    analysis = AudioBlockAnalyzer().analyze(block)

    assert analysis.rms > 0.04
    assert analysis.peak > analysis.rms
    assert len(analysis.bands) == 24
    assert max(analysis.bands) > 0.0


def test_audio_analyzer_handles_short_silence_without_false_energy() -> None:
    """Kiểm tra block rỗng trả mức 0 và đúng số band mà không phát sinh NaN."""
    analysis = AudioBlockAnalyzer().analyze(np.zeros(4, dtype=np.float32))

    assert analysis.rms == 0.0
    assert analysis.peak == 0.0
    assert analysis.bands == (0.0,) * 24
