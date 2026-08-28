import numpy as np

from aris.vision.grab_gesture import GrabGestureInterpreter


def sample_open_hand() -> np.ndarray:
    """Tạo landmark giả với ngón cái và ngón trỏ cách xa để kiểm thử gesture mới."""
    points = np.zeros((21, 3), dtype=np.float32)
    points[0] = (0.5, 0.8, 0)
    bases = {1: 0.36, 5: 0.42, 9: 0.5, 13: 0.58, 17: 0.66}
    for start, x_value in bases.items():
        for offset in range(4):
            points[start + offset] = (x_value, 0.68 - offset * 0.13, 0)
    points[4, 0] = 0.15
    return points


def test_pinch_requires_confirmation_before_grab() -> None:
    """Kiểm tra pinch phải ổn định đủ số frame mới chuyển sang trạng thái nắm."""
    interpreter = GrabGestureInterpreter(smoothing=1.0, grab_confirm_frames=2)
    open_hand = sample_open_hand()
    interpreter.update(open_hand)
    pinched = open_hand.copy()
    pinched[4] = pinched[8]

    first = interpreter.update(pinched)
    second = interpreter.update(pinched)

    assert not first.grabbed
    assert second.grabbed
    assert second.just_grabbed


def test_drag_then_release_produces_rotation_delta() -> None:
    """Kiểm tra điểm pinch kéo ngang tạo yaw và mở pinch phát trạng thái thả."""
    interpreter = GrabGestureInterpreter(smoothing=1.0, grab_confirm_frames=1)
    open_hand = sample_open_hand()
    interpreter.update(open_hand)
    pinched = open_hand.copy()
    pinched[4] = pinched[8]
    interpreter.update(pinched)

    dragged = pinched.copy()
    dragged[:, 0] += 0.04
    drag_frame = interpreter.update(dragged)
    released = dragged.copy()
    released[4, 0] -= 0.2
    release_frame = interpreter.update(released)

    assert drag_frame.grabbed
    assert drag_frame.yaw > 0
    assert release_frame.just_released
    assert not release_frame.grabbed


def test_open_pinch_distance_still_controls_zoom() -> None:
    """Kiểm tra thay đổi khoảng pinch khi chưa nắm vẫn tạo delta zoom legacy-compatible."""
    interpreter = GrabGestureInterpreter(smoothing=1.0)
    first = sample_open_hand()
    interpreter.update(first)
    second = first.copy()
    second[4, 0] -= 0.04

    frame = interpreter.update(second)

    assert not frame.grabbed
    assert frame.zoom > 0


def test_hybrid_mode_keeps_index_direction_control() -> None:
    """Kiểm tra chế độ grab mặc định vẫn xoay theo hướng ngón trỏ khi chưa nắm model."""
    interpreter = GrabGestureInterpreter(smoothing=1.0)
    pointing = sample_open_hand()
    pointing[8] = (0.74, 0.68, 0)

    frame = interpreter.update(pointing)

    assert frame.pointing
    assert frame.yaw > 0
    assert not frame.grabbed


def test_cancel_releases_active_grab() -> None:
    """Kiểm tra mất tay hoặc tắt camera giải phóng model đang được nắm."""
    interpreter = GrabGestureInterpreter(smoothing=1.0, grab_confirm_frames=1)
    hand = sample_open_hand()
    interpreter.update(hand)
    hand[4] = hand[8]
    interpreter.update(hand)

    canceled = interpreter.cancel()

    assert canceled.just_released
    assert not interpreter.is_grabbed
