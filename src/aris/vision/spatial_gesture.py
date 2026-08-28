from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class SpatialGestureMode(StrEnum):
    """Liệt kê trạng thái tay trung lập, di chuyển hologram và biến đổi model."""

    NEUTRAL = "neutral"
    MOVE = "move"
    TRANSFORM = "transform"


@dataclass(frozen=True, slots=True)
class SpatialGestureFrame:
    """Chứa mode độc quyền cùng delta di chuyển, cuộn, xoay và zoom của một frame tay."""

    mode: SpatialGestureMode = SpatialGestureMode.NEUTRAL
    just_started: bool = False
    just_released: bool = False
    move_x: float = 0.0
    move_y: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    zoom: float = 0.0


class SpatialGestureInterpreter:
    """Biến tay mở và pinch thành hai mode khóa riêng để không trùng chức năng."""

    def __init__(
        self,
        smoothing: float = 0.56,
        pinch_threshold: float = 0.40,
        open_threshold: float = 0.62,
        transform_hold_threshold: float = 1.05,
        confirm_frames: int = 3,
        release_frames: int = 2,
        missing_grace_frames: int = 3,
    ) -> None:
        """Khởi tạo EMA, ngưỡng dáng tay và số frame xác nhận chống nhận nhầm."""
        self.smoothing = float(np.clip(smoothing, 0.05, 1.0))
        self.pinch_threshold = max(0.05, float(pinch_threshold))
        self.open_threshold = max(self.pinch_threshold + 0.1, float(open_threshold))
        self.transform_hold_threshold = max(
            self.open_threshold,
            float(transform_hold_threshold),
        )
        self.confirm_frames = max(1, int(confirm_frames))
        self.release_frames = max(1, int(release_frames))
        self.missing_grace_frames = max(0, int(missing_grace_frames))
        self._mode = SpatialGestureMode.NEUTRAL
        self._candidate = SpatialGestureMode.NEUTRAL
        self._candidate_frames = 0
        self._release_frames = 0
        self._filtered_cursor: np.ndarray | None = None
        self._previous_cursor: np.ndarray | None = None
        self._filtered_pinch: float | None = None
        self._missing_frames = 0

    @property
    def mode(self) -> SpatialGestureMode:
        """Trả mode đã khóa hiện tại để UI có thể phản hồi trạng thái ngắn."""
        return self._mode

    def reset(self) -> None:
        """Xóa mode và bộ lọc khi camera mất tay hoặc phiên gesture kết thúc."""
        self._mode = SpatialGestureMode.NEUTRAL
        self._candidate = SpatialGestureMode.NEUTRAL
        self._candidate_frames = 0
        self._release_frames = 0
        self._filtered_cursor = None
        self._previous_cursor = None
        self._filtered_pinch = None
        self._missing_frames = 0

    def cancel(self) -> SpatialGestureFrame:
        """Hủy mode đang khóa và báo một nhịp release nếu trước đó có thao tác."""
        was_active = self._mode is not SpatialGestureMode.NEUTRAL
        self.reset()
        return SpatialGestureFrame(just_released=was_active)

    def miss(self) -> SpatialGestureFrame:
        """Giữ mode qua vài frame mất tay ngắn, rồi hủy để mở rộng tầm nhận diện xa."""
        if self._mode is SpatialGestureMode.NEUTRAL:
            return SpatialGestureFrame()
        self._missing_frames += 1
        if self._missing_frames <= self.missing_grace_frames:
            return SpatialGestureFrame(mode=self._mode)
        return self.cancel()

    def update(self, landmarks: Iterable[Sequence[float]]) -> SpatialGestureFrame:
        """Nhận 21 landmark và trả mode MOVE hoặc TRANSFORM loại trừ lẫn nhau."""
        points = np.asarray(list(landmarks), dtype=np.float32)
        if points.shape != (21, 3):
            raise ValueError(f"Expected 21 three-dimensional landmarks, received {points.shape}.")

        was_missing = self._missing_frames > 0
        self._missing_frames = 0
        palm_width = max(float(np.linalg.norm(points[5, :2] - points[17, :2])), 1e-5)
        cursor = points[[0, 5, 9, 13, 17], :2].mean(axis=0).astype(np.float64)
        pinch = float(np.linalg.norm(points[4, :2] - points[8, :2])) / palm_width
        if self._filtered_cursor is None or self._filtered_pinch is None:
            self._filtered_cursor = cursor.copy()
            self._previous_cursor = cursor.copy()
            self._filtered_pinch = pinch
        else:
            # Tay càng xa (palm nhỏ) càng được lọc mạnh để giảm rung landmark mà không tăng lag gần.
            adaptive_smoothing = float(
                np.clip(self.smoothing * palm_width / 0.15, 0.28, self.smoothing)
            )
            self._filtered_cursor += (cursor - self._filtered_cursor) * adaptive_smoothing
            self._filtered_pinch += (pinch - self._filtered_pinch) * adaptive_smoothing

        if was_missing:
            # Không dùng quãng dịch trong lúc MediaPipe mất tay để tránh cú nhảy khi bắt lại.
            self._previous_cursor = self._filtered_cursor.copy()

        raw_mode = self._classify(points, float(self._filtered_pinch))
        transition = self._transition(raw_mode)
        if transition is not None:
            return transition
        if self._mode is SpatialGestureMode.NEUTRAL:
            return SpatialGestureFrame()

        distance_gain = float(np.clip(0.13 / palm_width, 0.85, 1.65))
        cursor_movement = (self._filtered_cursor - self._previous_cursor) * distance_gain
        self._previous_cursor = self._filtered_cursor.copy()

        if self._mode is SpatialGestureMode.MOVE:
            move_x = float(cursor_movement[0]) if abs(float(cursor_movement[0])) >= 0.0008 else 0.0
            move_y = float(cursor_movement[1]) if abs(float(cursor_movement[1])) >= 0.0008 else 0.0
            return SpatialGestureFrame(
                mode=self._mode,
                move_x=round(float(np.clip(move_x, -0.08, 0.08)), 5),
                move_y=round(float(np.clip(move_y, -0.08, 0.08)), 5),
            )

        yaw = 0.0
        if math.fabs(float(cursor_movement[0])) >= 0.001:
            yaw = float(np.clip(cursor_movement[0] * 260.0, -10.0, 10.0))
        move_y = (
            float(cursor_movement[1])
            if math.fabs(float(cursor_movement[1])) >= 0.0008
            else 0.0
        )
        return SpatialGestureFrame(
            mode=self._mode,
            move_y=round(float(np.clip(move_y, -0.08, 0.08)), 5),
            yaw=round(yaw, 4),
            pitch=0.0,
            zoom=0.0,
        )

    def _classify(self, points: np.ndarray, pinch: float) -> SpatialGestureMode:
        """Phân loại tay mở năm ngón hoặc pinch dựa trên tỷ lệ theo lòng bàn tay."""
        wrist = points[0]
        extended = sum(
            float(np.linalg.norm(points[tip] - wrist))
            > float(np.linalg.norm(points[pip] - wrist)) * 1.06
            for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18))
        )
        thumb_extended = float(np.linalg.norm(points[4] - wrist)) > float(
            np.linalg.norm(points[3] - wrist)
        ) * 1.03
        if (
            self._mode is SpatialGestureMode.TRANSFORM
            and pinch <= self.transform_hold_threshold
        ):
            # Ưu tiên khóa TRANSFORM để việc banh/chụm hai ngón không bị hiểu nhầm thành MOVE.
            return SpatialGestureMode.TRANSFORM
        if extended >= 3 and thumb_extended and pinch >= self.open_threshold:
            return SpatialGestureMode.MOVE
        if pinch <= self.pinch_threshold:
            return SpatialGestureMode.TRANSFORM
        return SpatialGestureMode.NEUTRAL

    def _transition(self, raw_mode: SpatialGestureMode) -> SpatialGestureFrame | None:
        """Khóa mode sau xác nhận và buộc release ngắn trước khi đổi chức năng."""
        if self._mode is SpatialGestureMode.NEUTRAL:
            if raw_mode is SpatialGestureMode.NEUTRAL:
                self._candidate = raw_mode
                self._candidate_frames = 0
                return None
            if raw_mode is self._candidate:
                self._candidate_frames += 1
            else:
                self._candidate = raw_mode
                self._candidate_frames = 1
            if self._candidate_frames < self.confirm_frames:
                return None
            self._mode = raw_mode
            self._candidate = SpatialGestureMode.NEUTRAL
            self._candidate_frames = 0
            self._release_frames = 0
            self._previous_cursor = self._filtered_cursor.copy()
            return SpatialGestureFrame(mode=self._mode, just_started=True)

        if raw_mode is self._mode:
            self._release_frames = 0
            return None
        self._release_frames += 1
        if self._release_frames < self.release_frames:
            return SpatialGestureFrame(mode=self._mode)
        self._mode = SpatialGestureMode.NEUTRAL
        self._candidate = SpatialGestureMode.NEUTRAL
        self._candidate_frames = 0
        self._release_frames = 0
        self._previous_cursor = self._filtered_cursor.copy()
        return SpatialGestureFrame(just_released=True)
