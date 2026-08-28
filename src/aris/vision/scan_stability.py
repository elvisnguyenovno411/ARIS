from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StabilityUpdate:
    """Chứa phần trăm tiến độ và cờ capture sau một frame đánh giá tư thế."""

    progress: int
    complete: bool


class ScanStability:
    """Chỉ cho phép capture sau một chuỗi frame open-palm đạt chuẩn liên tục."""

    def __init__(self, required_frames: int = 14) -> None:
        """Khởi tạo số frame liên tục cần thiết; giá trị nhỏ nhất là một frame."""
        self.required_frames = max(1, int(required_frames))
        self._stable_frames = 0

    def reset(self) -> None:
        """Xóa chuỗi ổn định khi mất tay hoặc tư thế không còn đạt chuẩn."""
        self._stable_frames = 0

    def update(self, ready: bool) -> StabilityUpdate:
        """Nhận kết quả frame và trả tiến độ; một frame lỗi sẽ đưa tiến độ về 0."""
        # Capture chỉ an toàn khi các frame đạt chuẩn liên tục; không cộng dồn qua lúc mất tay.
        self._stable_frames = self._stable_frames + 1 if ready else 0
        progress = min(100, round(self._stable_frames / self.required_frames * 100))
        return StabilityUpdate(
            progress=progress,
            complete=self._stable_frames >= self.required_frames,
        )
