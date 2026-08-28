from aris.core.shutdown_guard import ShutdownDecision, ShutdownGuard


def test_shutdown_during_music_requires_explicit_confirmation() -> None:
    """Kiểm tra transcript tắt nhầm không thể đóng ARIS khi nhạc còn context."""
    guard = ShutdownGuard(confirmation_seconds=7.0)

    assert guard.evaluate(
        confirmed=False,
        music_context=True,
        timestamp=10.0,
    ) is ShutdownDecision.CONFIRM
    assert guard.evaluate(
        confirmed=True,
        music_context=True,
        timestamp=15.0,
    ) is ShutdownDecision.ALLOW


def test_shutdown_without_music_keeps_single_command_behavior() -> None:
    """Kiểm tra ngoài chế độ nhạc, lệnh tắt ARIS vẫn đóng HUD ngay như trước."""
    guard = ShutdownGuard()

    assert guard.evaluate(
        confirmed=False,
        music_context=False,
        timestamp=20.0,
    ) is ShutdownDecision.ALLOW


def test_explicit_named_shutdown_bypasses_music_confirmation_round_trip() -> None:
    """Kiểm tra câu gọi rõ ARIS tắt ngay cả khi nhạc đang phát, không bắt nói hai lần."""
    guard = ShutdownGuard()

    assert guard.evaluate(
        confirmed=True,
        music_context=True,
        timestamp=30.0,
    ) is ShutdownDecision.ALLOW
