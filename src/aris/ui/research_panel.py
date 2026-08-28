from __future__ import annotations

import math
import time
from urllib.parse import urlparse

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QDesktopServices, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from aris.search.models import SearchResult


class PersistentTypewriterLabel(QLabel):
    """Gõ nội dung tra cứu theo nhịp ổn định rồi giữ text cho đến khi panel đóng."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Tạo timer 60 FPS cho hiệu ứng chữ mà không chặn event loop của HUD."""
        super().__init__(parent)
        self._full_text = ""
        self._position = 0
        self._step = 1
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)

    def show_text(self, text: str, animated: bool = True) -> None:
        """Hiện text ngay hoặc gõ dần; đầu vào được coi là dữ liệu thuần, không phải HTML."""
        self._timer.stop()
        self._full_text = " ".join(text.strip().split())
        self._position = 0
        self._step = max(1, math.ceil(len(self._full_text) / 160))
        self.setTextFormat(Qt.TextFormat.PlainText)
        if not animated or not self._full_text:
            self.setText(self._full_text)
            return
        self.setText("▌")
        self._timer.start()

    def _advance(self) -> None:
        """Thêm một nhóm ký tự và dừng chính xác tại cuối câu trả lời."""
        self._position = min(len(self._full_text), self._position + self._step)
        visible = self._full_text[: self._position]
        if self._position >= len(self._full_text):
            self._timer.stop()
            self.setText(visible)
            return
        self.setText(f"{visible}▌")


