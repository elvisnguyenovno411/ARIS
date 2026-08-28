import numpy as np

from aris.vision.spatial_gesture import (
    SpatialGestureInterpreter,
    SpatialGestureMode,
)


def sample_open_hand() -> np.ndarray:
    """Tạo landmark tay mở với năm đầu ngón tách nhau cho kiểm thử spatial gesture."""
    points = np.zeros((21, 3), dtype=np.float32)
    points[0] = (0.5, 0.8, 0)
    bases = {1: 0.36, 5: 0.42, 9: 0.5, 13: 0.58, 17: 0.66}
    for start, x_value in bases.items():
        for offset in range(4):
            points[start + offset] = (x_value, 0.68 - offset * 0.13, 0)
    points[4, 0] = 0.15
    return points


def test_open_hand_requires_confirmation_before_move_mode() -> None:
    """Kiểm tra tay mở phải ổn định đủ frame mới được quyền di chuyển hologram."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=2)
    hand = sample_open_hand()

    first = interpreter.update(hand)
    second = interpreter.update(hand)

    assert first.mode is SpatialGestureMode.NEUTRAL
    assert second.mode is SpatialGestureMode.MOVE
    assert second.just_started


def test_open_hand_movement_produces_only_translation() -> None:
    """Kiểm tra năm ngón di chuyển model nhưng không đồng thời xoay hoặc zoom."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    hand = sample_open_hand()
    interpreter.update(hand)
    moved = hand.copy()
    moved[:, 0] += 0.04

    frame = interpreter.update(moved)

    assert frame.mode is SpatialGestureMode.MOVE
    assert frame.move_x > 0
    assert frame.yaw == 0
    assert frame.zoom == 0


def test_far_open_hand_keeps_move_classification() -> None:
    """Kiểm tra bàn tay nhỏ ở xa vẫn được nhận nhờ tỷ lệ hình học không phụ thuộc scale."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    hand = sample_open_hand()
    center = hand[:, :2].mean(axis=0)
    far_hand = hand.copy()
    far_hand[:, :2] = center + (far_hand[:, :2] - center) * 0.42

    frame = interpreter.update(far_hand)

    assert frame.mode is SpatialGestureMode.MOVE
    assert frame.just_started


def test_open_hand_tolerates_one_uncertain_fingertip() -> None:
    """Kiểm tra một đầu ngón bị che nhẹ không làm mất MOVE khi phần còn lại rõ ràng."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    hand = sample_open_hand()
    hand[12] = hand[10]

    frame = interpreter.update(hand)

    assert frame.mode is SpatialGestureMode.MOVE


def test_far_hand_receives_extra_motion_gain() -> None:
    """Kiểm tra tay ở xa vẫn điều khiển linh hoạt nhờ gain tăng theo palm nhỏ."""
    near_interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    far_interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    near = sample_open_hand()
    center = near[:, :2].mean(axis=0)
    far = near.copy()
    far[:, :2] = center + (far[:, :2] - center) * 0.42
    near_interpreter.update(near)
    far_interpreter.update(far)
    near_moved = near.copy()
    far_moved = far.copy()
    near_moved[:, 0] += 0.02
    far_moved[:, 0] += 0.02

    near_frame = near_interpreter.update(near_moved)
    far_frame = far_interpreter.update(far_moved)

    assert far_frame.move_x > near_frame.move_x


def test_pinch_drag_rotates_without_translating_widget() -> None:
    """Kiểm tra pinch kéo ngang chỉ tạo yaw và không tạo delta MOVE."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    pinched = sample_open_hand()
    pinched[4] = pinched[8]
    interpreter.update(pinched)
    dragged = pinched.copy()
    dragged[:, 0] += 0.04

    frame = interpreter.update(dragged)

    assert frame.mode is SpatialGestureMode.TRANSFORM
    assert frame.yaw > 0
    assert frame.pitch == 0
    assert frame.move_x == 0


def test_vertical_pinch_movement_does_not_tilt_model() -> None:
    """Kiểm tra pinch dọc tạo delta cuộn nhưng không làm model nghiêng."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    pinched = sample_open_hand()
    pinched[4] = pinched[8]
    interpreter.update(pinched)
    moved_up = pinched.copy()
    moved_up[:, 1] -= 0.06

    frame = interpreter.update(moved_up)

    assert frame.mode is SpatialGestureMode.TRANSFORM
    assert frame.move_y < 0
    assert frame.yaw == 0
    assert frame.pitch == 0


