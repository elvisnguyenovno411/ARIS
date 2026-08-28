from aris.ui.hud_state import HudMode, HudStateMachine


def test_hud_state_model_round_trip() -> None:
    """Kiểm tra model active luôn quay về logo khi nhận lệnh đóng."""
    state = HudStateMachine()

    assert state.show_model("rasengan") is HudMode.MODEL
    assert state.active_model == "rasengan"
    assert state.close_model() is HudMode.IDLE
    assert state.active_model is None


def test_hud_state_keeps_multiple_models_and_selects_previous_after_close() -> None:
    """Kiểm tra đóng model đang chọn không làm mất các hologram khác trên HUD."""
    state = HudStateMachine()
    state.show_model("rasengan")
    state.show_model("minato_kunai")

    assert state.open_models == ["rasengan", "minato_kunai"]
    assert state.close_model("minato_kunai") is HudMode.MODEL
    assert state.open_models == ["rasengan"]
    assert state.active_model == "rasengan"


def test_hud_state_can_close_all_floating_models() -> None:
    """Kiểm tra lệnh kết thúc phiên xóa mọi model nổi và trả logo về idle."""
    state = HudStateMachine()
    state.show_model("rasengan")
    state.show_model("iron_man_mask")

    assert state.close_all_models() is HudMode.IDLE
    assert state.open_models == []
    assert state.active_model is None


def test_listening_can_start_while_model_is_remembered() -> None:
    """Kiểm tra nghe lệnh end không làm mất model trước khi transcript hoàn tất."""
    state = HudStateMachine()
    state.show_model("minato_kunai")

    assert state.begin_listening() is HudMode.LISTENING
    assert state.active_model == "minato_kunai"


def test_speaking_mode_preserves_the_active_model() -> None:
    """Kiểm tra animation phát giọng không làm mất model đang được theo dõi."""
    state = HudStateMachine()
    state.show_model("rasengan")

    assert state.begin_speaking() is HudMode.SPEAKING
    assert state.active_model == "rasengan"
