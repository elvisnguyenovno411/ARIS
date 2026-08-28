from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RotationStep:
    """Chứa góc quay cần tích phân trong một nhịp render theo hai trục camera."""

    yaw: float = 0.0
    pitch: float = 0.0


class AutoRotateController:
    """Tạm dừng tự xoay khi có cử chỉ và tự bật lại sau khoảng nghỉ cấu hình."""

    def __init__(self, resume_delay_seconds: float = 5.0) -> None:
        """Khởi tạo tự xoay đang bật cùng thời gian chờ tối thiểu sau cử chỉ."""
        self.resume_delay_seconds = max(0.1, float(resume_delay_seconds))
        self._enabled = True
        self._resume_at: float | None = None

    @property
    def is_enabled(self) -> bool:
        """Cho biết người dùng có cho phép chế độ tự xoay hay không."""
        return self._enabled

    @property
    def is_rotating(self) -> bool:
        """Cho biết model đang được phép tự xoay ở thời điểm trạng thái gần nhất."""
        return self._enabled and self._resume_at is None

    def set_enabled(self, enabled: bool) -> None:
        """Bật tự xoay ngay hoặc tắt vô thời hạn theo lựa chọn thủ công."""
        self._enabled = bool(enabled)
        self._resume_at = None

    def note_gesture_activity(self, now: float | None = None) -> None:
        """Dừng tự xoay và dời mốc tự bật lại đến năm giây sau tín hiệu mới nhất."""
        if not self._enabled:
            return
        current = time.monotonic() if now is None else float(now)
        self._resume_at = current + self.resume_delay_seconds

    def should_rotate(self, now: float | None = None) -> bool:
        """Cập nhật countdown và trả True khi model được phép tự xoay trong frame này."""
        if not self._enabled:
            return False
        if self._resume_at is None:
            return True
        current = time.monotonic() if now is None else float(now)
        if current < self._resume_at:
            return False
        self._resume_at = None
        return True

    def remaining_seconds(self, now: float | None = None) -> float:
        """Trả số giây còn lại trước khi tự xoay hoặc 0 nếu không còn countdown."""
        if not self._enabled or self._resume_at is None:
            return 0.0
        current = time.monotonic() if now is None else float(now)
        return max(0.0, self._resume_at - current)


class GestureMomentum:
    """Mô phỏng vận tốc góc và ma sát để flick nhanh tạo quán tính xoay tự nhiên."""

    def __init__(
        self,
        response: float = 0.78,
        damping: float = 2.6,
        max_yaw_speed: float = 480.0,
        max_pitch_speed: float = 300.0,
    ) -> None:
        """Khởi tạo độ bám, ma sát và giới hạn vận tốc theo độ mỗi giây."""
        self.response = max(0.05, min(1.0, float(response)))
        self.damping = max(0.1, float(damping))
        self.max_yaw_speed = max(30.0, float(max_yaw_speed))
        self.max_pitch_speed = max(30.0, float(max_pitch_speed))
        self._yaw_speed = 0.0
        self._pitch_speed = 0.0

    def reset(self) -> None:
        """Xóa vận tốc góc để reset model hoặc chuyển chế độ không gây cú xoay thừa."""
        self._yaw_speed = 0.0
        self._pitch_speed = 0.0

    def push(self, yaw_delta: float, pitch_delta: float, elapsed: float) -> None:
        """Nhận delta gesture và thời gian frame để suy ra vận tốc vuốt theo độ/giây."""
        # velocity = angle / time; clamp dt tránh chia gần 0 khi hai signal đến sát nhau.
        interval = max(1 / 120, min(0.12, float(elapsed)))
        if yaw_delta:
            incoming_yaw = max(
                -self.max_yaw_speed,
                min(self.max_yaw_speed, float(yaw_delta) / interval),
            )
            self._yaw_speed += (incoming_yaw - self._yaw_speed) * self.response
        if pitch_delta:
            incoming_pitch = max(
                -self.max_pitch_speed,
                min(self.max_pitch_speed, float(pitch_delta) / interval),
            )
            self._pitch_speed += (incoming_pitch - self._pitch_speed) * self.response

    def advance(self, elapsed: float) -> RotationStep:
        """Tích phân vận tốc trong một frame render và giảm dần bằng ma sát thời gian thực."""
        interval = max(0.0, min(0.05, float(elapsed)))
        # Góc frame = vận tốc * dt; dt bị clamp để app resume không làm model nhảy xa.
        step = RotationStep(
            yaw=self._yaw_speed * interval,
            pitch=self._pitch_speed * interval,
        )
        # Ma sát mũ độc lập FPS: cùng thời gian thực sẽ giảm tốc như nhau ở 30 hoặc 60 FPS.
        decay = math.exp(-self.damping * interval)
        self._yaw_speed *= decay
        self._pitch_speed *= decay
        if abs(self._yaw_speed) < 0.05:
            self._yaw_speed = 0.0
        if abs(self._pitch_speed) < 0.05:
            self._pitch_speed = 0.0
        return step


