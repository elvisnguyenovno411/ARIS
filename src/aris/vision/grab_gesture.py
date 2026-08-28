from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from aris.vision.hand_geometry import GestureInterpreter


@dataclass(frozen=True, slots=True)
class GrabGestureFrame:
    """Mô tả trạng thái nắm/thả cùng delta xoay và zoom của một frame landmark."""

    grabbed: bool = False
    just_grabbed: bool = False
    just_released: bool = False
    pointing: bool = False
    yaw: float = 0.0
    pitch: float = 0.0
    zoom: float = 0.0


class GrabGestureInterpreter:
    """Nhận diện pinch nắm, kéo và thả từ landmark mà không lưu frame camera."""

    def __init__(
        self,
        smoothing: float = 0.78,
        grab_threshold: float = 0.32,
        release_threshold: float = 0.58,
        grab_confirm_frames: int = 3,
    ) -> None:
        """Khởi tạo ngưỡng pinch có hysteresis và số frame xác nhận để chống kích hoạt nhầm."""
        self.smoothing = float(np.clip(smoothing, 0.05, 1.0))
        self.grab_threshold = max(0.05, float(grab_threshold))
        self.release_threshold = max(self.grab_threshold + 0.05, float(release_threshold))
        self.grab_confirm_frames = max(1, int(grab_confirm_frames))
        self._filtered_cursor: np.ndarray | None = None
        self._previous_cursor: np.ndarray | None = None
        self._filtered_pinch: float | None = None
        self._hover_interpreter = GestureInterpreter()
        self._close_frames = 0
        self._grabbed = False

    @property
    def is_grabbed(self) -> bool:
        """Cho biết model hiện có đang được giữ bằng pinch hay không."""
        return self._grabbed

    def reset(self) -> None:
        """Xóa bộ lọc và trạng thái nắm khi bắt đầu một phiên landmark mới."""
        self._filtered_cursor = None
        self._previous_cursor = None
        self._filtered_pinch = None
        self._hover_interpreter.reset()
        self._close_frames = 0
        self._grabbed = False

    def cancel(self) -> GrabGestureFrame:
        """Hủy trạng thái hiện tại và trả về release nếu model đang được nắm."""
        was_grabbed = self._grabbed
        self.reset()
        return GrabGestureFrame(just_released=was_grabbed)

    def update(self, landmarks: Iterable[Sequence[float]]) -> GrabGestureFrame:
        """Suy ra trạng thái grab, delta kéo và zoom từ 21 landmark chuẩn hóa."""
        points = np.asarray(list(landmarks), dtype=np.float32)
        if points.shape != (21, 3):
            raise ValueError(f"Expected 21 three-dimensional landmarks, received {points.shape}.")

        # Palm center ổn định hơn midpoint pinch, nên động tác mở ngón không tạo cú xoay giả.
        palm_width = max(float(np.linalg.norm(points[5] - points[17])), 1e-5)
        cursor = points[[0, 5, 9, 13, 17], :2].mean(axis=0).astype(np.float64)
        pinch = float(np.linalg.norm(points[4] - points[8])) / palm_width

        if self._filtered_cursor is None or self._filtered_pinch is None:
            self._filtered_cursor = cursor.copy()
            self._previous_cursor = cursor.copy()
            self._filtered_pinch = pinch
            hover = self._hover_interpreter.update(points)
            return GrabGestureFrame(
                pointing=bool(hover.yaw or hover.pitch),
                yaw=hover.yaw,
                pitch=hover.pitch,
                zoom=hover.zoom,
            )

        # EMA giảm jitter landmark nhưng alpha cao để thao tác grab vẫn bám tay.
        self._filtered_cursor += (cursor - self._filtered_cursor) * self.smoothing
        self._filtered_pinch += (pinch - self._filtered_pinch) * self.smoothing
        previous_cursor = self._previous_cursor
        movement = self._filtered_cursor - previous_cursor
        self._previous_cursor = self._filtered_cursor.copy()

        if not self._grabbed:
            # Ba frame pinch kín liên tục chống việc zoom vô tình kích hoạt grab.
            self._close_frames = (
                self._close_frames + 1
                if self._filtered_pinch <= self.grab_threshold
                else 0
            )
            if self._close_frames >= self.grab_confirm_frames:
                self._grabbed = True
                self._close_frames = 0
                self._hover_interpreter.reset()
                return GrabGestureFrame(grabbed=True, just_grabbed=True)

            # Khi chưa grab, hybrid mode vẫn nhận hướng ngón trỏ và pinch zoom như yêu cầu beta.
            hover = self._hover_interpreter.update(points)
            zoom = hover.zoom if self._filtered_pinch > self.release_threshold else 0.0
            return GrabGestureFrame(
                pointing=bool(hover.yaw or hover.pitch),
                yaw=hover.yaw,
                pitch=hover.pitch,
                zoom=zoom,
            )

        yaw = 0.0
        pitch = 0.0
        # Trong lúc grab, delta palm được đổi sang độ quay và clamp để flick không mất kiểm soát.
        if math.fabs(float(movement[0])) >= 0.001:
            yaw = float(np.clip(movement[0] * 260.0, -10.0, 10.0))
        if math.fabs(float(movement[1])) >= 0.001:
            pitch = float(np.clip(-movement[1] * 220.0, -8.0, 8.0))

        released = self._filtered_pinch >= self.release_threshold
        if released:
            self._grabbed = False
            self._hover_interpreter.reset()
        return GrabGestureFrame(
            grabbed=self._grabbed,
            just_released=released,
            yaw=round(yaw, 4),
            pitch=round(pitch, 4),
        )
