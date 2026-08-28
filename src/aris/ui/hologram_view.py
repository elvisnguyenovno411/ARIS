from __future__ import annotations

import math
import time

from pyqtgraph import opengl as gl
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor

from aris.models.geometry import SceneBlueprint
from aris.models.scene_factory import SceneFactory
from aris.vision.gesture_motion import (
    AutoRotateController,
    GestureMomentum,
    RotationSpring,
    clamp_zoom_distance,
    zoom_distance_by_percent,
)
from aris.vision.grab_gesture import GrabGestureFrame
from aris.vision.hand_geometry import HandProfile
from aris.vision.spatial_gesture import SpatialGestureFrame, SpatialGestureMode


class HologramView(gl.GLViewWidget):
    """Render scene low-poly bằng OpenGL và nhận xoay/zoom từ chuột hoặc cử chỉ."""

    model_changed = Signal(str)

    def __init__(
        self,
        parent=None,
        render_fps: int = 60,
        transparent: bool = False,
        show_grid: bool = True,
        initial_model_key: str | None = "rasengan",
        initial_profile: HandProfile | None = None,
        viewport_scale: float = 1.0,
    ) -> None:
        """Khởi tạo viewport và chỉ dựng model ban đầu một lần nếu khóa được cung cấp."""
        super().__init__(parent)
        self._transparent = bool(transparent)
        self._show_grid = bool(show_grid)
        self._viewport_scale = max(1.0, float(viewport_scale))
        self._render_fps = max(30, min(120, int(render_fps)))
        if self._transparent:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
            self.setAutoFillBackground(False)
            self.setBackgroundColor(QColor(0, 0, 0, 0))
        else:
            self.setBackgroundColor(QColor("#02090f"))
        self.factory = SceneFactory()
        self.current_key = initial_model_key or ""
        self.hand_profile = initial_profile
        self._azimuth = -90.0
        self._elevation = 16.0
        self._distance = 12.0
        self._default_distance = 12.0
        self._target_azimuth = self._azimuth
        self._target_elevation = self._elevation
        self._target_distance = self._distance
        self._auto_rotation = AutoRotateController(resume_delay_seconds=5.0)
        self._gesture_motion = GestureMomentum()
        self._rotation_spring = RotationSpring()
        self._gesture_mode = "legacy"
        self._grab_active = False
        self._pointing_active = False
        self._last_animation_at = time.monotonic()
        self._reveal_started_at = self._last_animation_at
        self._last_gesture_at: float | None = None
        self._scene_items: list[object] = []
        self._model_items: list[object] = []
        self._animated_items: list[object] = []
        self._model_root: GLGraphicsItem | None = None
        self._timer = QTimer(self)
        # Timer render nội suy transform nhẹ; MediaPipe vẫn ở worker để UI không bị block.
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(max(8, round(1000 / self._render_fps)))
        self._timer.timeout.connect(self._animate)
        if initial_model_key is not None:
            self.show_model(initial_model_key, initial_profile)

    @property
    def target_camera_distance(self) -> float:
        """Trả camera distance đích để probe xác nhận lệnh zoom đã được áp dụng."""
        return self._target_distance

    @property
    def is_auto_rotating(self) -> bool:
        """Cho biết model đang tự xoay hay đang tạm dừng vì cử chỉ/countdown."""
        return self._auto_rotation.is_rotating

    def auto_rotate_remaining_seconds(self, now: float | None = None) -> float:
        """Trả countdown còn lại trước khi model tiếp tục tự xoay."""
        return self._auto_rotation.remaining_seconds(now)

    def set_rendering_active(self, enabled: bool) -> None:
        """Chỉ chạy render loop khi panel hologram hiện để tránh dùng GPU ngầm ở trang logo."""
        if enabled:
            self._last_animation_at = time.monotonic()
            if not self._timer.isActive():
                self._timer.start()
            self.update()
        else:
            self._timer.stop()

    def set_render_fps(self, render_fps: int) -> None:
        """Đổi nhịp render an toàn để ưu tiên model được chọn và tiết kiệm GPU nền."""
        # View đang chọn luôn truyền >=30; cho view nền xuống 24 để nhiều model không
        # tranh GPU nhưng chuyển động tự xoay vẫn liên tục nhờ dt độc lập frame rate.
        self._render_fps = max(15, min(120, int(render_fps)))
        self._timer.setInterval(max(8, round(1000 / self._render_fps)))

    def release_gesture(self) -> None:
        """Dừng quán tính gesture hiện tại khi model mất lựa chọn hoặc bị đóng."""
        self._gesture_motion.reset()
        self._rotation_spring.reset()
        self._grab_active = False
        self._pointing_active = False
        self._last_gesture_at = None

    def show_model(self, model_key: str, profile: HandProfile | None = None) -> None:
        """Xóa scene cũ, dựng model theo khóa và giữ profile tay nếu được cung cấp."""
        if profile is not None:
            self.hand_profile = profile
        self.current_key = model_key
        blueprint = self.factory.build(model_key, self.hand_profile)
        self._load_blueprint(blueprint)
        self.model_changed.emit(model_key)

    def show_scanned_hand(self, profile: HandProfile) -> None:
        """Hiển thị model tay hologram vừa quét dù nó không nằm trong thư viện sáu model."""
        self.hand_profile = profile
        self.current_key = "hand_scan"
        blueprint = self.factory.build("hand_scan", profile)
        self._load_blueprint(blueprint)
        self.model_changed.emit("hand_scan")

    def apply_gesture(self, yaw: float, pitch: float, zoom: float) -> None:
        """Giữ cơ chế legacy: đổi delta chỉ tay thành quán tính orbit camera và zoom."""
        self._gesture_mode = "legacy"
        self._grab_active = False
        now = time.monotonic()
        if yaw or pitch or zoom:
            self._auto_rotation.note_gesture_activity(now)
        elapsed = now - self._last_gesture_at if self._last_gesture_at is not None else 1 / 30
        self._last_gesture_at = now
        if yaw or pitch:
            self._gesture_motion.push(yaw, pitch, elapsed)
        self._target_distance = clamp_zoom_distance(self._target_distance, zoom)

    def apply_grab_gesture(self, frame: GrabGestureFrame) -> None:
        """Áp dụng pinch nắm/kéo/thả vào model và giữ vận tốc cuối để tạo quán tính."""
        self._gesture_mode = "grab_throw"
        now = time.monotonic()
        if (
            frame.grabbed
            or frame.just_grabbed
            or frame.just_released
            or frame.pointing
            or frame.yaw
            or frame.pitch
            or frame.zoom
        ):
            self._auto_rotation.note_gesture_activity(now)
        elapsed = now - self._last_gesture_at if self._last_gesture_at is not None else 1 / 30
        self._last_gesture_at = now

        if frame.just_grabbed:
            # Grab mới bắt đầu sẽ triệt quán tính cũ để model bám ngay vào tay người dùng.
            self._gesture_motion.reset()
            self._rotation_spring.reset()
            self._grab_active = True
            self._pointing_active = False
        if frame.yaw or frame.pitch:
            # Pointing điều khiển trực tiếp; grab drag mới nạp vận tốc để release có quán tính.
            if frame.pointing and not frame.grabbed:
                if not self._pointing_active:
                    self._gesture_motion.reset()
                self._pointing_active = True
            else:
                self._pointing_active = False
                self._gesture_motion.push(frame.yaw, frame.pitch, elapsed)
            self._rotation_spring.push(frame.yaw, frame.pitch)
        elif not frame.grabbed:
            self._pointing_active = False
        if frame.just_released:
            self._grab_active = False
            self._pointing_active = False
        elif frame.grabbed:
            self._grab_active = True
        self._target_distance = clamp_zoom_distance(self._target_distance, frame.zoom)

    def apply_spatial_gesture(self, frame: SpatialGestureFrame) -> None:
        """Áp dụng pinch chỉ xoay ngang; bỏ qua hoàn toàn pitch và zoom từ camera."""
        self._gesture_mode = "spatial"
        now = time.monotonic()
        if frame.mode is not SpatialGestureMode.NEUTRAL or frame.just_released:
            # Giữ model đứng yên suốt lúc tay đang khóa; release bắt đầu countdown năm giây.
            self._auto_rotation.note_gesture_activity(now)
        elapsed = now - self._last_gesture_at if self._last_gesture_at is not None else 1 / 30
        self._last_gesture_at = now

        if frame.just_started:
            self._gesture_motion.reset()
            self._rotation_spring.reset()
            self._grab_active = frame.mode is SpatialGestureMode.TRANSFORM
            self._pointing_active = False
        if frame.mode is SpatialGestureMode.MOVE:
            self._grab_active = False
            self._pointing_active = False
            return
        if frame.mode is SpatialGestureMode.TRANSFORM:
            self._grab_active = True
            if frame.yaw:
                self._gesture_motion.push(frame.yaw, 0.0, elapsed)
                self._rotation_spring.push(frame.yaw, 0.0)
        if frame.just_released:
            self._grab_active = False
            self._pointing_active = False

    def set_auto_rotate(self, enabled: bool) -> None:
        """Bật/tắt xoay camera chậm dùng để xem model đủ 360 độ."""
        self._auto_rotation.set_enabled(enabled)
        self._target_azimuth = self._azimuth
        self._target_elevation = self._elevation
        self._target_distance = self._distance
        self._gesture_motion.reset()
        self._rotation_spring.reset()
        self._grab_active = False
        self._pointing_active = False
        self._last_gesture_at = None

    def adjust_zoom_percent(self, percent_delta: float) -> float:
        """Phóng/thu model theo phần trăm chính xác và trả khoảng cách camera đích mới."""
        self._target_distance = zoom_distance_by_percent(
            self._target_distance,
            percent_delta,
            minimum=max(2.0, self._default_distance * 0.25),
            maximum=max(8.0, self._default_distance * 2.5),
        )
        return self._target_distance

    def reset_view(self) -> None:
        """Đưa camera và model về góc mặc định nhưng giữ nguyên chế độ điều khiển hiện tại."""
        self._azimuth = -90.0
        self._elevation = 16.0
        self._distance = self._default_distance
        self._target_azimuth = self._azimuth
        self._target_elevation = self._elevation
        self._target_distance = self._distance
        self._gesture_motion.reset()
        self._rotation_spring.reset()
        self._grab_active = False
        self._pointing_active = False
        self._last_gesture_at = None
        self._last_animation_at = time.monotonic()
        if self._model_root is not None:
            # Một transform gốc thay cho hàng chục transform con giúp gesture nhẹ hơn đáng kể.
            self._model_root.resetTransform()
        self.setCameraPosition(
            distance=self._distance,
            elevation=self._elevation,
            azimuth=self._azimuth,
        )

    def _clear_scene(self) -> None:
        """Loại bỏ toàn bộ OpenGL item của model trước khi dựng scene mới."""
        for item in self._scene_items:
            try:
                self.removeItem(item)
            except ValueError:
                pass
        self._scene_items.clear()
        self._model_items.clear()
        self._animated_items.clear()
        self._model_root = None

    def _load_blueprint(self, blueprint: SceneBlueprint) -> None:
        """Chuyển blueprint độc lập UI thành các GLMesh/GLLine/GLScatter item."""
        self._clear_scene()
        if self._show_grid:
            grid = gl.GLGridItem()
            grid.setSize(16, 16, 1)
            grid.setSpacing(1, 1, 1)
            grid.setColor((22, 104, 122, 80))
            grid.translate(0, 0, blueprint.floor_z)
            self.addItem(grid)
            self._scene_items.append(grid)

        # Mọi mảnh model dùng chung một parent transform; xoay model chỉ cần một phép cập nhật.
        self._model_root = GLGraphicsItem()
        self.addItem(self._model_root)
        self._scene_items.append(self._model_root)

        for part in blueprint.parts:
            item = gl.GLMeshItem(
                vertexes=part.mesh.vertices,
                faces=part.mesh.faces,
                color=part.color,
                smooth=part.smooth,
                drawEdges=part.draw_edges,
                edgeColor=part.edge_color,
                shader="shaded",
                glOptions="translucent",
            )
            self.addItem(item)
            item.setParentItem(self._model_root)
            # Danh sách riêng cho phép gesture xoay model mà không xoay grid/camera.
            self._model_items.append(item)
            if any(token in part.name for token in ("shell", "core", "repulsor")):
                self._animated_items.append(item)

        for line in blueprint.lines:
            item = gl.GLLinePlotItem(
                pos=line.points,
                color=line.color,
                width=line.width,
                antialias=True,
                mode=line.mode,
            )
            item.setGLOptions("translucent")
            self.addItem(item)
            item.setParentItem(self._model_root)
            self._model_items.append(item)
            if "orbit" in line.name:
                self._animated_items.append(item)

        for points in blueprint.points:
            item = gl.GLScatterPlotItem(
                pos=points.points,
                color=points.color,
                size=points.size,
                pxMode=True,
            )
            item.setGLOptions("translucent")
            self.addItem(item)
            item.setParentItem(self._model_root)
            self._model_items.append(item)
            self._animated_items.append(item)

        distance_scale = 0.62 * self._viewport_scale if self._transparent else 1.0
        self._default_distance = blueprint.camera_distance * distance_scale
        self._distance = self._default_distance
        self.reset_view()
        if self._transparent:
            # Camera tiến nhẹ từ xa vào model và không đổi kích thước widget.
            self._distance = self._default_distance * 1.72
            self._target_distance = self._default_distance
            self._reveal_started_at = time.monotonic()
            self.setCameraPosition(
                distance=self._distance,
                elevation=self._elevation,
                azimuth=self._azimuth,
            )

    def _rotate_model(self, yaw: float, pitch: float) -> None:
        """Xoay toàn bộ item của model quanh tâm thế giới mà không làm nghiêng lưới nền."""
        if self._model_root is None:
            return
        if yaw:
            self._model_root.rotate(float(yaw), 0, 0, 1, local=False)
        if pitch:
            self._model_root.rotate(float(pitch), 1, 0, 0, local=False)

    def _animate(self) -> None:
        """Tạo chuyển động nhẹ cho camera và các lớp năng lượng mà không đổi mesh."""
        now = time.monotonic()
        # Clamp dt tránh cú nhảy transform nếu cửa sổ từng bị pause hoặc kéo giữa hai màn hình.
        elapsed = max(0.0, min(0.05, now - self._last_animation_at))
        self._last_animation_at = now
        if self._auto_rotation.should_rotate(now):
            self._target_azimuth += 8.5 * elapsed
        elif self._gesture_mode == "legacy":
            rotation = self._gesture_motion.advance(elapsed)
            self._target_azimuth += rotation.yaw
            self._target_elevation = max(
                -75.0, min(75.0, self._target_elevation + rotation.pitch)
            )
        else:
            if not self._grab_active and not self._pointing_active:
                rotation = self._gesture_motion.advance(elapsed)
                self._rotation_spring.push(rotation.yaw, rotation.pitch)
            rotation = self._rotation_spring.advance(elapsed)
            self._rotate_model(rotation.yaw, rotation.pitch)

        camera_changed = any(
            abs(current - target) > 0.001
            for current, target in (
                (self._azimuth, self._target_azimuth),
                (self._elevation, self._target_elevation),
                (self._distance, self._target_distance),
            )
        )
        if camera_changed:
            # Nội suy camera che bước nhảy 30 Hz từ webcam bằng nhịp render gần 60 Hz.
            reveal_age = now - self._reveal_started_at
            settle_rate = 8.5 if reveal_age < 0.72 else 40.0
            interpolation = 1.0 - math.exp(-settle_rate * elapsed)
            self._azimuth += (self._target_azimuth - self._azimuth) * interpolation
            self._elevation += (self._target_elevation - self._elevation) * interpolation
            self._distance += (self._target_distance - self._distance) * interpolation
            self.setCameraPosition(
                distance=self._distance,
                elevation=self._elevation,
                azimuth=self._azimuth,
            )
        if self.current_key == "rasengan":
            for index, item in enumerate(self._animated_items):
                angle = (11.25 + index * 2.5) * elapsed
                try:
                    item.rotate(angle, 0, 0, 1, local=True)
                except TypeError:
                    item.rotate(angle, 0, 0, 1)
        self.update()
