from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Signal
from PySide6.QtWidgets import QWidget

from aris.search.models import SearchResult
from aris.ui.research_panel import ResearchPanel
from aris.vision.spatial_gesture import SpatialGestureFrame, SpatialGestureMode


class ResearchPanelManager(QObject):
    """Quản lý nhiều bảng Web Search nổi, lựa chọn, kéo và đóng độc lập trong HUD."""

    selection_changed = Signal(str)
    panel_closed = Signal(str)
    dismissal_started = Signal()

    def __init__(self, container: QWidget, max_panels: int = 6) -> None:
        """Gắn manager vào HUD và giới hạn số bảng để giữ UI/memory ổn định."""
        super().__init__(container)
        self.container = container
        self.max_panels = max(2, min(8, int(max_panels)))
        self._panels: OrderedDict[str, ResearchPanel] = OrderedDict()
        self._closing: set[str] = set()
        self._active_id: str | None = None
        self._sequence = 0
        self.container.installEventFilter(self)

    @property
    def panel_ids(self) -> tuple[str, ...]:
        """Trả ID của các bảng theo thứ tự tạo để worker định tuyến đúng kết quả."""
        return tuple(self._panels)

    @property
    def active_id(self) -> str | None:
        """Trả ID bảng đang nằm trên cùng hoặc None khi không còn bảng."""
        return self._active_id

    @property
    def has_panels(self) -> bool:
        """Cho biết HUD hiện có ít nhất một bảng tra cứu chưa được đóng."""
        return bool(self._panels)

    def panel(self, panel_id: str) -> ResearchPanel | None:
        """Trả widget theo ID để kiểm thử hoặc cập nhật kết quả bất đồng bộ."""
        return self._panels.get(panel_id)

    def open_loading(self, query: str) -> str:
        """Tạo bảng loading mới tại vị trí xen kẽ và trả ID ổn định cho worker."""
        while len(self._panels) >= self.max_panels:
            oldest_id = next(iter(self._panels))
            self._finalize_close(oldest_id)

        self._sequence += 1
        panel_id = f"research-{self._sequence}"
        panel = ResearchPanel(panel_id, self.container)
        panel.close_requested.connect(self.close_panel)
        panel.selected.connect(self.select_panel)
        self._panels[panel_id] = panel
        panel.move(
            research_panel_position(
                self.container.size(),
                panel.size(),
                len(self._panels) - 1,
            )
        )
        panel.show_loading(query)
        panel.animate_in()
        self.select_panel(panel_id)
        return panel_id

    def show_result(
        self,
        panel_id: str,
        result: SearchResult,
        requests_remaining: int,
    ) -> bool:
        """Đưa kết quả về đúng bảng đã tạo; trả False nếu bảng đã bị người dùng đóng."""
        panel = self._panels.get(panel_id)
        if panel is None or panel_id in self._closing:
            return False
        panel.show_result(result, requests_remaining)
        self.select_panel(panel_id)
        return True

    def select_panel(self, panel_id: str) -> bool:
        """Đưa một bảng lên trên cùng và cập nhật viền chọn mà không đổi vị trí bảng khác."""
        if panel_id not in self._panels or panel_id in self._closing:
            return False
        self._active_id = panel_id
        for candidate_id, panel in self._panels.items():
            panel.set_selected(candidate_id == panel_id)
        self.selection_changed.emit(panel_id)
        return True

    def close_panel(self, panel_id: str | None = None, *, play_effect: bool = True) -> bool:
        """De-materialize bảng theo ID hoặc bảng đang chọn rồi giải phóng sau animation."""
        target = panel_id or self._active_id
        panel = self._panels.get(target or "")
        if panel is None or target is None or target in self._closing:
            return False
        self._closing.add(target)
        if play_effect:
            self.dismissal_started.emit()
        panel.animate_out(lambda target_id=target: self._finalize_close(target_id))
        return True

    def close_all(self, *, animated: bool = True) -> None:
        """Đóng mọi bảng đồng thời và chỉ yêu cầu một cue âm thanh cho cả nhóm."""
        panel_ids = tuple(self._panels)
        if not panel_ids:
            return
        if animated:
            self.dismissal_started.emit()
            for panel_id in panel_ids:
                self.close_panel(panel_id, play_effect=False)
            return
        for panel_id in panel_ids:
            self._finalize_close(panel_id)

    def apply_spatial_gesture(self, frame: SpatialGestureFrame) -> None:
        """Dùng tay mở để di chuyển và pinch dọc để cuộn riêng bảng đang chọn."""
        panel = self._panels.get(self._active_id or "")
        if panel is None or self._active_id in self._closing:
            return
        if frame.mode is SpatialGestureMode.MOVE:
            panel.apply_hand_translation(frame.move_x, frame.move_y)
        elif frame.mode is SpatialGestureMode.TRANSFORM:
            panel.apply_hand_scroll(frame.move_y)

    def dispose(self) -> None:
        """Dừng ngay animation/timer của mọi bảng khi ARIS tắt hoặc sonar ALERT khóa UI."""
        self.close_all(animated=False)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API name
        """Kẹp các bảng trong HUD khi full-screen, restore hoặc Windows scaling thay đổi."""
        if watched is self.container and event.type() is QEvent.Type.Resize:
            for panel in self._panels.values():
                panel.move_clamped(panel.pos())
        return super().eventFilter(watched, event)

    def _finalize_close(self, panel_id: str) -> None:
        """Xóa một widget đã tắt và chọn bảng mới nhất còn lại làm active."""
        panel = self._panels.pop(panel_id, None)
        self._closing.discard(panel_id)
        if panel is None:
            return
        panel.stop()
        panel.deleteLater()
        if self._active_id == panel_id:
            self._active_id = next(reversed(self._panels), None)
        if self._active_id is not None:
            self.select_panel(self._active_id)
        else:
            self.selection_changed.emit("")
        self.panel_closed.emit(panel_id)


def research_panel_position(container_size: QSize, panel_size: QSize, index: int) -> QPoint:
    """Xếp bốn bảng đầu vào bốn góc; bảng sau cascade nhẹ và vẫn kéo được."""
    margin = 26
    max_x = max(margin, container_size.width() - panel_size.width() - margin)
    max_y = max(margin, container_size.height() - panel_size.height() - margin)
    slot = index % 4
    layer = index // 4
    inset = min(90, layer * 34)
    right_side = slot in {0, 2}
    bottom_side = slot in {2, 3}
    x_value = max_x - inset if right_side else margin + inset
    y_value = max_y - inset if bottom_side else margin + inset
    return QPoint(x_value, y_value)
