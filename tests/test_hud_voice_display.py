from __future__ import annotations

from unittest.mock import Mock

from aris.ai.router import IntentRouter
from aris.core.types import Intent, IntentType
from aris.hardware.protocol import GuardState
from aris.models.catalog import ModelCatalog
from aris.ui.hud_window import HudWindow
from aris.voice.wake_session import WakeSession


def test_spoken_reply_never_reveals_transcript_on_hud() -> None:
    """Kiểm tra lúc TTS bắt đầu, HUD vẫn chỉ có logo thay vì hiện câu đang đọc."""
    hud = Mock()

    HudWindow._on_speech_playback_started(hud, "Nội dung chỉ được đọc.", 2400)

    hud._hide_status.assert_called_once_with()
    hud._show_status.assert_not_called()


def test_failed_speech_does_not_fall_back_to_full_transcript() -> None:
    """Kiểm tra lỗi loa không khiến toàn bộ nội dung riêng tư xuất hiện trên HUD."""
    hud = Mock()

    HudWindow._on_speech_playback_failed(hud, "Nội dung không được hiện.")

    hud._hide_status.assert_called_once_with()
    hud._show_status.assert_not_called()


def test_bare_close_dismisses_focused_research_panel() -> None:
    """Kiểm tra `close` đóng panel đang focus thay vì im lặng vì không có model."""
    hud = Mock()
    hud.research_manager.has_panels = True
    hud.model_manager.has_models = False
    hud._gesture_target = "research"

    HudWindow._handle_close_intent(hud, Intent(IntentType.CLOSE_MODEL))

    hud._close_research.assert_called_once_with()
    hud._close_model.assert_not_called()


def test_named_shutdown_bypasses_sleeping_wake_session() -> None:
    """Kiểm tra lệnh thoát rõ tên luôn hoạt động dù phiên Hey ARIS đã ngủ."""
    hud = Mock()
    hud.guard_state = GuardState.OFF
    hud.music.has_music_context = True
    hud.wake_session = WakeSession(10.0)
    hud.router = IntentRouter(ModelCatalog())

    HudWindow._on_transcript(hud, "Đóng ARIS")

    intent = hud._dispatch_intent.call_args.args[0]
    assert intent.kind is IntentType.EXIT_ARIS
    assert intent.arguments == {"confirmed": True}


def test_wake_phrase_is_removed_before_stop_music_routing() -> None:
    """Kiểm tra `Hey ARIS, dừng nhạc` không dùng tên wake làm target tắt ứng dụng."""
    hud = Mock()
    hud.guard_state = GuardState.OFF
    hud.music.has_music_context = True
    hud.wake_session = WakeSession(10.0)
    hud.router = IntentRouter(ModelCatalog())

    HudWindow._on_transcript(hud, "Hey ARIS, dừng nhạc")

    intent = hud._dispatch_intent.call_args.args[0]
    assert intent.kind is IntentType.STOP_MUSIC
