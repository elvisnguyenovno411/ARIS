from __future__ import annotations

from aris.ui.hud_state import HudMode
from aris.ui.hud_widgets import AudioCoreWidget, TechBackground


def test_speaking_energy_fades_smoothly_into_idle(qtbot) -> None:
    """Đảm bảo kết thúc câu nói không làm lõi co nhỏ đột ngột trong một frame."""
    core = AudioCoreWidget(animation_fps=60)
    qtbot.addWidget(core)
    core.set_animation_active(False)
    core.set_mode(HudMode.SPEAKING)
    for _ in range(90):
        core._animate()
    speaking_energy = core.visual_energy

    core.set_mode(HudMode.IDLE)
    core._animate()

    assert speaking_energy > 0.5
    assert 0.0 < speaking_energy - core.visual_energy < 0.03


def test_idle_core_keeps_a_visible_energy_floor(qtbot) -> None:
    """Đảm bảo logo idle vẫn thở nhẹ và không tụt về lõi tĩnh gần bằng không."""
    core = AudioCoreWidget(animation_fps=60)
    qtbot.addWidget(core)
    core.set_animation_active(False)
    core.set_mode(HudMode.IDLE)
    for _ in range(120):
        core._animate()

    assert core.visual_energy >= 0.25


def test_core_animation_phase_never_wraps_back_to_zero(qtbot) -> None:
    """Đảm bảo quỹ đạo lõi tiếp tục vô hạn thay vì giật lại sau một chu kỳ ngắn."""
    core = AudioCoreWidget(animation_fps=60)
    qtbot.addWidget(core)
    core.set_animation_active(False)
    core._phase = 0.999

    core._animate()

    assert core._phase > 1.0


def test_technology_background_phase_is_also_continuous(qtbot) -> None:
    """Đảm bảo các node nền không cùng lúc nhảy về vị trí đầu sau một chu kỳ."""
    background = TechBackground()
    qtbot.addWidget(background)
    background.set_animation_active(False)
    background._phase = 0.999

    background._advance()

    assert background._phase > 1.0


def test_outer_monitor_dash_offset_does_not_jump_at_cycle_boundary(qtbot) -> None:
    """Đảm bảo vòng tím đi xuyên mốc pha 1.0 bằng một bước nhỏ thay vì giật về đầu."""
    core = AudioCoreWidget(animation_fps=60)
    qtbot.addWidget(core)
    core.set_animation_active(False)
    core._phase = 0.999
    before = core.monitor_dash_offset

    core._animate()

    assert core.monitor_dash_offset < before
    assert abs(core.monitor_dash_offset - before) < 1.0


def test_spoken_audio_level_drives_core_energy(qtbot) -> None:
    """Đảm bảo biên độ giọng ARIS được làm mượt vào animation thay vì chỉ dùng micro."""
    core = AudioCoreWidget(animation_fps=60)
    qtbot.addWidget(core)
    core.set_animation_active(False)
    core.set_mode(HudMode.SPEAKING)
    core.set_speech_level(1.0)

    for _ in range(20):
        core._animate()

    assert core._speech_level > 0.9
    assert core.visual_energy > 0.5


def test_startup_progress_is_clamped_for_core_and_background(qtbot) -> None:
    """Đảm bảo timeline lỗi không thể tạo alpha hoặc bán kính ngoài phạm vi hợp lệ."""
    core = AudioCoreWidget(animation_fps=60)
    background = TechBackground()
    qtbot.addWidget(core)
    qtbot.addWidget(background)
    core.set_animation_active(False)
    background.set_animation_active(False)

    core.set_startup_progress(-3.0)
    background.set_startup_progress(4.0)

    assert core.startup_progress == 0.0
    assert background.startup_progress == 1.0


def test_sound_effect_level_drives_core_without_speaking_mode(qtbot) -> None:
    """Đảm bảo cue materialize làm lõi sáng nhưng không đổi state thành ARIS đang nói."""
    core = AudioCoreWidget(animation_fps=60)
    qtbot.addWidget(core)
    core.set_animation_active(False)
    core.set_mode(HudMode.MODEL)
    core.set_effect_level(1.0)

    for _ in range(12):
        core._animate()

    assert core._effect_level > 0.9
    assert core._speaking_blend == 0.0


def test_music_beat_drives_core_and_purple_background(qtbot) -> None:
    """Đảm bảo trạng thái nhạc làm lõi nảy và nền chuyển tím bằng nội suy."""
    core = AudioCoreWidget(animation_fps=60)
    background = TechBackground()
    qtbot.addWidget(core)
    qtbot.addWidget(background)
    core.set_animation_active(False)
    background.set_animation_active(False)

    core.set_music_active(True)
    background.set_music_active(True)
    core.set_music_level(1.0)
    background.set_music_level(1.0)
    for _ in range(16):
        core._animate()
        background._advance()

    assert core._music_level > 0.9
    assert core.visual_energy > 0.5
    assert background._music_blend > 0.7

    core.set_music_active(False)
    background.set_music_active(False)
    for _ in range(28):
        core._animate()
        background._advance()

    assert core._music_level < 0.05
    assert background._music_blend < 0.15
