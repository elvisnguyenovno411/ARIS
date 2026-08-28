from __future__ import annotations

import math
import time

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from aris.models.catalog import ModelCatalog
from aris.ui.hologram_view import HologramView
from aris.vision.grab_gesture import GrabGestureFrame
from aris.vision.hand_geometry import HandProfile
from aris.vision.spatial_gesture import SpatialGestureFrame, SpatialGestureMode

FLOATING_FRAME_SIZE = 340
FLOATING_VIEW_SIZE = 700


def clamp_floating_position(
    position: QPoint,
    container_size: QSize,
    widget_size: QSize,
    margin: int = 16,
    anchor_size: QSize | None = None,
) -> QPoint:
    """Kẹp khung điều khiển trong HUD nhưng cho vùng overscan trong suốt tràn ra ngoài."""
    safe_margin = max(0, int(margin))
    anchor = anchor_size or widget_size
    anchor_width = min(widget_size.width(), max(1, anchor.width()))
    anchor_height = min(widget_size.height(), max(1, anchor.height()))
    inset_x = round((widget_size.width() - anchor_width) / 2)
    inset_y = round((widget_size.height() - anchor_height) / 2)
    minimum_x = safe_margin - inset_x
    minimum_y = safe_margin - inset_y
    maximum_x = container_size.width() - safe_margin - inset_x - anchor_width
    maximum_y = container_size.height() - safe_margin - inset_y - anchor_height
    if maximum_x < minimum_x:
        minimum_x = maximum_x = round((container_size.width() - widget_size.width()) / 2)
    if maximum_y < minimum_y:
        minimum_y = maximum_y = round((container_size.height() - widget_size.height()) / 2)
    return QPoint(
        max(minimum_x, min(maximum_x, position.x())),
        max(minimum_y, min(maximum_y, position.y())),
    )


def centered_floating_position(container_size: QSize, widget_size: QSize) -> QPoint:
    """Tính tọa độ để tâm hologram trùng với tâm lõi ARIS trên HUD."""
    return QPoint(
        round((container_size.width() - widget_size.width()) / 2),
        round((container_size.height() - widget_size.height()) / 2),
    )