def test_pinched_hand_depth_change_does_not_control_zoom() -> None:
    """Kiểm tra đưa cả tay gần camera không còn vô tình phóng to model."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    pinched = sample_open_hand()
    pinched[4] = pinched[8]
    interpreter.update(pinched)
    center = pinched[[0, 5, 9, 13, 17], :2].mean(axis=0)
    closer = pinched.copy()
    closer[:, :2] = center + (closer[:, :2] - center) * 1.12
    closer[4] = closer[8]

    frame = interpreter.update(closer)

    assert frame.mode is SpatialGestureMode.TRANSFORM
    assert frame.zoom == 0
    assert frame.move_x == 0


def test_thumb_index_spread_never_zooms_in_transform_mode() -> None:
    """Kiểm tra tách ngón chỉ giữ khóa xoay và không tự thay đổi kích thước model."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    pinched = sample_open_hand()
    pinched[4] = pinched[8]
    interpreter.update(pinched)
    spread = pinched.copy()
    spread[4, 0] -= 0.08

    frame = interpreter.update(spread)

    assert frame.mode is SpatialGestureMode.TRANSFORM
    assert frame.zoom == 0
    assert frame.move_x == 0


def test_thumb_index_close_never_zooms_out() -> None:
    """Kiểm tra chụm hai đầu ngón không thu nhỏ vì zoom chỉ do lệnh ARIS điều khiển."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    hand = sample_open_hand()
    hand[4] = hand[8]
    interpreter.update(hand)
    spread = hand.copy()
    spread[4, 0] -= 0.08
    interpreter.update(spread)
    closed = spread.copy()
    closed[4] = closed[8]

    frame = interpreter.update(closed)

    assert frame.mode is SpatialGestureMode.TRANSFORM
    assert frame.zoom == 0


def test_mode_change_requires_release_frames() -> None:
    """Kiểm tra một frame pinch nhiễu không đổi MOVE thành TRANSFORM tức thì."""
    interpreter = SpatialGestureInterpreter(
        smoothing=1.0,
        confirm_frames=1,
        release_frames=2,
    )
    open_hand = sample_open_hand()
    interpreter.update(open_hand)
    pinched = open_hand.copy()
    pinched[4] = pinched[8]

    noisy = interpreter.update(pinched)

    assert noisy.mode is SpatialGestureMode.MOVE
    assert not noisy.just_released


def test_cancel_releases_locked_spatial_mode() -> None:
    """Kiểm tra mất tay hủy mode đang khóa để model không tiếp tục tự di chuyển."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    interpreter.update(sample_open_hand())

    canceled = interpreter.cancel()

    assert canceled.just_released
    assert interpreter.mode is SpatialGestureMode.NEUTRAL


def test_short_detection_dropout_keeps_locked_mode() -> None:
    """Kiểm tra vài frame mất tay ở khoảng cách xa không buộc người dùng tạo gesture lại."""
    interpreter = SpatialGestureInterpreter(
        smoothing=1.0,
        confirm_frames=1,
        missing_grace_frames=2,
    )
    interpreter.update(sample_open_hand())

    first_miss = interpreter.miss()
    second_miss = interpreter.miss()
    released = interpreter.miss()

    assert first_miss.mode is SpatialGestureMode.MOVE
    assert second_miss.mode is SpatialGestureMode.MOVE
    assert released.just_released


def test_reacquired_hand_does_not_jump_hologram() -> None:
    """Kiểm tra tay bắt lại sau dropout không áp dụng quãng dịch bị mất vào model."""
    interpreter = SpatialGestureInterpreter(smoothing=1.0, confirm_frames=1)
    hand = sample_open_hand()
    interpreter.update(hand)
    interpreter.miss()
    reacquired = hand.copy()
    reacquired[:, 0] += 0.12

    frame = interpreter.update(reacquired)

    assert frame.mode is SpatialGestureMode.MOVE
    assert frame.move_x == 0
    assert frame.move_y == 0
