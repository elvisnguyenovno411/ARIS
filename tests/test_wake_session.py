from aris.voice.wake_session import WakeAction, WakeSession


def test_sleeping_session_ignores_commands_without_wake_phrase() -> None:
    """Đảm bảo ARIS đang ngủ không thực thi câu nói thông thường."""
    session = WakeSession(10.0)

    decision = session.process("Mở Chrome", 5.0)

    assert decision.action is WakeAction.IGNORE


def test_wake_phrase_can_activate_and_include_a_command() -> None:
    """Kiểm tra một câu `Hey ARIS` vừa đánh thức vừa chuyển lệnh còn lại cho router."""
    session = WakeSession(10.0)

    decision = session.process("Hey ARIS, mở Chrome", 8.0)

    assert decision.action is WakeAction.COMMAND
    assert decision.command == "mở Chrome"
    assert session.is_awake(17.9)


def test_common_wake_transcription_variants_are_supported() -> None:
    """Kiểm tra Iris/Eris do ASR nghe nhầm vẫn đánh thức nhưng không nhận giữa câu."""
    for phrase in (
        "Hey Iris",
        "Hey Eris",
        "Hay ARIS",
        "Hi ARIS",
        "Hê Ari",
        "Hey Ares",
        "ARIS",
        "HeyARIS",
        "Hey Artist",
        "Hey Harris",
        "Hey a risk",
        "Hey RS",
    ):
        assert WakeSession().process(phrase, 1.0).action is WakeAction.WAKE

    assert WakeSession().process("Tôi nói hey ARIS", 1.0).action is WakeAction.IGNORE


def test_session_expires_after_ten_seconds_without_new_transcript() -> None:
    """Đảm bảo hết 10 giây im lặng thì câu tiếp theo lại cần wake phrase."""
    session = WakeSession(10.0)
    session.process("Hey ARIS", 20.0)
    assert session.process("Mở Chrome", 29.9).action is WakeAction.COMMAND

    assert session.process("Mở Discord", 40.0).action is WakeAction.IGNORE


def test_confirmed_voice_start_extends_only_an_awake_session() -> None:
    """Kiểm tra VAD gia hạn timeout đang mở nhưng tiếng nói thường không tự đánh thức ARIS."""
    session = WakeSession(10.0)
    assert session.touch(1.0) is False

    session.process("Hey ARIS", 5.0)
    assert session.touch(14.0) is True
    assert session.is_awake(23.9)
