import numpy as np
import pytest

from aris.vision.hand_geometry import GestureInterpreter, build_hand_profile


def sample_landmarks() -> np.ndarray:
    """Tạo landmark bàn tay giả định đủ ổn định cho kiểm thử hình học."""
    points = np.zeros((21, 3), dtype=np.float32)
    points[0] = (0.5, 0.8, 0)
    bases = {1: 0.36, 5: 0.42, 9: 0.5, 13: 0.58, 17: 0.66}
    for start, x_value in bases.items():
        for offset in range(4):
            points[start + offset] = (x_value, 0.68 - offset * 0.13, 0)
    return points


def test_profile_is_relative_and_serializable() -> None:
    """Kiểm tra profile dùng tỷ lệ tương đối và có đủ năm ngón."""
    profile = build_hand_profile(sample_landmarks(), "Left")
    assert profile.handedness == "Left"
    assert profile.palm_width == 1.0
    assert set(profile.finger_lengths) == {"thumb", "index", "middle", "ring", "pinky"}
    assert profile.to_dict()["handedness"] == "Left"


def test_gesture_interpreter_produces_zoom_delta() -> None:
    """Kiểm tra thay đổi khoảng cách chụm tạo ra lệnh zoom có giới hạn."""
    interpreter = GestureInterpreter(smoothing=1.0)
    first = sample_landmarks()
    interpreter.update(first)
    second = first.copy()
    second[4, 0] -= 0.05
    delta = interpreter.update(second)
    assert delta.zoom > 0


def test_gesture_interpreter_maps_index_direction_to_rotation() -> None:
    """Kiểm tra hướng tip so với MCP tạo dấu yaw/pitch đúng cho bốn hướng chính."""
    base = sample_landmarks()
    right = base.copy()
    right[8] = (0.74, 0.68, 0)
    left = base.copy()
    left[8] = (0.12, 0.68, 0)
    up = base.copy()
    up[8] = (0.42, 0.2, 0)
    down = base.copy()
    down[8] = (0.42, 0.96, 0)

    assert GestureInterpreter(smoothing=1.0).update(right).yaw > 0
    assert GestureInterpreter(smoothing=1.0).update(left).yaw < 0
    assert GestureInterpreter(smoothing=1.0).update(up).pitch > 0
    assert GestureInterpreter(smoothing=1.0).update(down).pitch < 0


def test_gesture_smoothing_approaches_target_gradually() -> None:
    """Kiểm tra EMA tiến dần tới vận tốc đích thay vì tạo bước nhảy ngay frame đầu."""
    interpreter = GestureInterpreter(smoothing=0.25)
    right = sample_landmarks()
    right[8] = (0.74, 0.68, 0)

    first = interpreter.update(right)
    second = interpreter.update(right)

    assert 0 < first.yaw < second.yaw < 2.8


def test_direction_dead_zone_rejects_short_noisy_vector() -> None:
    """Kiểm tra vector ngón trỏ quá ngắn không tạo xoay do landmark rung."""
    interpreter = GestureInterpreter(smoothing=1.0)
    noisy = sample_landmarks()
    noisy[8] = noisy[5] + np.array((0.01, 0.0, 0.0), dtype=np.float32)

    delta = interpreter.update(noisy)

    assert delta.yaw == 0
    assert delta.pitch == 0


def test_zoom_dead_zone_accumulates_small_changes() -> None:
    """Kiểm tra jitter nhỏ bị chặn nhưng thay đổi tích lũy đủ lớn vẫn tạo zoom."""
    interpreter = GestureInterpreter(smoothing=1.0, zoom_dead_zone=0.02)
    first = sample_landmarks()
    interpreter.update(first)
    tiny = first.copy()
    tiny[4, 0] -= 0.002
    larger = first.copy()
    larger[4, 0] -= 0.02

    assert interpreter.update(tiny).zoom == 0
    assert interpreter.update(larger).zoom > 0


def test_zoom_delta_is_clamped() -> None:
    """Kiểm tra landmark pinch bất thường không tạo delta zoom vượt giới hạn an toàn."""
    interpreter = GestureInterpreter(smoothing=1.0)
    first = sample_landmarks()
    interpreter.update(first)
    extreme = first.copy()
    extreme[4, 0] -= 2.0

    assert interpreter.update(extreme).zoom == 0.18


def test_gesture_interpreter_reset_prevents_reentry_jump() -> None:
    """Kiểm tra mất tay rồi nhận lại không tạo cú nhảy camera từ landmark cũ."""
    interpreter = GestureInterpreter(smoothing=1.0)
    interpreter.update(sample_landmarks())
    interpreter.reset()

    returned = sample_landmarks()
    returned[:, 0] += 0.15
    delta = interpreter.update(returned)
    fresh_delta = GestureInterpreter(smoothing=1.0).update(returned)

    assert delta == fresh_delta
    assert delta.zoom == 0


def test_hand_profile_rejects_incomplete_landmarks() -> None:
    """Kiểm tra scan không thể tạo profile nếu MediaPipe không cung cấp đủ 21 landmark."""
    with pytest.raises(ValueError, match="Expected 21"):
        build_hand_profile(np.zeros((20, 3), dtype=np.float32))
