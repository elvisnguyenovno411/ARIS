from __future__ import annotations

from aris.voice.barge_in import BargeInDetector


def test_speaker_echo_does_not_interrupt_during_or_after_guard() -> None:
    """Đảm bảo mức tiếng vọng ổn định từ loa không khiến ARIS tự cắt câu trả lời."""
    detector = BargeInDetector()
    detector.reset(10.0)

    for index in range(14):
        assert detector.feed(0.028, 10.0 + index * 0.064) is False


def test_three_strong_voice_blocks_interrupt_playback() -> None:
    """Đảm bảo khoảng 190 ms giọng rõ sau guard đủ để dừng audio đang phát."""
    detector = BargeInDetector()
    detector.reset(20.0)
    for index in range(12):
        detector.feed(0.02, 20.0 + index * 0.064)

    assert detector.feed(0.1, 20.8) is False
    assert detector.feed(0.11, 20.864) is False
    assert detector.feed(0.1, 20.928) is True
    assert detector.feed(0.12, 20.992) is False


def test_short_transient_does_not_interrupt_playback() -> None:
    """Đảm bảo tiếng click/vỗ đơn lẻ không bị nhầm thành người dùng nói cắt ngang."""
    detector = BargeInDetector()
    detector.reset(30.0)
    for index in range(12):
        detector.feed(0.018, 30.0 + index * 0.064)

    assert detector.feed(0.14, 30.8) is False
    assert detector.feed(0.018, 30.864) is False
    assert detector.feed(0.018, 30.928) is False


def test_moderate_user_voice_interrupts_after_echo_baseline() -> None:
    """Xác nhận giọng nói vừa phải vẫn ngắt được sau khi đã học mức tiếng loa."""
    detector = BargeInDetector()
    detector.reset(40.0)
    for index in range(6):
        assert detector.feed(0.020, 40.0 + index * 0.064) is False

    assert detector.feed(0.065, 40.40) is False
    assert detector.feed(0.065, 40.464) is False
    assert detector.feed(0.065, 40.528) is True


def test_sudden_speaker_peak_is_learned_instead_of_interrupting() -> None:
    """Xác nhận đoạn TTS đột ngột lớn hơn không bị nhầm thành giọng cắt ngang."""
    detector = BargeInDetector()
    detector.reset(50.0)
    for index in range(6):
        assert detector.feed(0.030, 50.0 + index * 0.064) is False

    assert detector.feed(0.060, 50.40) is False
    assert detector.feed(0.060, 50.464) is False
    assert detector.feed(0.060, 50.528) is False