class RotationSpring:
    """Trải delta landmark thưa thành chuyển động xoay liên tục ở FPS render cao."""

    def __init__(
        self,
        natural_frequency: float = 26.0,
        damping_ratio: float = 1.0,
        max_yaw_speed: float = 720.0,
        max_pitch_speed: float = 480.0,
    ) -> None:
        """Khởi tạo lò xo tới hạn cùng giới hạn vận tốc góc theo độ mỗi giây."""
        self.natural_frequency = max(4.0, float(natural_frequency))
        self.damping_ratio = max(0.7, float(damping_ratio))
        self.max_yaw_speed = max(30.0, float(max_yaw_speed))
        self.max_pitch_speed = max(30.0, float(max_pitch_speed))
        self._remaining_yaw = 0.0
        self._remaining_pitch = 0.0
        self._yaw_speed = 0.0
        self._pitch_speed = 0.0

    def reset(self) -> None:
        """Dừng ngay vận tốc và bỏ phần góc chưa render khi nắm lại hoặc đổi model."""
        self._remaining_yaw = 0.0
        self._remaining_pitch = 0.0
        self._yaw_speed = 0.0
        self._pitch_speed = 0.0

    def push(self, yaw_delta: float, pitch_delta: float) -> None:
        """Cộng delta mới vào góc đích; yaw không giới hạn để model quay đủ 360 độ."""
        self._remaining_yaw += float(yaw_delta)
        self._remaining_pitch += float(pitch_delta)

    def advance(self, elapsed: float) -> RotationStep:
        """Tính bước xoay mượt theo thời gian với vận tốc liên tục và không vượt đích."""
        interval = max(0.0, min(0.05, float(elapsed)))
        if interval == 0.0:
            return RotationStep()

        # Chia nhỏ dt giúp kết quả gần như giống nhau ở màn hình 60, 120 hoặc 165 Hz.
        substeps = max(1, math.ceil(interval / (1 / 240)))
        step_interval = interval / substeps
        yaw_total = 0.0
        pitch_total = 0.0
        stiffness = self.natural_frequency**2
        damping = 2.0 * self.damping_ratio * self.natural_frequency

        for _ in range(substeps):
            yaw_step, self._remaining_yaw, self._yaw_speed = self._integrate_axis(
                self._remaining_yaw,
                self._yaw_speed,
                stiffness,
                damping,
                self.max_yaw_speed,
                step_interval,
            )
            pitch_step, self._remaining_pitch, self._pitch_speed = self._integrate_axis(
                self._remaining_pitch,
                self._pitch_speed,
                stiffness,
                damping,
                self.max_pitch_speed,
                step_interval,
            )
            yaw_total += yaw_step
            pitch_total += pitch_step

        return RotationStep(yaw=yaw_total, pitch=pitch_total)

    @staticmethod
    def _integrate_axis(
        remaining: float,
        speed: float,
        stiffness: float,
        damping: float,
        speed_limit: float,
        elapsed: float,
    ) -> tuple[float, float, float]:
        """Tích phân một trục lò xo và chặn overshoot ở cuối chuyển động."""
        acceleration = stiffness * remaining - damping * speed
        next_speed = max(-speed_limit, min(speed_limit, speed + acceleration * elapsed))
        step = next_speed * elapsed
        if remaining and step * remaining > 0.0 and abs(step) >= abs(remaining):
            return remaining, 0.0, 0.0

        next_remaining = remaining - step
        if abs(next_remaining) < 0.001 and abs(next_speed) < 0.05:
            return next_remaining, 0.0, 0.0
        return step, next_remaining, next_speed


def clamp_zoom_distance(
    current_distance: float,
    zoom_delta: float,
    sensitivity: float = 9.0,
    minimum: float = 6.0,
    maximum: float = 26.0,
) -> float:
    """Đổi delta pinch thành khoảng cách camera và kẹp trong giới hạn nhìn thấy model."""
    lower = min(float(minimum), float(maximum))
    upper = max(float(minimum), float(maximum))
    # Pinch dương kéo camera gần hơn; clamp bảo vệ model khỏi bay qua near/far view.
    requested = float(current_distance) - float(zoom_delta) * float(sensitivity)
    return max(lower, min(upper, requested))


def zoom_distance_by_percent(
    current_distance: float,
    percent_delta: float,
    minimum: float = 6.0,
    maximum: float = 26.0,
) -> float:
    """Đổi phần trăm kích thước nhìn thấy thành khoảng cách camera được kẹp an toàn."""
    bounded_percent = max(-100.0, min(100.0, float(percent_delta)))
    visual_scale = max(0.2, 1.0 + bounded_percent / 100.0)
    requested = float(current_distance) / visual_scale
    lower = min(float(minimum), float(maximum))
    upper = max(float(minimum), float(maximum))
    return max(lower, min(upper, requested))
