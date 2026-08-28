from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from aris.ui.hud_state import HudMode


def _smoothstep(value: float) -> float:
    """Kẹp và làm mềm một tiến độ nội bộ để tránh đổi tốc độ đột ngột."""
    clamped = max(0.0, min(1.0, float(value)))
    return clamped * clamped * (3.0 - 2.0 * clamped)


def _blend_color(first: QColor, second: QColor, amount: float) -> QColor:
    """Nội suy hai màu để nền chuyển trạng thái âm nhạc mà không bị bật khung hình."""
    blend = max(0.0, min(1.0, float(amount)))
    return QColor(
        round(first.red() + (second.red() - first.red()) * blend),
        round(first.green() + (second.green() - first.green()) * blend),
        round(first.blue() + (second.blue() - first.blue()) * blend),
        round(first.alpha() + (second.alpha() - first.alpha()) * blend),
    )


class TechBackground(QWidget):
    """Vẽ nền công nghệ nhẹ bằng QPainter để không tranh OpenGL context với model."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Khởi tạo grid và các node cố định để animation không tạo cấp phát ngẫu nhiên."""
        super().__init__(parent)
        generator = random.Random(0xA715)
        self._nodes = [
            (generator.random(), generator.random(), generator.uniform(0.35, 1.0))
            for _ in range(34)
        ]
        self._circuits = self._build_circuits(generator)
        self._phase = 0.0
        self._startup_progress = 1.0
        self._security_alert_blend = 0.0
        self._target_security_alert_blend = 0.0
        self._music_blend = 0.0
        self._target_music_blend = 0.0
        self._music_level = 0.0
        self._target_music_level = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def set_animation_active(self, enabled: bool) -> None:
        """Bật nền động ở trang logo và đóng timer khi OpenGL đang che toàn bộ nền."""
        if enabled:
            if not self._timer.isActive():
                self._timer.start()
            self.update()
        else:
            self._timer.stop()

    def set_startup_progress(self, progress: float) -> None:
        """Nhận tiến độ mở màn để ánh sáng và đường mạch lan từ tâm ra ngoài."""
        self._startup_progress = max(0.0, min(1.0, float(progress)))
        self.update()

    def set_security_alert(self, enabled: bool) -> None:
        """Chuyển nền sang cảnh báo đỏ bằng nội suy, không tạo hiệu ứng chớp gây khó chịu."""
        self._target_security_alert_blend = 1.0 if enabled else 0.0
        self.update()

    def set_music_active(self, enabled: bool) -> None:
        """Chuyển nền sang tím–đen khi nhạc phát và trở lại khi tạm dừng."""
        self._target_music_blend = 1.0 if enabled else 0.0
        if not enabled:
            self._target_music_level = 0.0
        self.update()

    def set_music_level(self, level: float) -> None:
        """Nhận biên độ bài hát để ánh tím thở theo nhịp mà không lưu sample."""
        self._target_music_level = max(0.0, min(1.0, float(level)))

    @property
    def startup_progress(self) -> float:
        """Trả tiến độ reveal nền hiện tại phục vụ kiểm thử animation."""
        return self._startup_progress

    def _advance(self) -> None:
        """Dịch pha chậm ở 30 FPS để nền sống động nhưng giữ mức CPU thấp."""
        self._phase += 0.009
        self._security_alert_blend += (
            self._target_security_alert_blend - self._security_alert_blend
        ) * 0.09
        self._music_blend += (self._target_music_blend - self._music_blend) * 0.075
        music_smoothing = 0.52 if self._target_music_level > self._music_level else 0.16
        self._music_level += (
            self._target_music_level - self._music_level
        ) * music_smoothing
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API name
        """Vẽ gradient, lưới phối cảnh và node ánh sáng theo kích thước cửa sổ."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bounds = QRectF(self.rect())
        gradient = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        music_blend = self._music_blend * (1.0 - self._security_alert_blend)
        gradient.setColorAt(
            0.0,
            _blend_color(QColor("#000107"), QColor("#07000f"), music_blend),
        )
        gradient.setColorAt(
            0.46,
            _blend_color(QColor("#020914"), QColor("#160025"), music_blend),
        )
        gradient.setColorAt(
            1.0,
            _blend_color(QColor("#06021a"), QColor("#020006"), music_blend),
        )
        painter.fillRect(bounds, gradient)

        width = max(1.0, bounds.width())
        height = max(1.0, bounds.height())
        center = QPointF(width * 0.5, height * 0.5)
        ambient_glow = QRadialGradient(center, min(width, height) * 0.52)
        ambient_glow.setColorAt(0.0, QColor(15, 111, 160, 42))
        ambient_glow.setColorAt(0.42, QColor(21, 40, 100, 20))
        ambient_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ambient_glow)
        painter.drawRect(bounds)

        if music_blend > 0.002:
            music_alpha = int((32 + self._music_level * 118) * music_blend)
            music_glow = QRadialGradient(center, min(width, height) * 0.67)
            music_glow.setColorAt(0.0, QColor(121, 42, 255, music_alpha))
            music_glow.setColorAt(0.46, QColor(69, 9, 142, int(music_alpha * 0.58)))
            music_glow.setColorAt(1.0, QColor(5, 0, 15, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(music_glow)
            painter.drawRect(bounds)

        if self._security_alert_blend > 0.002:
            pulse = 0.86 + 0.14 * math.sin(self._phase * math.tau * 0.72)
            alert_alpha = int(185 * self._security_alert_blend * pulse)
            alert_glow = QRadialGradient(center, min(width, height) * 0.74)
            alert_glow.setColorAt(0.0, QColor(155, 10, 24, alert_alpha))
            alert_glow.setColorAt(0.48, QColor(94, 3, 18, int(alert_alpha * 0.72)))
            alert_glow.setColorAt(1.0, QColor(30, 0, 8, int(alert_alpha * 0.34)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(alert_glow)
            painter.drawRect(bounds)

        for x_ratio, y_ratio, speed in self._nodes:
            moving_y = (y_ratio + self._phase * speed) % 1.0
            alpha = int(24 + 72 * (0.5 + 0.5 * math.sin((moving_y + speed) * math.tau)))
            painter.setPen(Qt.PenStyle.NoPen)
            alert = self._security_alert_blend
            painter.setBrush(
                QColor(
                    int(42 + (255 - 42) * alert),
                    int(218 + (67 - 218) * alert),
                    int(255 + (74 - 255) * alert),
                    alpha,
                )
            )
            radius = 1.0 + speed * 1.4
            painter.drawEllipse(QPointF(x_ratio * width, moving_y * height), radius, radius)

        self._draw_startup_mask(painter, bounds, center)
        self._draw_circuits(painter, center, min(width, height))

    @staticmethod
    def _build_circuits(generator: random.Random) -> list[tuple[QPointF, ...]]:
        """Tạo sẵn các nhánh mạch chuẩn hóa để mỗi frame chỉ cần scale và vẽ."""
        circuits: list[tuple[QPointF, ...]] = []
        for index in range(12):
            angle = index / 12 * math.tau + generator.uniform(-0.1, 0.1)
            direction = QPointF(math.cos(angle), math.sin(angle))
            tangent = QPointF(-direction.y(), direction.x())
            side_a = generator.uniform(-0.09, 0.09)
            side_b = side_a + generator.uniform(-0.12, 0.12)
            end_radius = generator.uniform(0.52, 0.72)
            circuits.append(
                (
                    QPointF(direction.x() * 0.12, direction.y() * 0.12),
                    QPointF(direction.x() * 0.23, direction.y() * 0.23),
                    QPointF(
                        direction.x() * 0.23 + tangent.x() * side_a,
                        direction.y() * 0.23 + tangent.y() * side_a,
                    ),
                    QPointF(
                        direction.x() * 0.39 + tangent.x() * side_a,
                        direction.y() * 0.39 + tangent.y() * side_a,
                    ),
                    QPointF(
                        direction.x() * 0.39 + tangent.x() * side_b,
                        direction.y() * 0.39 + tangent.y() * side_b,
                    ),
                    QPointF(
                        direction.x() * end_radius + tangent.x() * side_b,
                        direction.y() * end_radius + tangent.y() * side_b,
                    ),
                )
            )
        return circuits

    def _draw_startup_mask(
        self,
        painter: QPainter,
        bounds: QRectF,
        center: QPointF,
    ) -> None:
        """Che nền theo radial alpha để ánh sáng hiện từ lõi thay vì bật toàn màn hình."""
        if self._startup_progress >= 1.0:
            return
        center_reveal = _smoothstep(self._startup_progress / 0.26)
        edge_reveal = _smoothstep((self._startup_progress - 0.22) / 0.78)
        mask = QRadialGradient(center, min(bounds.width(), bounds.height()) * 0.78)
        mask.setColorAt(0.0, QColor(0, 0, 3, int(255 * (1.0 - center_reveal))))
        mask.setColorAt(0.42, QColor(0, 0, 3, int(255 * (1.0 - edge_reveal * 0.74))))
        mask.setColorAt(1.0, QColor(0, 0, 3, int(255 * (1.0 - edge_reveal))))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(mask)
        painter.drawRect(bounds)

    def _draw_circuits(self, painter: QPainter, center: QPointF, extent: float) -> None:
        """Vẽ mạch điện kéo dài theo startup rồi giữ một lớp công nghệ rất mờ ở idle."""
        reveal = _smoothstep((self._startup_progress - 0.2) / 0.58)
        if reveal <= 0.0:
            return
        launch_glow = 1.0 - _smoothstep((self._startup_progress - 0.55) / 0.45)
        alpha = int(36 + 174 * launch_glow)
        pen = QPen(QColor(36, 220, 255, alpha), 1.2 + 0.8 * launch_glow)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        scale = extent * 0.72
        for index, normalized_points in enumerate(self._circuits):
            local_reveal = max(0.0, min(1.0, reveal * 1.18 - index * 0.014))
            if local_reveal <= 0.0:
                continue
            points = [
                QPointF(center.x() + point.x() * scale, center.y() + point.y() * scale)
                for point in normalized_points
            ]
            path, head = self._partial_path(points, local_reveal)
            if self._security_alert_blend > 0.01:
                color = QColor(255, 55 if index % 3 else 82, 68, alpha)
            elif self._music_blend > 0.01:
                music = self._music_blend
                normal = (
                    QColor(118, 82, 255, alpha)
                    if index % 3 == 0
                    else QColor(36, 220, 255, alpha)
                )
                color = _blend_color(normal, QColor(151, 62, 255, alpha), music)
            else:
                color = (
                    QColor(118, 82, 255, alpha)
                    if index % 3 == 0
                    else QColor(36, 220, 255, alpha)
                )
            pen.setColor(color)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            if head is not None and launch_glow > 0.05:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(185, 250, 255, int(220 * launch_glow)))
                painter.drawEllipse(head, 2.0 + launch_glow * 2.0, 2.0 + launch_glow * 2.0)

    @staticmethod
    def _partial_path(
        points: list[QPointF],
        progress: float,
    ) -> tuple[QPainterPath, QPointF | None]:
        """Cắt một polyline theo tỷ lệ tổng chiều dài và trả điểm sáng ở đầu mạch."""
        path = QPainterPath()
        if not points:
            return path, None
        path.moveTo(points[0])
        lengths = [
            math.hypot(b.x() - a.x(), b.y() - a.y())
            for a, b in zip(points, points[1:], strict=False)
        ]
        remaining = sum(lengths) * max(0.0, min(1.0, progress))
        head = points[0]
        for first, second, length in zip(points, points[1:], lengths, strict=False):
            if remaining >= length:
                path.lineTo(second)
                head = second
                remaining -= length
                continue
            ratio = remaining / max(length, 1e-6)
            head = QPointF(
                first.x() + (second.x() - first.x()) * ratio,
                first.y() + (second.y() - first.y()) * ratio,
            )
            path.lineTo(head)
            break
        return path, head


class AudioCoreWidget(QWidget):
    """Vẽ lõi A có thể nhấn và vòng phổ âm thanh phản ứng theo microphone."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, animation_fps: int = 60) -> None:
        """Khởi tạo logo vector, bộ làm mượt spectrum và timer theo FPS được chọn."""
        super().__init__(parent)
        self.setMinimumSize(440, 440)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("ARIS voice core")
        self.setToolTip("Click to start or stop listening")
        self._mode = HudMode.IDLE
        self._monitoring = False
        self._level = 0.0
        self._target_level = 0.0
        self._speech_level = 0.0
        self._target_speech_level = 0.0
        self._effect_level = 0.0
        self._target_effect_level = 0.0
        self._music_active = False
        self._music_level = 0.0
        self._target_music_level = 0.0
        self._music_beat = 0.0
        self._startup_progress = 1.0
        self._bands = [0.0] * 24
        self._target_bands = [0.0] * 24
        self._phase = 0.0
        self._visual_energy = 0.26
        self._speaking_blend = 0.0
        self._listening_blend = 0.0
        generator = random.Random(0xA215)
        self._orbit_specs = [
            (
                generator.uniform(-76.0, 76.0),
                generator.uniform(0.28, 0.82),
                generator.uniform(1.02, 1.42),
                generator.choice((-1.0, 1.0)) * generator.uniform(0.35, 1.05),
                generator.uniform(0.0, 360.0),
            )
            for _ in range(11)
        ]
        self._particles = [
            (
                generator.randrange(len(self._orbit_specs)),
                generator.random(),
                generator.uniform(1.0, 3.0),
            )
            for _ in range(54)
        ]
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(max(8, round(1000 / max(30, min(120, animation_fps)))))
        self._timer.timeout.connect(self._animate)
        self._timer.start()

    def set_animation_active(self, enabled: bool) -> None:
        """Chỉ chạy timer của logo khi trang logo hiện để tránh repaint widget bị che."""
        if enabled:
            if not self._timer.isActive():
                self._timer.start()
            self.update()
        else:
            self._timer.stop()

    def set_mode(self, mode: HudMode) -> None:
        """Cập nhật trạng thái màu/chuyển động của lõi theo state machine."""
        self._mode = mode
        self.update()

    def set_monitoring(self, enabled: bool) -> None:
        """Bật vòng chỉ báo cho biết microphone monitor local đang hoạt động."""
        self._monitoring = bool(enabled)
        self.update()

    def set_audio_level(self, level: float) -> None:
        """Nhận RMS chuẩn hóa và đặt đích nội suy để logo không rung giật."""
        self._target_level = max(0.0, min(1.0, float(level)))

    def set_spectrum(self, bands: list[float]) -> None:
        """Nhận tối đa 24 dải FFT chuẩn hóa dùng cho vòng tần số radial."""
        if not bands:
            return
        values = [max(0.0, min(1.0, float(value))) for value in bands[:24]]
        self._target_bands = values + [0.0] * (24 - len(values))

    def set_speech_level(self, level: float) -> None:
        """Nhận biên độ audio ARIS đang phát để chữ A chuyển động theo đúng nhịp nói."""
        self._target_speech_level = max(0.0, min(1.0, float(level)))

    def set_effect_level(self, level: float) -> None:
        """Nhận biên độ cue startup/model để lõi A phản ứng mà không giả là đang nói."""
        self._target_effect_level = max(0.0, min(1.0, float(level)))

    def set_music_active(self, enabled: bool) -> None:
        """Bật trạng thái vòng nhạc; dừng/tạm dừng sẽ làm nhịp hạ mượt về 0."""
        self._music_active = bool(enabled)
        if not enabled:
            self._target_music_level = 0.0
        self.update()

    def set_music_level(self, level: float) -> None:
        """Nhận mức nhạc và tạo xung transient để vòng năng lượng nảy mạnh theo beat."""
        value = max(0.0, min(1.0, float(level)))
        rise = max(0.0, value - self._target_music_level)
        self._music_beat = max(self._music_beat, min(1.0, value * 0.62 + rise * 3.4))
        self._target_music_level = value

    def set_startup_progress(self, progress: float) -> None:
        """Nhận tiến độ startup để chữ A sáng trước, sau đó mới mở các vòng HUD."""
        self._startup_progress = max(0.0, min(1.0, float(progress)))
        self.update()

    @property
    def startup_progress(self) -> float:
        """Trả tiến độ reveal lõi hiện tại phục vụ kiểm thử và chụp frame."""
        return self._startup_progress

    @property
    def visual_energy(self) -> float:
        """Trả về phong bì năng lượng đã làm mượt để kiểm tra chuyển trạng thái logo."""
        return self._visual_energy

    @property
    def monitor_dash_offset(self) -> float:
        """Trả về offset vòng tím liên tục, không reset khi pha vượt qua một chu kỳ."""
        return -self._phase * 50.0

    def _animate(self) -> None:
        """Nội suy audio và pha phát sáng ở 60 FPS để chuyển động liền mạch."""
        speaking_target = 1.0 if self._mode is HudMode.SPEAKING else 0.0
        listening_target = 1.0 if self._mode is HudMode.LISTENING else 0.0
        self._speaking_blend += (speaking_target - self._speaking_blend) * 0.075
        self._listening_blend += (listening_target - self._listening_blend) * 0.1
        energy_targets = {
            HudMode.IDLE: 0.26,
            HudMode.LISTENING: 0.44,
            HudMode.THINKING: 0.5,
            HudMode.SPEAKING: 0.58,
            HudMode.MODEL: 0.3,
            HudMode.ERROR: 0.44,
            HudMode.ALERT: 0.56,
        }
        target_energy = energy_targets[self._mode]
        if self._mode is HudMode.SPEAKING:
            target_energy += self._speech_level * 0.3
        if self._music_active:
            target_energy = max(
                target_energy,
                0.5 + self._music_level * 0.24 + self._music_beat * 0.2,
            )
        self._visual_energy += (target_energy - self._visual_energy) * 0.055
        phase_step = (
            0.008
            + self._speaking_blend * 0.006
            + self._listening_blend * 0.002
            + (0.006 + self._music_level * 0.006 if self._music_active else 0.0)
        )
        # Không reset pha tổng ở 1.0; từng chuyển động tự modulo sau khi nhân tốc độ riêng.
        self._phase += phase_step
        self._level += (self._target_level - self._level) * 0.24
        speech_smoothing = 0.38 if self._target_speech_level > self._speech_level else 0.16
        self._speech_level += (
            self._target_speech_level - self._speech_level
        ) * speech_smoothing
        effect_smoothing = 0.5 if self._target_effect_level > self._effect_level else 0.2
        self._effect_level += (
            self._target_effect_level - self._effect_level
        ) * effect_smoothing
        music_smoothing = 0.58 if self._target_music_level > self._music_level else 0.18
        self._music_level += (
            self._target_music_level - self._music_level
        ) * music_smoothing
        self._music_beat *= 0.86
        for index, target in enumerate(self._target_bands):
            self._bands[index] += (target - self._bands[index]) * 0.3
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API name
        """Phát signal duy nhất khi người dùng nhấn chuột trái vào lõi ARIS."""
        if event.button() is Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API name
        """Vẽ spectrum, vòng trạng thái và chữ A vector theo tỉ lệ widget."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = QPointF(self.width() / 2, self.height() / 2)
        extent = min(self.width(), self.height())
        base_radius = extent * 0.225

        orbit_reveal = _smoothstep((self._startup_progress - 0.1) / 0.56)
        logo_reveal = _smoothstep(self._startup_progress / 0.22)
        self._draw_startup_wave(painter, center, base_radius)
        painter.save()
        painter.setOpacity(orbit_reveal)
        self._draw_energy_orb(painter, center, base_radius)
        self._draw_spectrum(painter, center, base_radius)
        self._draw_state_rings(painter, center, base_radius)
        painter.restore()
        painter.save()
        painter.setOpacity(logo_reveal)
        self._draw_logo(painter, center, extent * 0.082)
        painter.restore()

    def _draw_startup_wave(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Phát một vòng sáng từ chữ A ra HUD đúng pha power-up của opening cue."""
        progress = (self._startup_progress - 0.12) / 0.72
        if not 0.0 < progress < 1.0:
            return
        eased = _smoothstep(progress)
        wave_radius = radius * (0.34 + eased * 3.35)
        alpha = int(math.sin(progress * math.pi) * (130 + self._effect_level * 105))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(52, 229, 255, alpha), 1.4 + 2.0 * (1.0 - eased)))
        painter.drawEllipse(center, wave_radius, wave_radius)
        painter.setPen(QPen(QColor(111, 76, 255, max(0, alpha // 2)), 5.0))
        painter.drawEllipse(center, wave_radius * 0.985, wave_radius * 0.985)

    def _draw_energy_orb(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Vẽ lõi năng lượng nhiều quỹ đạo cyan–purple theo tham chiếu nhưng giữ bản sắc ARIS."""
        idle_breath = 0.025 * math.sin((self._phase * 1.35 % 1.0) * math.tau)
        voice_pulse = (
            self._speaking_blend
            * 0.09
            * math.sin((self._phase * 3.0 % 1.0) * math.tau)
        )
        music_pulse = self._music_beat * 0.2 if self._music_active else 0.0
        energy = max(
            self._level * 1.35,
            self._speech_level * 1.18,
            self._effect_level * 1.24,
            self._music_level * 1.12 if self._music_active else 0.0,
            self._visual_energy + idle_breath + voice_pulse + music_pulse,
        )
        energy = max(0.0, min(1.0, energy))
        glow_radius = radius * (1.48 + energy * 0.1)
        glow = QRadialGradient(center, glow_radius)
        glow.setColorAt(0.0, QColor(210, 254, 255, 215))
        glow.setColorAt(0.08, QColor(35, 229, 255, 180 + int(50 * energy)))
        glow.setColorAt(0.28, QColor(26, 117, 255, 75 + int(55 * energy)))
        glow.setColorAt(0.58, QColor(98, 50, 255, 32 + int(35 * energy)))
        glow.setColorAt(1.0, QColor(4, 9, 24, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, glow_radius, glow_radius)

        for index, (tilt, eccentricity, scale, speed, offset) in enumerate(self._orbit_specs):
            painter.save()
            painter.translate(center)
            rotation = tilt + (self._phase * speed % 1.0) * 360.0
            painter.rotate(rotation)
            orbit_radius = radius * scale * (
                1.0 + energy * 0.025 + self._music_beat * 0.075
            )
            rect = QRectF(
                -orbit_radius,
                -orbit_radius * eccentricity,
                orbit_radius * 2.0,
                orbit_radius * eccentricity * 2.0,
            )
            cyan = index % 3 != 0
            color = (
                QColor(55, 229, 255, 105 + int(90 * energy))
                if cyan
                else QColor(119, 75, 255, 90 + int(80 * energy))
            )
            pen = QPen(color, 0.9 + (index % 4) * 0.35)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            start = int((offset + (self._phase * speed % 2.0) * 180.0) * 16)
            painter.drawArc(rect, start, int((116 + index * 7) * 16))
            painter.drawArc(rect, start + 190 * 16, int((42 + index * 5) * 16))
            painter.restore()

        painter.setPen(Qt.PenStyle.NoPen)
        for orbit_index, offset, size in self._particles:
            tilt, eccentricity, scale, speed, _ = self._orbit_specs[orbit_index]
            angle = (offset + self._phase * speed * 1.7) % 1.0 * math.tau
            orbit_radius = radius * scale
            local_x = math.cos(angle) * orbit_radius
            local_y = math.sin(angle) * orbit_radius * eccentricity
            rotation = math.radians(tilt)
            x = local_x * math.cos(rotation) - local_y * math.sin(rotation)
            y = local_x * math.sin(rotation) + local_y * math.cos(rotation)
            alpha = 85 + int(130 * (0.5 + 0.5 * math.sin(angle * 1.7)))
            color = QColor(83, 232, 255, alpha) if orbit_index % 3 else QColor(133, 94, 255, alpha)
            painter.setBrush(color)
            particle_size = size * (
                1.0 + energy * 0.45 + self._music_beat * 0.75
            )
            painter.drawEllipse(
                QPointF(center.x() + x, center.y() + y),
                particle_size,
                particle_size,
            )

        core_radius = radius * (0.29 + energy * 0.035)
        core = QRadialGradient(center, core_radius)
        core.setColorAt(0.0, QColor(255, 255, 255, 255))
        core.setColorAt(0.18, QColor(173, 251, 255, 245))
        core.setColorAt(0.58, QColor(29, 204, 255, 205))
        core.setColorAt(1.0, QColor(49, 45, 255, 42))
        painter.setBrush(core)
        painter.drawEllipse(center, core_radius, core_radius)

    def _draw_spectrum(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Vẽ 48 thanh đối xứng từ 24 band để vòng âm thanh cân bằng quanh logo."""
        mode_gain = 0.14 + self._listening_blend * 0.86 + self._speaking_blend * 0.54
        for index in range(48):
            source_index = index if index < 24 else 47 - index
            value = self._bands[source_index] * mode_gain
            if self._music_active:
                music_shape = 0.52 + 0.48 * math.sin(index * 0.83 + self._phase * 8.0)
                value = max(
                    value,
                    self._music_level * (0.24 + music_shape * 0.34)
                    + self._music_beat * (0.36 + music_shape * 0.42),
                )
            speaking_wave = self._speaking_blend * 0.12 * (
                0.5
                + 0.5
                * math.sin((self._phase * 4.0 % 1.0) * math.tau + index * 0.45)
            )
            ambient = 0.025 + speaking_wave + 0.018 * math.sin(
                (self._phase % 1.0) * math.tau + index * 0.7
            )
            length = 4.0 + (value + ambient) * radius * 0.25
            angle = -math.pi / 2 + index / 48 * math.tau
            spectrum_radius = radius * 1.46
            inner = QPointF(
                center.x() + math.cos(angle) * spectrum_radius,
                center.y() + math.sin(angle) * spectrum_radius,
            )
            outer = QPointF(
                center.x() + math.cos(angle) * (spectrum_radius + length),
                center.y() + math.sin(angle) * (spectrum_radius + length),
            )
            alpha = 80 + int(150 * min(1.0, value + self._level * 0.5))
            color = QColor(36, 221, 255, alpha) if index % 3 else QColor(108, 76, 255, alpha)
            active_blend = max(self._listening_blend, self._speaking_blend)
            pen = QPen(color, 1.2 + active_blend * 0.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(inner, outer)

    def _draw_state_rings(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Vẽ vòng monitoring và cung chuyển động khác nhau cho từng trạng thái HUD."""
        if self._mode in {HudMode.ERROR, HudMode.ALERT}:
            primary = QColor(255, 76, 119, 220)
        elif self._mode is HudMode.LISTENING:
            primary = QColor(43, 232, 255, 245)
        elif self._music_active:
            primary = QColor(151, 72, 255, 238)
        else:
            speaking = self._speaking_blend
            primary = QColor(
                int(49 + (117 - 49) * speaking),
                int(188 + (91 - 188) * speaking),
                255,
                int(185 + 50 * speaking),
            )

        pulse = (
            1.0
            + self._level * 0.045
            + self._visual_energy * 0.018
            + self._music_beat * 0.17
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 24), 9))
        painter.drawEllipse(center, radius * 0.72 * pulse, radius * 0.72 * pulse)
        painter.setPen(QPen(primary, 1.4))
        painter.drawEllipse(center, radius * 0.74, radius * 0.74)

        if self._monitoring:
            monitor_color = (
                QColor(255, 58, 72, 220)
                if self._mode is HudMode.ALERT
                else QColor(101, 92, 255, 190)
            )
            monitor_pen = QPen(monitor_color, 2.0)
            monitor_pen.setDashPattern([5.0, 6.0])
            # Offset tăng liên tục; không modulo nên pattern không nhảy về điểm đầu mỗi chu kỳ.
            monitor_pen.setDashOffset(self.monitor_dash_offset)
            painter.setPen(monitor_pen)
            painter.drawEllipse(center, radius * 1.56, radius * 1.56)

        if self._mode is HudMode.THINKING:
            rect = QRectF(
                center.x() - radius * 1.28,
                center.y() - radius * 1.28,
                radius * 2.56,
                radius * 2.56,
            )
            painter.setPen(QPen(QColor(72, 234, 255, 225), 4.0))
            start = int((self._phase % 1.0) * 360 * 16)
            painter.drawArc(rect, start, 92 * 16)
            painter.drawArc(rect, start + 180 * 16, 54 * 16)
        elif self._speaking_blend > 0.01:
            rect = QRectF(
                center.x() - radius * 1.3,
                center.y() - radius * 1.3,
                radius * 2.6,
                radius * 2.6,
            )
            speaking_alpha = int(225 * self._speaking_blend)
            painter.setPen(QPen(QColor(89, 224, 255, speaking_alpha), 3.2))
            start = int(-(self._phase % 1.0) * 360 * 16)
            painter.drawArc(rect, start, 128 * 16)
            painter.setPen(
                QPen(QColor(132, 83, 255, int(205 * self._speaking_blend)), 2.2)
            )
            painter.drawArc(rect, start + 170 * 16, 104 * 16)

    def _draw_logo(self, painter: QPainter, center: QPointF, size: float) -> None:
        """Vẽ biểu tượng A tách thanh ngang theo logo đã duyệt mà không cần bitmap lớn."""
        fallback_rhythm = self._speaking_blend * (
            0.18 + 0.12 * (0.5 + 0.5 * math.sin(self._phase * math.tau * 3.1))
        )
        speech_rhythm = max(self._speech_level, fallback_rhythm)
        startup_scale = 0.68 + _smoothstep(self._startup_progress / 0.3) * 0.32
        startup_bloom = math.sin(min(1.0, self._startup_progress / 0.48) * math.pi) * 0.13
        size *= startup_scale + startup_bloom
        size *= 1.0 + self._speaking_blend * 0.025 + speech_rhythm * 0.115
        size *= 1.0 + self._effect_level * 0.07
        if self._music_active:
            size *= 1.0 + self._music_level * 0.035 + self._music_beat * 0.13
        gradient = QLinearGradient(center.x(), center.y() - size, center.x(), center.y() + size)
        if self._mode is HudMode.ALERT:
            gradient.setColorAt(0.0, QColor("#fff1f3"))
            gradient.setColorAt(0.48, QColor("#ff405b"))
            gradient.setColorAt(1.0, QColor("#8e001e"))
        else:
            gradient.setColorAt(0.0, QColor("#26ddff"))
            gradient.setColorAt(0.55, QColor("#149de8"))
            gradient.setColorAt(1.0, QColor("#6a45ff"))

        glow = QPainterPath()
        glow.addEllipse(center, size * 0.84, size * 0.84)
        painter.setPen(Qt.PenStyle.NoPen)
        logo_level = max(self._level, self._speech_level, self._effect_level)
        painter.setBrush(QColor(18, 186, 255, 18 + int(logo_level * 68)))
        painter.drawPath(glow)

        top = QPointF(center.x(), center.y() - size)
        left_leg = QPolygonF(
            [
                top,
                QPointF(center.x() - size * 0.92, center.y() + size),
                QPointF(center.x() - size * 0.61, center.y() + size),
                QPointF(center.x() + size * 0.04, center.y() - size * 0.46),
            ]
        )
        right_leg = QPolygonF(
            [
                top,
                QPointF(center.x() + size * 0.92, center.y() + size),
                QPointF(center.x() + size * 0.61, center.y() + size),
                QPointF(center.x() - size * 0.04, center.y() - size * 0.46),
            ]
        )
        bar = QPolygonF(
            [
                QPointF(center.x() - size * 0.28, center.y() + size * 0.35),
                QPointF(center.x() + size * 0.28, center.y() + size * 0.35),
                QPointF(center.x() + size * 0.38, center.y() + size * 0.6),
                QPointF(center.x() - size * 0.38, center.y() + size * 0.6),
            ]
        )
        painter.setBrush(gradient)
        painter.drawPolygon(left_leg)
        painter.drawPolygon(right_leg)
        painter.drawPolygon(bar)
