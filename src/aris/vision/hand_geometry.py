from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import numpy as np

FINGER_CHAINS: dict[str, tuple[int, ...]] = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


@dataclass(frozen=True, slots=True)
class HandProfile:
    """Lưu tỷ lệ bàn tay đã chuẩn hóa; không chứa ảnh hoặc kích thước thật."""

    handedness: str
    palm_width: float
    palm_length: float
    finger_lengths: dict[str, float]
    finger_spreads: dict[str, float]
    captured_at: str

    def to_dict(self) -> dict[str, object]:
        """Chuyển profile thành dữ liệu JSON an toàn để lưu local."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> HandProfile:
        """Khôi phục profile từ JSON và kiểm tra các trường cơ bản."""
        return cls(
            handedness=str(payload.get("handedness", "Right")),
            palm_width=float(payload.get("palm_width", 1.0)),
            palm_length=float(payload.get("palm_length", 1.0)),
            finger_lengths={
                str(key): float(value)
                for key, value in dict(payload.get("finger_lengths", {})).items()
            },
            finger_spreads={
                str(key): float(value)
                for key, value in dict(payload.get("finger_spreads", {})).items()
            },
            captured_at=str(payload.get("captured_at", "")),
        )


@dataclass(frozen=True, slots=True)
class ScanAssessment:
    """Mô tả chất lượng tư thế quét và câu hướng dẫn ngắn cho người dùng."""

    ready: bool
    score: float
    guidance_key: str


@dataclass(frozen=True, slots=True)
class GestureDelta:
    """Chứa thay đổi góc xoay và zoom suy ra từ một khung landmark."""

    yaw: float = 0.0
    pitch: float = 0.0
    zoom: float = 0.0


def _points_array(landmarks: Iterable[Sequence[float]]) -> np.ndarray:
    """Chuyển 21 landmark thành mảng NumPy ba chiều và xác thực hình dạng."""
    points = np.asarray(list(landmarks), dtype=np.float32)
    if points.shape != (21, 3):
        raise ValueError(f"Expected 21 three-dimensional landmarks, received {points.shape}.")
    return points


def _distance(first: np.ndarray, second: np.ndarray) -> float:
    """Tính khoảng cách Euclid ba chiều giữa hai landmark."""
    return float(np.linalg.norm(first - second))


def build_hand_profile(
    landmarks: Iterable[Sequence[float]], handedness: str = "Right"
) -> HandProfile:
    """Tạo tỷ lệ bàn tay tương đối từ 21 landmark mà không suy đoán cm/mm."""
    points = _points_array(landmarks)
    # Chuẩn hóa mọi kích thước theo bề rộng lòng bàn tay (MCP 5→17), vì webcam không có scale mm.
    palm_width_raw = max(_distance(points[5], points[17]), 1e-5)
    palm_length_raw = _distance(points[0], points[9])
    finger_lengths: dict[str, float] = {}
    for name, chain in FINGER_CHAINS.items():
        indices = (0, *chain) if name == "thumb" else chain
        # Tổng chiều dài từng đốt giữ tỷ lệ hình học tốt hơn khoảng cách thẳng tip→base.
        length = sum(
            _distance(points[a], points[b]) for a, b in zip(indices, indices[1:], strict=False)
        )
        # Clamp loại bỏ landmark lỗi để model low-poly không kéo dài ra khỏi viewport.
        finger_lengths[name] = round(float(np.clip(length / palm_width_raw, 0.25, 3.0)), 4)

    middle_tip = points[12]
    spreads = {
        "thumb": _distance(points[4], points[8]) / palm_width_raw,
        "index": _distance(points[8], middle_tip) / palm_width_raw,
        "ring": _distance(points[16], middle_tip) / palm_width_raw,
        "pinky": _distance(points[20], middle_tip) / palm_width_raw,
    }
    return HandProfile(
        handedness="Left" if handedness.casefold().startswith("l") else "Right",
        palm_width=1.0,
        palm_length=round(float(np.clip(palm_length_raw / palm_width_raw, 0.6, 2.2)), 4),
        finger_lengths=finger_lengths,
        finger_spreads={
            key: round(float(np.clip(value, 0.0, 2.0)), 4) for key, value in spreads.items()
        },
        captured_at=datetime.now(UTC).isoformat(),
    )


def assess_open_palm(landmarks: Iterable[Sequence[float]]) -> ScanAssessment:
    """Đánh giá bàn tay có ở giữa, đủ lớn và mở phù hợp để quét hay chưa."""
    points = _points_array(landmarks)
    # Center/size dùng tọa độ chuẩn hóa 0..1 nên không phụ thuộc độ phân giải webcam.
    center = points[:, :2].mean(axis=0)
    width = float(points[:, 0].max() - points[:, 0].min())
    height = float(points[:, 1].max() - points[:, 1].min())
    if center[0] < 0.36:
        return ScanAssessment(False, 0.35, "move_right")
    if center[0] > 0.64:
        return ScanAssessment(False, 0.35, "move_left")
    if center[1] < 0.32:
        return ScanAssessment(False, 0.4, "move_down")
    if center[1] > 0.68:
        return ScanAssessment(False, 0.4, "move_up")
    if max(width, height) < 0.32:
        return ScanAssessment(False, 0.45, "move_closer")
    if max(width, height) > 0.9:
        return ScanAssessment(False, 0.45, "move_away")

    wrist = points[0]
    extended = 0
    # Một ngón được xem là mở khi tip xa cổ tay hơn PIP ít nhất 12%, giúp chống co ngón nhẹ.
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if _distance(points[tip], wrist) > _distance(points[pip], wrist) * 1.12:
            extended += 1
    spread = _distance(points[8], points[20]) / max(_distance(points[5], points[17]), 1e-5)
    if extended < 4:
        return ScanAssessment(False, 0.55, "open_fingers")
    if spread < 1.35:
        return ScanAssessment(False, 0.65, "separate_fingers")
    return ScanAssessment(True, 1.0, "hold_still")


class GestureInterpreter:
    """Biến hướng ngón trỏ và độ chụm thành delta xoay/zoom ổn định có dead zone."""

    def __init__(
        self,
        smoothing: float = 0.42,
        direction_dead_zone: float = 0.28,
        zoom_dead_zone: float = 0.015,
    ) -> None:
        """Khởi tạo EMA và dead zone; đầu vào được kẹp để tránh cấu hình gây rung."""
        self.smoothing = float(np.clip(smoothing, 0.05, 1.0))
        self.direction_dead_zone = float(np.clip(direction_dead_zone, 0.05, 0.8))
        self.zoom_dead_zone = float(np.clip(zoom_dead_zone, 0.001, 0.2))
        self._yaw = 0.0
        self._pitch = 0.0
        self._filtered_pinch: float | None = None
        self._zoom_reference: float | None = None

    def reset(self) -> None:
        """Xóa trạng thái khung trước khi bắt đầu một phiên cử chỉ mới."""
        self._yaw = 0.0
        self._pitch = 0.0
        self._filtered_pinch = None
        self._zoom_reference = None

    def update(self, landmarks: Iterable[Sequence[float]]) -> GestureDelta:
        """Trả delta xoay từ hướng MCP→tip và zoom từ thay đổi khoảng chụm đã lọc."""
        points = _points_array(landmarks)
        palm_width = max(_distance(points[5], points[17]), 1e-5)
        direction = points[8, :2] - points[5, :2]
        magnitude = float(np.linalg.norm(direction))
        target_yaw = 0.0
        target_pitch = 0.0

        # Chỉ nhận hướng khi đoạn MCP(5)→tip(8) đủ dài so với lòng bàn tay.
        if magnitude > palm_width * 0.45:
            unit = direction / max(magnitude, 1e-5)
            horizontal = float(unit[0])
            vertical = float(unit[1])
            # Dead zone theo từng trục chặn rung nhỏ nhưng vẫn cho hướng chéo điều khiển hai trục.
            if math.fabs(horizontal) >= self.direction_dead_zone:
                target_yaw = float(np.clip(horizontal * 2.8, -2.8, 2.8))
            if math.fabs(vertical) >= self.direction_dead_zone:
                target_pitch = float(np.clip(-vertical * 2.2, -2.2, 2.2))

        # EMA: filtered += alpha * (target-filtered); alpha nhỏ mượt hơn nhưng trễ hơn.
        self._yaw += (target_yaw - self._yaw) * self.smoothing
        self._pitch += (target_pitch - self._pitch) * self.smoothing
        if target_yaw == 0.0 and math.fabs(self._yaw) < 0.04:
            self._yaw = 0.0
        if target_pitch == 0.0 and math.fabs(self._pitch) < 0.04:
            self._pitch = 0.0

        # Pinch được chia cho palm width để zoom ổn định khi tay gần/xa camera.
        pinch = _distance(points[4], points[8]) / palm_width
        if self._filtered_pinch is None or self._zoom_reference is None:
            self._filtered_pinch = pinch
            self._zoom_reference = pinch
            zoom = 0.0
        else:
            self._filtered_pinch += (pinch - self._filtered_pinch) * self.smoothing
            pinch_delta = self._filtered_pinch - self._zoom_reference
            zoom = 0.0
            # So với reference gần nhất để chuyển động chậm được tích lũy thay vì mất qua dead zone.
            if math.fabs(pinch_delta) >= self.zoom_dead_zone:
                zoom = float(np.clip(pinch_delta * 1.8, -0.18, 0.18))
                self._zoom_reference = self._filtered_pinch

        return GestureDelta(
            yaw=round(self._yaw, 4),
            pitch=round(self._pitch, 4),
            zoom=round(zoom, 4),
        )
