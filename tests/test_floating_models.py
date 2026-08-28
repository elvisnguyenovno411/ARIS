from PySide6.QtCore import QPoint, QSize

from aris.ui.floating_models import (
    FLOATING_FRAME_SIZE,
    FLOATING_VIEW_SIZE,
    centered_floating_position,
    clamp_floating_position,
)


def test_floating_position_stays_inside_hud_edges() -> None:
    """Kiểm tra kéo quá xa vẫn giữ toàn bộ hologram bên trong HUD."""
    container = QSize(1100, 700)
    hologram = QSize(340, 340)

    assert clamp_floating_position(QPoint(-500, -200), container, hologram) == QPoint(
        16, 16
    )
    assert clamp_floating_position(QPoint(5000, 4000), container, hologram) == QPoint(
        744, 344
    )


def test_floating_position_preserves_valid_drag_target() -> None:
    """Kiểm tra vị trí hợp lệ không bị manager tự thay đổi ngoài ý người dùng."""
    position = QPoint(220, 180)

    assert clamp_floating_position(
        position,
        QSize(1480, 900),
        QSize(340, 340),
    ) == position


def test_new_hologram_is_centered_over_aris_core() -> None:
    """Kiểm tra model mới có tâm trùng tâm HUD trước khi nhận cử chỉ năm ngón."""
    assert centered_floating_position(QSize(1480, 900), QSize(340, 340)) == QPoint(
        570,
        280,
    )


def test_overscan_view_keeps_only_the_control_frame_inside_hud() -> None:
    """Kiểm tra model được tràn khỏi khung chọn trong khi khung 340 px vẫn không mất khỏi HUD."""
    widget = QSize(FLOATING_VIEW_SIZE, FLOATING_VIEW_SIZE)
    anchor = QSize(FLOATING_FRAME_SIZE, FLOATING_FRAME_SIZE)

    assert clamp_floating_position(
        QPoint(-500, -500), QSize(1100, 700), widget, anchor_size=anchor
    ) == QPoint(-164, -164)
    assert clamp_floating_position(
        QPoint(5000, 5000), QSize(1100, 700), widget, anchor_size=anchor
    ) == QPoint(564, 164)