class FloatingHologram(QFrame):
    """Hiển thị một model 3D tách nền có thể chọn và kéo trong HUD ARIS."""

    selected = Signal(str)

    def __init__(
        self,
        model_key: str,
        display_name: str,
        parent: QWidget,
        render_fps: int = 120,
        profile: HandProfile | None = None,
    ) -> None:
        """Tạo viewport trong suốt cho một model và nạp profile tay khi được cung cấp."""
        super().__init__(parent)
        self.model_key = model_key
        self.display_name = display_name
        self._active_fps = max(30, min(120, int(render_fps)))
        self._drag_offset: QPoint | None = None
        self._target_x = 0.0
        self._target_y = 0.0
        self._last_position_at = time.monotonic()
        self.setObjectName("FloatingHologram")
        self.setProperty("selected", False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setAccessibleName(f"ARIS hologram: {display_name}")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(FLOATING_VIEW_SIZE, FLOATING_VIEW_SIZE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = HologramView(
            self,
            render_fps=self._active_fps,
            transparent=True,
            show_grid=False,
            initial_model_key=model_key,
            initial_profile=profile,
            viewport_scale=FLOATING_VIEW_SIZE / (FLOATING_FRAME_SIZE - 14),
        )
        layout.addWidget(self.view)
        self.view.installEventFilter(self)
        self._position_timer = QTimer(self)
        self._position_timer.setTimerType(Qt.TimerType.PreciseTimer)
        # 60 Hz đủ khớp màn hình và giảm một nửa số lần move widget trong compositor.
        self._position_timer.setInterval(16)
        self._position_timer.timeout.connect(self._animate_position)
        self.view.set_rendering_active(True)

    def set_selected(self, selected: bool) -> None:
        """Đổi viền chọn và ưu tiên FPS cho model đang nhận cử chỉ tay."""
        active = bool(selected)
        self.setProperty("selected", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.view.set_render_fps(self._active_fps if active else min(24, self._active_fps))
        if active:
            self.raise_()

    def move_clamped(self, position: QPoint) -> None:
        """Di chuyển hologram tới vị trí đã kẹp theo kích thước HUD hiện tại."""
        parent = self.parentWidget()
        if parent is None:
            return
        clamped = clamp_floating_position(
            position,
            parent.size(),
            self.size(),
            anchor_size=QSize(FLOATING_FRAME_SIZE, FLOATING_FRAME_SIZE),
        )
        self._target_x = float(clamped.x())
        self._target_y = float(clamped.y())
        self._position_timer.stop()
        self.move(clamped)

    def apply_hand_translation(self, move_x: float, move_y: float) -> None:
        """Đổi delta lòng bàn tay chuẩn hóa thành vị trí HUD đích có nội suy mượt."""
        if not move_x and not move_y:
            return
        parent = self.parentWidget()
        if parent is None:
            return
        horizontal = float(move_x) * parent.width() * 1.35
        vertical = float(move_y) * parent.height() * 1.35
        requested = QPoint(
            round(self._target_x + horizontal),
            round(self._target_y + vertical),
        )
        clamped = clamp_floating_position(
            requested,
            parent.size(),
            self.size(),
            anchor_size=QSize(FLOATING_FRAME_SIZE, FLOATING_FRAME_SIZE),
        )
        self._target_x = float(clamped.x())
        self._target_y = float(clamped.y())
        if not self._position_timer.isActive():
            self._last_position_at = time.monotonic()
            self._position_timer.start()

    def shutdown(self) -> None:
        """Dừng timer OpenGL và hủy widget khi model được đóng."""
        self.view.release_gesture()
        self._position_timer.stop()
        self.view.set_rendering_active(False)
        self.hide()
        self.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Biến kéo chuột trên viewport thành kéo hologram thay vì xoay camera mặc định."""
        if watched is self.view and isinstance(event, QMouseEvent):
            if event.type() is QEvent.Type.MouseButtonPress:
                return self._begin_drag(event)
            if event.type() is QEvent.Type.MouseMove:
                return self._continue_drag(event)
            if event.type() is QEvent.Type.MouseButtonRelease:
                return self._finish_drag(event)
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Cho phép vùng viền mảnh cũng chọn và kéo được hologram."""
        if self._begin_drag(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Tiếp tục kéo khi con trỏ đi qua vùng viền của hologram."""
        if self._continue_drag(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Kết thúc kéo trên vùng viền và trả con trỏ về hình bàn tay mở."""
        if self._finish_drag(event):
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Vẽ bốn góc chọn mảnh thay cho khung kín để model vẫn có cảm giác tách nền."""
        super().paintEvent(event)
        if not bool(self.property("selected")):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(42, 222, 255, 150), 1.2))
        inset = round((self.width() - FLOATING_FRAME_SIZE) / 2)
        length = 24
        right = inset + FLOATING_FRAME_SIZE
        bottom = inset + FLOATING_FRAME_SIZE
        for first, second in (
            (QPoint(inset, inset + length), QPoint(inset, inset)),
            (QPoint(inset, inset), QPoint(inset + length, inset)),
            (QPoint(right - length, inset), QPoint(right, inset)),
            (QPoint(right, inset), QPoint(right, inset + length)),
            (QPoint(inset, bottom - length), QPoint(inset, bottom)),
            (QPoint(inset, bottom), QPoint(inset + length, bottom)),
            (QPoint(right - length, bottom), QPoint(right, bottom)),
            (QPoint(right, bottom), QPoint(right, bottom - length)),
        ):
            painter.drawLine(first, second)

    def _begin_drag(self, event: QMouseEvent) -> bool:
        """Ghi offset chuột toàn cục để bắt đầu kéo không làm widget nhảy vị trí."""
        if event.button() is not Qt.MouseButton.LeftButton:
            return False
        self.selected.emit(self.model_key)
        self._position_timer.stop()
        self._target_x = float(self.x())
        self._target_y = float(self.y())
        self._drag_offset = event.globalPosition().toPoint() - self.mapToGlobal(QPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()
        return True

    def _animate_position(self) -> None:
        """Nội suy vị trí hologram ở nhịp cao để che bước landmark webcam thưa."""
        now = time.monotonic()
        elapsed = max(0.0, min(0.05, now - self._last_position_at))
        self._last_position_at = now
        interpolation = 1.0 - math.exp(-24.0 * elapsed)
        next_x = self.x() + (self._target_x - self.x()) * interpolation
        next_y = self.y() + (self._target_y - self.y()) * interpolation
        if abs(self._target_x - next_x) < 0.6 and abs(self._target_y - next_y) < 0.6:
            next_x = self._target_x
            next_y = self._target_y
            self._position_timer.stop()
        self.move(round(next_x), round(next_y))

    def _continue_drag(self, event: QMouseEvent) -> bool:
        """Áp dụng vị trí kéo mới khi nút trái vẫn đang được giữ."""
        if self._drag_offset is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return False
        parent = self.parentWidget()
        if parent is None:
            return False
        global_top_left = event.globalPosition().toPoint() - self._drag_offset
        self.move_clamped(parent.mapFromGlobal(global_top_left))
        event.accept()
        return True

    def _finish_drag(self, event: QMouseEvent) -> bool:
        """Xóa trạng thái kéo sau khi người dùng thả nút chuột trái."""
        if event.button() is not Qt.MouseButton.LeftButton or self._drag_offset is None:
            return False
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()
        return True


class FloatingModelManager(QObject):
    """Quản lý nhiều hologram trong HUD và chuyển gesture tới model đang chọn."""

    selection_changed = Signal(str)
    models_changed = Signal(object)

    def __init__(
        self,
        parent: QWidget,
        catalog: ModelCatalog,
        render_fps: int = 120,
    ) -> None:
        """Gắn manager vào HUD và chuẩn bị thư viện model cùng profile hiệu năng."""
        super().__init__(parent)
        self.container = parent
        self.catalog = catalog
        self.render_fps = max(30, min(120, int(render_fps)))
        self._widgets: dict[str, FloatingHologram] = {}
        self._active_key: str | None = None
        self._compositor_probe: HologramView | None = None
        self.container.installEventFilter(self)

    def prepare_compositor(self) -> None:
        """Tạo sẵn GL child trong suốt để model đầu không buộc cửa sổ Windows dựng lại."""
        if self._compositor_probe is not None:
            return
        probe = HologramView(
            self.container,
            render_fps=30,
            transparent=True,
            show_grid=False,
            initial_model_key=None,
        )
        probe.setFixedSize(2, 2)
        probe.move(0, 0)
        probe.set_rendering_active(False)
        probe.show()
        probe.lower()
        self._compositor_probe = probe

    def dispose(self) -> None:
        """Dừng cả hologram và GL probe khi cửa sổ ARIS thật sự đóng."""
        self.close_all()
        if self._compositor_probe is not None:
            self._compositor_probe.set_rendering_active(False)
            self._compositor_probe.hide()
            self._compositor_probe.deleteLater()
            self._compositor_probe = None

    @property
    def model_keys(self) -> tuple[str, ...]:
        """Trả danh sách khóa model đang mở theo thứ tự chúng được tạo."""
        return tuple(self._widgets)

    @property
    def active_key(self) -> str | None:
        """Trả khóa model đang nhận cử chỉ hoặc None khi HUD không có model."""
        return self._active_key

    @property
    def active_view(self) -> HologramView | None:
        """Trả viewport đang được chọn để probe hoặc điều khiển cử chỉ."""
        widget = self._widgets.get(self._active_key or "")
        return widget.view if widget is not None else None

    @property
    def has_models(self) -> bool:
        """Cho biết HUD hiện có ít nhất một hologram đang mở hay không."""
        return bool(self._widgets)

    def open_model(
        self,
        model_key: str,
        profile: HandProfile | None = None,
    ) -> FloatingHologram:
        """Mở model mới hoặc chọn lại model cùng khóa nếu nó đã tồn tại."""
        existing = self._widgets.get(model_key)
        if existing is not None:
            self.select_model(model_key)
            return existing

        display_name = "Scanned Hand"
        if model_key != "hand_scan":
            display_name = self.catalog.get(model_key).display_name
        widget = FloatingHologram(
            model_key,
            display_name,
            self.container,
            render_fps=self.render_fps,
            profile=profile,
        )
        widget.selected.connect(self.select_model)
        self._widgets[model_key] = widget
        widget.move_clamped(self._initial_position(widget.size()))
        widget.show()
        self.select_model(model_key)
        self.models_changed.emit(self.model_keys)
        return widget

    def select_model(self, model_key: str) -> bool:
        """Chọn model theo khóa và hạ FPS các hologram nền để giữ tổng thể mượt."""
        if model_key not in self._widgets:
            return False
        previous = self._widgets.get(self._active_key or "")
        if previous is not None and previous.model_key != model_key:
            previous.view.release_gesture()
        self._active_key = model_key
        for key, widget in self._widgets.items():
            widget.set_selected(key == model_key)
        self.selection_changed.emit(model_key)
        return True

    def close_model(self, model_key: str | None = None) -> bool:
        """Đóng model theo tên hoặc model đang chọn rồi chọn hologram gần nhất còn lại."""
        target = model_key or self._active_key
        if target is None:
            return False
        widget = self._widgets.pop(target, None)
        if widget is None:
            return False
        widget.shutdown()
        if self._active_key == target:
            self._active_key = next(reversed(self._widgets), None)
        if self._active_key is not None:
            self.select_model(self._active_key)
        else:
            self.selection_changed.emit("")
        self.models_changed.emit(self.model_keys)
        return True

    def close_all(self) -> None:
        """Đóng toàn bộ hologram và dừng các timer OpenGL của chúng."""
        for widget in tuple(self._widgets.values()):
            widget.shutdown()
        self._widgets.clear()
        self._active_key = None
        self.selection_changed.emit("")
        self.models_changed.emit(self.model_keys)

    def apply_gesture(self, yaw: float, pitch: float, zoom: float) -> None:
        """Chuyển gesture legacy tới duy nhất model đang được chọn."""
        view = self.active_view
        if view is not None:
            view.apply_gesture(yaw, pitch, zoom)

    def apply_grab_gesture(self, frame: GrabGestureFrame) -> None:
        """Chuyển grab–drag–release tới duy nhất model đang được chọn."""
        view = self.active_view
        if view is not None:
            view.apply_grab_gesture(frame)

    def apply_spatial_gesture(self, frame: SpatialGestureFrame) -> None:
        """Di chuyển widget bằng tay mở hoặc biến đổi model bằng pinch đang khóa."""
        widget = self._widgets.get(self._active_key or "")
        if widget is None:
            return
        widget.view.apply_spatial_gesture(frame)
        if frame.mode is SpatialGestureMode.MOVE:
            widget.apply_hand_translation(frame.move_x, frame.move_y)

    def adjust_model_zoom(
        self,
        operation: str,
        percent: int,
        model_key: str | None = None,
    ) -> str | None:
        """Phóng/thu model được gọi tên hoặc model đang chọn và trả khóa đã đổi."""
        target = model_key or self._active_key
        widget = self._widgets.get(target or "")
        if widget is None:
            return None
        self.select_model(widget.model_key)
        magnitude = max(1, min(100, int(percent)))
        signed_percent = magnitude if operation == "in" else -magnitude
        widget.view.adjust_zoom_percent(signed_percent)
        return widget.model_key

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Kẹp lại mọi hologram khi cửa sổ ARIS được thay đổi kích thước."""
        if watched is self.container and event.type() is QEvent.Type.Resize:
            for widget in self._widgets.values():
                widget.move_clamped(widget.pos())
        return super().eventFilter(watched, event)

    def _initial_position(self, widget_size: QSize) -> QPoint:
        """Đặt mọi model mới đúng giữa lõi ARIS để người dùng tự đưa nó sang vị trí muốn."""
        return centered_floating_position(self.container.size(), widget_size)
