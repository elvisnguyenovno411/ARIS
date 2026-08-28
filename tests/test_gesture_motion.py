import pytest

from aris.vision.gesture_motion import (
    AutoRotateController,
    GestureMomentum,
    RotationSpring,
    clamp_zoom_distance,
    zoom_distance_by_percent,
)


def test_auto_rotate_pauses_and_resumes_after_five_seconds() -> None:
    """Kiểm tra cử chỉ dừng tự xoay ngay và đúng năm giây sau mới chạy tiếp."""
    controller = AutoRotateController(resume_delay_seconds=5.0)

    controller.note_gesture_activity(now=10.0)

    assert not controller.should_rotate(now=14.99)
    assert controller.remaining_seconds(now=14.99) == pytest.approx(0.01)
    assert controller.should_rotate(now=15.0)
    assert controller.is_rotating


def test_each_new_gesture_restarts_auto_rotate_countdown() -> None:
    """Kiểm tra tín hiệu tay liên tục luôn đẩy countdown tới sau cử chỉ cuối cùng."""
    controller = AutoRotateController(resume_delay_seconds=5.0)
    controller.note_gesture_activity(now=10.0)
    controller.note_gesture_activity(now=13.0)

    assert not controller.should_rotate(now=15.0)
    assert controller.should_rotate(now=18.0)


def test_manual_auto_rotate_disable_never_resumes_from_countdown() -> None:
    """Kiểm tra nút tắt thủ công không bị bộ đếm cử chỉ tự ý bật lại."""
    controller = AutoRotateController(resume_delay_seconds=5.0)
    controller.note_gesture_activity(now=10.0)
    controller.set_enabled(False)

    assert not controller.should_rotate(now=100.0)
    assert not controller.is_rotating


def test_fast_flick_creates_more_rotation_than_slow_drag() -> None:
    """Kiểm tra flick lớn trong cùng thời gian tạo vận tốc xoay mạnh hơn drag nhẹ."""
    slow = GestureMomentum()
    fast = GestureMomentum()
    slow.push(yaw_delta=1.0, pitch_delta=0.0, elapsed=1 / 30)
    fast.push(yaw_delta=6.0, pitch_delta=0.0, elapsed=1 / 30)

    slow_step = slow.advance(1 / 60)
    fast_step = fast.advance(1 / 60)

    assert fast_step.yaw > slow_step.yaw * 4


def test_flick_keeps_direction_while_friction_slows_it() -> None:
    """Kiểm tra quán tính tiếp tục đúng hướng và giảm dần khi không nhận lực mới."""
    momentum = GestureMomentum()
    momentum.push(yaw_delta=6.0, pitch_delta=0.0, elapsed=1 / 30)

    first = momentum.advance(1 / 60)
    second = momentum.advance(1 / 60)

    assert first.yaw > second.yaw > 0


def test_reset_removes_remaining_rotation() -> None:
    """Kiểm tra reset loại bỏ toàn bộ quán tính còn lại trước khi đổi chế độ."""
    momentum = GestureMomentum()
    momentum.push(yaw_delta=6.0, pitch_delta=2.0, elapsed=1 / 30)
    momentum.reset()

    step = momentum.advance(1 / 60)

    assert step.yaw == 0
    assert step.pitch == 0


def test_zoom_distance_is_clamped_to_viewport_limits() -> None:
    """Kiểm tra pinch cực lớn không thể đẩy camera xuyên hoặc quá xa model."""
    assert clamp_zoom_distance(12.0, zoom_delta=100.0) == 6.0
    assert clamp_zoom_distance(12.0, zoom_delta=-100.0) == 26.0


def test_zoom_distance_uses_configured_sensitivity() -> None:
    """Kiểm tra công thức distance mới bằng distance cũ trừ delta nhân sensitivity."""
    result = clamp_zoom_distance(12.0, zoom_delta=0.2, sensitivity=5.0)

    assert result == 11.0


def test_voice_zoom_percent_preserves_visual_scale_math() -> None:
    """Kiểm tra tăng kích thước 50% đổi camera distance theo tỷ lệ nghịch chính xác."""
    assert zoom_distance_by_percent(12.0, 50) == 8.0
    assert zoom_distance_by_percent(12.0, -25) == 16.0


def test_voice_zoom_percent_is_clamped_to_visible_distance() -> None:
    """Kiểm tra lệnh giọng quá lớn vẫn giữ model trong giới hạn camera an toàn."""
    assert zoom_distance_by_percent(12.0, 500) == 6.0
    assert zoom_distance_by_percent(12.0, -500) == 26.0


def test_floating_view_zoom_uses_its_smaller_dynamic_camera_limit() -> None:
    """Kiểm tra viewport trong suốt không bị giới hạn cũ đảo ngược lệnh phóng to."""
    assert zoom_distance_by_percent(7.13, 30, minimum=3.2, maximum=17.825) < 7.13


def test_rotation_spring_spreads_landmark_delta_across_render_frames() -> None:
    """Kiểm tra một delta webcam được trải qua nhiều frame thay vì tạo cú giật tức thời."""
    spring = RotationSpring()
    spring.push(yaw_delta=12.0, pitch_delta=0.0)

    first = spring.advance(1 / 120)
    second = spring.advance(1 / 120)

    assert 0.0 < first.yaw < 12.0
    assert second.yaw > 0.0
    assert first.yaw + second.yaw < 12.0


def test_rotation_spring_completes_unbounded_360_degree_yaw() -> None:
    """Kiểm tra yaw nhận đủ một vòng 360 độ mà không bị clamp giữa chuyển động."""
    spring = RotationSpring()
    spring.push(yaw_delta=360.0, pitch_delta=0.0)

    rendered_yaw = sum(spring.advance(1 / 120).yaw for _ in range(360))

    assert abs(rendered_yaw - 360.0) < 0.1


def test_rotation_spring_is_nearly_frame_rate_independent() -> None:
    """Kiểm tra cùng thời gian cho kết quả gần nhau ở render 60 FPS và 120 FPS."""

    def render_at(fps: int) -> float:
        """Mô phỏng tổng yaw sau một giây ở FPS render được cung cấp."""
        spring = RotationSpring()
        spring.push(yaw_delta=180.0, pitch_delta=0.0)
        return sum(spring.advance(1 / fps).yaw for _ in range(fps))

    assert abs(render_at(60) - render_at(120)) < 0.5


def test_rotation_spring_reset_discards_remaining_motion() -> None:
    """Kiểm tra nắm mới dừng phần chuyển động cũ để model bám tay ngay lập tức."""
    spring = RotationSpring()
    spring.push(yaw_delta=90.0, pitch_delta=20.0)
    spring.advance(1 / 120)
    spring.reset()

    step = spring.advance(1 / 120)

    assert step.yaw == 0.0
    assert step.pitch == 0.0