class ResearchPanel(QFrame):
    """Hiện kết quả Web Search như một bảng hologram nổi trong cùng cửa sổ ARIS."""

    close_requested = Signal(str)
    selected = Signal(str)

    def __init__(self, panel_id: str, parent: QWidget | None = None) -> None:
        """Dựng một bảng có ID riêng để nhiều kết quả cùng tồn tại trong một HUD."""
        super().__init__(parent)
        self.panel_id = panel_id
        self.setObjectName("ResearchPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(320, 340)
        self.setMaximumSize(520, 620)
        self.resize(420, 460)
        self._scan_phase = 0.0
        self._drag_offset: QPoint | None = None
        self._selected = False
        self._animation_group = None
        self._target_x = float(self.x())
        self._target_y = float(self.y())
        self._last_position_at = time.monotonic()
        self._scroll_target = 0.0
        self._last_scroll_at = time.monotonic()
        self._source_buttons: list[QPushButton] = []
        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(33)
        self._scan_timer.timeout.connect(self._advance_scan)
        self._position_timer = QTimer(self)
        self._position_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._position_timer.setInterval(16)
        self._position_timer.timeout.connect(self._animate_position)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._scroll_timer.setInterval(16)
        self._scroll_timer.timeout.connect(self._animate_scroll)
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        """Sắp xếp header, câu hỏi, nội dung và nguồn trong khung không che logo mặc định."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(11)

        header = QHBoxLayout()
        self.system_label = QLabel("OPENAI // LIVE INTELLIGENCE")
        self.system_label.setObjectName("ResearchSystem")
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("ResearchClose")
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(lambda: self.close_requested.emit(self.panel_id))
        header.addWidget(self.system_label)
        header.addStretch(1)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        self.state_label = QLabel("STANDBY")
        self.state_label.setObjectName("ResearchState")
        layout.addWidget(self.state_label)

        self.query_label = QLabel()
        self.query_label.setObjectName("ResearchQuery")
        self.query_label.setWordWrap(True)
        self.query_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.query_label)

        divider = QFrame()
        divider.setObjectName("ResearchDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("ResearchScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_body = QWidget()
        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(2, 2, 8, 2)
        scroll_layout.setSpacing(10)
        self.answer_label = PersistentTypewriterLabel()
        self.answer_label.setObjectName("ResearchAnswer")
        self.answer_label.setWordWrap(True)
        self.answer_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.answer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll_layout.addWidget(self.answer_label)
        self.sources_title = QLabel("VERIFIED SOURCES")
        self.sources_title.setObjectName("ResearchSourcesTitle")
        scroll_layout.addWidget(self.sources_title)
        for index in range(4):
            button = QPushButton()
            button.setObjectName("ResearchSource")
            button.setProperty("sourceIndex", index + 1)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setVisible(False)
            button.clicked.connect(lambda _checked=False, item=button: self._open_source(item))
            self._source_buttons.append(button)
            scroll_layout.addWidget(button)
        scroll_layout.addStretch(1)
        self.scroll_area.setWidget(scroll_body)
        layout.addWidget(self.scroll_area, 1)

        self.meta_label = QLabel("LOCAL LIMIT ACTIVE · NO HISTORY SAVED")
        self.meta_label.setObjectName("ResearchMeta")
        layout.addWidget(self.meta_label)

    def show_loading(self, query: str) -> None:
        """Mở panel ở trạng thái quét trong lúc worker gọi Web Search."""
        self.query_label.setText(query)
        self.state_label.setText("SCANNING PUBLIC WEB ···")
        self.answer_label.show_text("Đang đối chiếu dữ liệu và nguồn công khai…", animated=False)
        self._reset_scroll()
        self.sources_title.hide()
        for button in self._source_buttons:
            button.hide()
            button.setProperty("sourceUrl", "")
        self.meta_label.setText("OPENAI WEB SEARCH · REQUEST IN PROGRESS")
        self.show()
        self.raise_()
        self._scan_timer.start()

    def show_result(self, result: SearchResult, requests_remaining: int) -> None:
        """Hiện tóm tắt, nguồn và ngân sách phiên mà không đọc hoặc mở link tự động."""
        self.query_label.setText(result.query or "WEB SEARCH")
        if result.success:
            self.state_label.setText("GROUNDED RESPONSE · ONLINE")
            self.answer_label.show_text(result.answer, animated=not result.cached)
        else:
            self.state_label.setText("SEARCH UNAVAILABLE · SAFE FALLBACK")
            self.answer_label.show_text(result.answer, animated=False)
        self._reset_scroll()

        self.sources_title.setVisible(bool(result.sources))
        for index, button in enumerate(self._source_buttons):
            if index >= len(result.sources):
                button.hide()
                button.setProperty("sourceUrl", "")
                continue
            source = result.sources[index]
            button.setText(f"{index + 1:02d}  {source.title}")
            button.setToolTip(source.url)
            button.setProperty("sourceUrl", source.url)
            button.show()
        cache_text = "CACHE" if result.cached else "LIVE"
        self.meta_label.setText(
            f"{cache_text} · {len(result.sources)} SOURCES · "
            f"{max(0, requests_remaining)} REQUESTS LEFT"
        )
        self.show()
        self.raise_()
        self._scan_timer.start()

    def stop(self) -> None:
        """Dừng animation nhẹ và ẩn panel khi đóng thông tin hoặc thoát ARIS."""
        if self._animation_group is not None:
            self._animation_group.stop()
            self._animation_group = None
        self._scan_timer.stop()
        self._position_timer.stop()
        self._scroll_timer.stop()
        self.answer_label.show_text("", animated=False)
        self.hide()

    def set_selected(self, selected: bool) -> None:
        """Đổi màu viền của bảng đang được chọn và đưa nó lên trên các bảng khác."""
        self._selected = bool(selected)
        self._scan_timer.setInterval(33 if self._selected else 66)
        if self._selected:
            self.raise_()
        self.update()

    def animate_in(self) -> None:
        """Materialize bảng từ tâm nhỏ/mờ tới hình học hiện tại trong khoảng 280 ms."""
        final_geometry = self.geometry()
        start_geometry = _scaled_geometry(final_geometry, 0.78)
        self._run_transition(start_geometry, final_geometry, 0.0, 1.0, 280, None)

    def animate_out(self, finished_callback) -> None:
        """Thu nhỏ và làm mờ bảng rồi gọi callback để manager giải phóng widget."""
        start_geometry = self.geometry()
        end_geometry = _scaled_geometry(start_geometry, 0.72)

        def finish() -> None:
            """Ẩn bảng đã de-materialize trước khi manager xóa tham chiếu."""
            self.hide()
            finished_callback()

        self._run_transition(start_geometry, end_geometry, 1.0, 0.0, 230, finish)

    def move_clamped(self, target: QPoint) -> None:
        """Di chuyển bảng tới vị trí mới nhưng luôn giữ toàn bộ khung trong HUD."""
        parent = self.parentWidget()
        if parent is None:
            self._target_x = float(target.x())
            self._target_y = float(target.y())
            self.move(target)
            return
        max_x = max(8, parent.width() - self.width() - 8)
        max_y = max(8, parent.height() - self.height() - 8)
        clamped = QPoint(
            max(8, min(max_x, target.x())),
            max(8, min(max_y, target.y())),
        )
        self._target_x = float(clamped.x())
        self._target_y = float(clamped.y())
        self._position_timer.stop()
        self.move(clamped)

    def apply_hand_translation(self, move_x: float, move_y: float) -> None:
        """Đổi delta bàn tay mở thành vị trí bảng đích có nội suy giống model 3D."""
        if not move_x and not move_y:
            return
        parent = self.parentWidget()
        if parent is None:
            return
        requested = QPoint(
            round(self._target_x + float(move_x) * parent.width() * 1.35),
            round(self._target_y + float(move_y) * parent.height() * 1.35),
        )
        max_x = max(8, parent.width() - self.width() - 8)
        max_y = max(8, parent.height() - self.height() - 8)
        self._target_x = float(max(8, min(max_x, requested.x())))
        self._target_y = float(max(8, min(max_y, requested.y())))
        if not self._position_timer.isActive():
            self._last_position_at = time.monotonic()
            self._position_timer.start()

    def apply_hand_scroll(self, move_y: float) -> None:
        """Cuộn nội dung bảng theo kéo dọc của pinch mà không di chuyển cả widget."""
        if not move_y:
            return
        scrollbar = self.scroll_area.verticalScrollBar()
        maximum = scrollbar.maximum()
        if maximum <= 0:
            return
        if not self._scroll_timer.isActive():
            self._scroll_target = float(scrollbar.value())
        viewport_height = max(240, self.scroll_area.viewport().height())
        self._scroll_target = max(
            0.0,
            min(
                float(maximum),
                self._scroll_target - float(move_y) * viewport_height * 2.4,
            ),
        )
        if not self._scroll_timer.isActive():
            self._last_scroll_at = time.monotonic()
            self._scroll_timer.start()

    def move_to_default(self, parent_size: QSize) -> None:
        """Đặt bảng bên phải lõi và kẹp trong HUD ở mọi mức Windows display scaling."""
        margin = 34
        x_value = max(margin, parent_size.width() - self.width() - margin)
        y_value = max(margin, (parent_size.height() - self.height()) // 2)
        self.move(x_value, y_value)

    def _run_transition(
        self,
        start_geometry: QRect,
        end_geometry: QRect,
        start_opacity: float,
        end_opacity: float,
        duration_ms: int,
        finished_callback,
    ) -> None:
        """Chạy geometry và opacity song song trên UI thread, không tạo timer thủ công."""
        if self._animation_group is not None:
            self._animation_group.stop()
        self._position_timer.stop()
        effect = self.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        effect.setOpacity(start_opacity)
        self.setGeometry(start_geometry)
        self.show()
        self.raise_()

        geometry_animation = QPropertyAnimation(self, b"geometry")
        geometry_animation.setDuration(duration_ms)
        geometry_animation.setStartValue(start_geometry)
        geometry_animation.setEndValue(end_geometry)
        geometry_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        opacity_animation = QPropertyAnimation(effect, b"opacity")
        opacity_animation.setDuration(duration_ms)
        opacity_animation.setStartValue(start_opacity)
        opacity_animation.setEndValue(end_opacity)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(geometry_animation)
        group.addAnimation(opacity_animation)
        if finished_callback is not None:
            group.finished.connect(finished_callback)
        group.finished.connect(self._finish_transition)
        self._animation_group = group
        group.start()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API name
        """Vẽ nền kính, góc khóa và scan-line cyan bằng painter nhẹ."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(5, 5, -5, -5)
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        painter.fillPath(path, QColor(1, 12, 24, 226))
        border = QColor(75, 235, 255, 225) if self._selected else QColor(31, 220, 255, 150)
        painter.setPen(QPen(border, 1.7 if self._selected else 1.1))
        painter.drawPath(path)

        scan_y = rect.top() + int(self._scan_phase * max(1, rect.height()))
        painter.setPen(QPen(QColor(49, 224, 255, 42), 1))
        painter.drawLine(rect.left() + 12, scan_y, rect.right() - 12, scan_y)

        painter.setPen(QPen(QColor(111, 83, 255, 210), 2.0))
        arm = 24
        for x_value, y_value, x_sign, y_sign in (
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ):
            painter.drawLine(x_value, y_value, x_value + x_sign * arm, y_value)
            painter.drawLine(x_value, y_value, x_value, y_value + y_sign * arm)
        super().paintEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API name
        """Cho phép kéo bảng bằng vùng trống nhưng giữ nút nguồn có thể bấm bình thường."""
        if event.button() is Qt.MouseButton.LeftButton and event.position().y() < 74:
            self.selected.emit(self.panel_id)
            self._drag_offset = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API name
        """Di chuyển bảng trong biên HUD khi người dùng kéo phần header."""
        if self._drag_offset is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        parent = self.parentWidget()
        if parent is None:
            return
        target = self.mapToParent(event.position().toPoint() - self._drag_offset)
        self.move_clamped(target)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API name
        """Kết thúc kéo bảng khi thả chuột trái."""
        if event.button() is Qt.MouseButton.LeftButton:
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def _advance_scan(self) -> None:
        """Tiến scan-line theo pha liên tục để bảng có chuyển động nhẹ và không giật."""
        self._scan_phase += 0.0045
        if self._scan_phase >= 1.0:
            self._scan_phase -= 1.0
        self.update()

    def _animate_position(self) -> None:
        """Nội suy vị trí bảng ở nhịp cao để che bước landmark webcam thưa."""
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

    def _animate_scroll(self) -> None:
        """Nội suy thanh cuộn ở nhịp cao để thao tác pinch không giật theo frame camera."""
        scrollbar = self.scroll_area.verticalScrollBar()
        now = time.monotonic()
        elapsed = max(0.0, min(0.05, now - self._last_scroll_at))
        self._last_scroll_at = now
        current = float(scrollbar.value())
        next_value = current + (self._scroll_target - current) * (
            1.0 - math.exp(-28.0 * elapsed)
        )
        if abs(self._scroll_target - next_value) < 0.75:
            next_value = self._scroll_target
            self._scroll_timer.stop()
        scrollbar.setValue(round(next_value))

    def _reset_scroll(self) -> None:
        """Đưa nội dung mới về đầu bảng và xóa quán tính cuộn của kết quả trước."""
        self._scroll_timer.stop()
        self._scroll_target = 0.0
        self.scroll_area.verticalScrollBar().setValue(0)

    def _finish_transition(self) -> None:
        """Đồng bộ đích kéo tay với vị trí cuối animation để bảng không nhảy ngược."""
        self._target_x = float(self.x())
        self._target_y = float(self.y())
        self._animation_group = None

    @staticmethod
    def _open_source(button: QPushButton) -> None:
        """Mở URL do citation trả về chỉ sau cú nhấn rõ ràng và kiểm tra lại giao thức."""
        url = str(button.property("sourceUrl") or "")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(url))


def _scaled_geometry(rectangle: QRect, scale: float) -> QRect:
    """Tạo QRect thu/phóng quanh tâm để animation không nhảy vị trí khi bắt đầu."""
    bounded_scale = max(0.2, min(1.0, float(scale)))
    width = max(1, round(rectangle.width() * bounded_scale))
    height = max(1, round(rectangle.height() * bounded_scale))
    return QRect(
        rectangle.center().x() - width // 2,
        rectangle.center().y() - height // 2,
        width,
        height,
    )
