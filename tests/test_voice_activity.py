from aris.voice.voice_activity import (
    ExternalAudioVoiceGate,
    VoiceActivityDetector,
    VoiceActivityEvent,
)


def test_background_noise_does_not_start_listening() -> None:
    """Kiểm tra tiếng nền nhỏ chỉ hiệu chỉnh noise floor và không mở bản ghi."""
    detector = VoiceActivityDetector()

    assert detector.feed(0.003, 1.0) is VoiceActivityEvent.NONE
    assert detector.feed(0.004, 1.064) is VoiceActivityEvent.NONE
    assert not detector.is_speaking


def test_two_speech_blocks_start_automatic_listening() -> None:
    """Kiểm tra hai block giọng liên tục đủ để VAD bắt đầu câu không cần thao tác."""
    detector = VoiceActivityDetector()

    assert detector.feed(0.06, 2.0) is VoiceActivityEvent.NONE
    assert detector.feed(0.07, 2.064) is VoiceActivityEvent.START
    assert detector.is_speaking


def test_external_gate_can_confirm_vad_without_counting_voice_twice() -> None:
    """Kiểm tra voice gate đã xác nhận có thể mở câu ngay và VAD vẫn tự dừng đúng hạn."""
    detector = VoiceActivityDetector()

    detector.confirm_speech(2.0)

    assert detector.is_speaking
    assert detector.feed(0.002, 2.1) is VoiceActivityEvent.NONE
    assert detector.feed(0.002, 2.73) is VoiceActivityEvent.STOP
    assert not detector.is_speaking


def test_silence_stops_utterance_after_hold_time() -> None:
    """Kiểm tra VAD chỉ kết thúc sau im lặng liên tục để không cắt giữa câu."""
    detector = VoiceActivityDetector()
    detector.feed(0.06, 3.0)
    detector.feed(0.07, 3.064)

    assert detector.feed(0.002, 3.2) is VoiceActivityEvent.NONE
    assert detector.feed(0.002, 3.79) is VoiceActivityEvent.NONE
    assert detector.feed(0.002, 3.84) is VoiceActivityEvent.STOP
    assert not detector.is_speaking


def test_speech_resets_pending_silence() -> None:
    """Kiểm tra một âm tiết mới hủy bộ đếm im lặng để giữ nguyên cả câu nói."""
    detector = VoiceActivityDetector()
    detector.feed(0.06, 5.0)
    detector.feed(0.07, 5.064)
    detector.feed(0.002, 5.2)

    assert detector.feed(0.05, 5.7) is VoiceActivityEvent.NONE
    assert detector.feed(0.002, 6.0) is VoiceActivityEvent.NONE
    assert detector.feed(0.002, 6.65) is VoiceActivityEvent.STOP


def test_external_audio_gate_suppresses_music_but_passes_near_voice() -> None:
    """Kiểm tra echo nhạc bị chặn còn giọng gần mic vẫn mở đường cho VAD."""
    gate = ExternalAudioVoiceGate()
    gate.reset(10.0)

    assert gate.feed(0.08, 0.35, 10.10) == 0.0
    assert gate.feed(0.08, 0.35, 10.30) == 0.0
    assert gate.feed(0.08, 0.35, 10.50) == 0.0
    assert gate.feed(0.27, 0.35, 10.60) == 0.0
    assert gate.candidate_active
    assert gate.feed(0.28, 0.35, 10.66) > 0.2


def test_external_audio_gate_holds_voice_across_short_syllable_gap() -> None:
    """Kiểm tra khoảng nghỉ ngắn trong Hey ARIS không bị nhạc đóng gate giữa câu."""
    gate = ExternalAudioVoiceGate()
    gate.reset(20.0)
    gate.feed(0.06, 0.3, 20.4)
    gate.feed(0.24, 0.3, 20.5)
    gate.feed(0.25, 0.3, 20.56)

    assert gate.feed(0.02, 0.3, 20.8) == 0.02
    assert gate.feed(0.02, 0.3, 21.4) == 0.0


def test_external_audio_gate_ignores_modulated_echo_without_voice() -> None:
    """Kiểm tra beat nhạc thay đổi vẫn không đi qua gate hoặc tạo ứng viên giọng giả."""
    gate = ExternalAudioVoiceGate()
    gate.reset(30.0)

    samples = (
        (0.05, 0.20, 30.10),
        (0.09, 0.42, 30.24),
        (0.06, 0.25, 30.38),
        (0.12, 0.55, 30.52),
        (0.07, 0.30, 30.66),
    )

    for mic, playback, timestamp in samples:
        assert gate.feed(mic, playback, timestamp) == 0.0
        assert not gate.candidate_active
