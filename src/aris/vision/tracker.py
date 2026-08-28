from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal

from aris.vision.camera_lifecycle import CameraLifecycle
from aris.vision.grab_gesture import GrabGestureFrame, GrabGestureInterpreter
from aris.vision.hand_geometry import (
    GestureInterpreter,
    assess_open_palm,
    build_hand_profile,
)
from aris.vision.scan_stability import ScanStability
from aris.vision.spatial_gesture import (
    SpatialGestureFrame,
    SpatialGestureInterpreter,
    SpatialGestureMode,
)

GUIDANCE_EN = {
    "no_hand": "Place one open palm in front of the camera.",
    "move_right": "Move your hand slightly right.",
    "move_left": "Move your hand slightly left.",
    "move_down": "Move your hand slightly down.",
    "move_up": "Move your hand slightly up.",
    "move_closer": "Move your hand closer to the camera.",
    "move_away": "Move your hand farther from the camera.",
    "open_fingers": "Open all four fingers.",
    "separate_fingers": "Separate your fingers slightly.",
    "hold_still": "Good position. Hold still.",
    "moving": "Open-hand move locked. Guide the hologram to a new position.",
    "transforming": "Pinch locked. Move left or right to rotate; voice controls zoom.",
    "grabbed": "Legacy grab locked. Move your hand, then open the pinch to throw.",
    "released": "Gesture released. The selected hologram is ready.",
}

GUIDANCE_VI = {
    "no_hand": "Đưa một lòng bàn tay mở trước camera.",
    "move_right": "Dịch bàn tay sang phải một chút.",
    "move_left": "Dịch bàn tay sang trái một chút.",
    "move_down": "Hạ bàn tay xuống một chút.",
    "move_up": "Nâng bàn tay lên một chút.",
    "move_closer": "Đưa bàn tay gần camera hơn.",
    "move_away": "Đưa bàn tay xa camera hơn.",
    "open_fingers": "Mở đủ bốn ngón tay.",
    "separate_fingers": "Tách các ngón nhẹ ra.",
    "hold_still": "Vị trí tốt. Hãy giữ yên.",
    "moving": "Đã khóa di chuyển năm ngón. Đưa hologram tới vị trí mới.",
    "transforming": "Đã khóa pinch. Đưa trái/phải để xoay; zoom dùng lệnh giọng.",
    "grabbed": "Đã khóa grab cũ. Di chuyển tay rồi mở hai ngón để thả.",
    "released": "Đã thả cử chỉ. Hologram đang chọn đã sẵn sàng.",
}


class VisionController(QObject):
    """Chạy webcam và MediaPipe trong thread nền mà không lưu bất kỳ frame nào."""

    status_changed = Signal(str, str)
    scan_progress = Signal(int)
    scan_completed = Signal(object)
    gesture_delta = Signal(float, float, float)
    grab_gesture = Signal(object)
    spatial_gesture = Signal(object)
    running_changed = Signal(bool)
    fps_sampled = Signal(float)

    def __init__(
        self,
        model_path: Path,
        camera_index: int = 0,
        gesture_mode: str = "spatial",
        target_fps: int = 24,
        inference_size: tuple[int, int] = (640, 480),
    ) -> None:
        """Khởi tạo controller với model local, camera và profile FPS suy luận nhẹ."""
        super().__init__()
        self.model_path = model_path
        self.camera_index = camera_index
        self.gesture_mode = (
            gesture_mode if gesture_mode in {"spatial", "grab_throw", "legacy"} else "spatial"
        )
        self.target_fps = max(12, min(30, int(target_fps)))
        self.inference_size = (
            max(320, min(640, int(inference_size[0]))),
            max(240, min(480, int(inference_size[1]))),
        )
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._demand_event = threading.Event()
        self._lifecycle = CameraLifecycle()
        self._language = "en"
        self._state_lock = threading.Lock()
        self._camera_active = False

    @property
    def is_running(self) -> bool:
        """Cho biết worker nhận diện tay có đang hoạt động hay không."""
        return bool(self._thread and self._thread.is_alive())

    @property
    def is_camera_active(self) -> bool:
        """Cho biết webcam đã mở thành công và đang cấp frame trong RAM hay chưa."""
        with self._state_lock:
            return self._camera_active

    def preload(self) -> None:
        """Nạp MediaPipe nền trước, nhưng chỉ mở webcam khi model hoặc scan cần dùng."""
        self.start()

    def set_language(self, language: str) -> None:
        """Đổi ngôn ngữ câu hướng dẫn camera mà không khởi động lại thread."""
        with self._state_lock:
            self._language = "vi" if language == "vi" else "en"

    def start(self) -> None:
        """Mở camera trong thread nền nếu chưa chạy."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="aris-vision", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.5) -> None:
        """Yêu cầu thread camera dừng và chờ ngắn để giải phóng webcam."""
        # Xóa cả scan và gesture trước khi join để worker thoát dù đang ở giữa một phiên.
        self._lifecycle.clear()
        self._stop_event.set()
        self._demand_event.set()
        thread = self._thread
        if thread and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=timeout)
        self._thread = None

    def request_scan(self) -> None:
        """Bật chế độ tự quét khi tư thế lòng bàn tay đạt chất lượng yêu cầu."""
        self._lifecycle.request_scan()
        self._demand_event.set()
        self.start()

    def set_gesture_enabled(self, enabled: bool) -> None:
        """Bật hoặc tắt phát tín hiệu xoay/zoom từ landmark bàn tay."""
        self._lifecycle.set_gesture_enabled(enabled)
        if enabled:
            self._demand_event.set()
            self.start()
        elif self.gesture_mode == "spatial":
            self.spatial_gesture.emit(SpatialGestureFrame(just_released=True))
        elif self.gesture_mode == "grab_throw":
            self.grab_gesture.emit(GrabGestureFrame(just_released=True))

    def _guidance(self, key: str) -> str:
        """Trả về câu hướng dẫn camera theo ngôn ngữ giao diện hiện tại."""
        with self._state_lock:
            language = self._language
        return (GUIDANCE_VI if language == "vi" else GUIDANCE_EN).get(key, key)

    def _set_camera_active(self, active: bool) -> None:
        """Cập nhật trạng thái webcam thread-safe cho watchdog giao diện."""
        with self._state_lock:
            self._camera_active = active

    def _open_camera(self) -> cv2.VideoCapture | None:
        """Thử các backend Windows và tự kết nối lại khi webcam tạm thời bận."""
        backends = []
        for backend_name in ("CAP_DSHOW", "CAP_MSMF", "CAP_ANY"):
            backend = getattr(cv2, backend_name, None)
            if backend is not None and backend not in backends:
                backends.append(backend)
        attempts = 0
        while not self._stop_event.is_set() and self._lifecycle.should_run:
            for backend in backends:
                capture = cv2.VideoCapture(self.camera_index, backend)
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                capture.set(cv2.CAP_PROP_FPS, 30)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if capture.isOpened():
                    return capture
                capture.release()
            attempts += 1
            if attempts == 1 or attempts % 5 == 0:
                self.status_changed.emit("Camera đang kết nối lại…", "waiting")
            self._stop_event.wait(0.35)
        return None

    def _run(self) -> None:
        """Vòng lặp nội bộ xử lý video local và chỉ phát landmark đã suy ra."""
        landmarker = None
        capture = None
        try:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Missing MediaPipe model: {self.model_path}")
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision

            # Chỉ theo dõi một tay để giảm CPU/độ trễ và tránh điều khiển mơ hồ giữa hai người.
            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(self.model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.42,
                min_hand_presence_confidence=0.42,
                min_tracking_confidence=0.45,
            )
            landmarker = vision.HandLandmarker.create_from_options(options)
            self.status_changed.emit("Vision engine ready.", "idle")
            while not self._stop_event.is_set() and not self._lifecycle.should_run:
                self._demand_event.clear()
                self._demand_event.wait(0.5)
            if self._stop_event.is_set():
                return
            capture = self._open_camera()
            if capture is None:
                return
            self._set_camera_active(True)
            self.running_changed.emit(True)
            self.status_changed.emit("Camera local · privacy mode", "ready")
            legacy_interpreter = GestureInterpreter()
            grab_interpreter = GrabGestureInterpreter()
            spatial_interpreter = SpatialGestureInterpreter()
            stability = ScanStability(required_frames=14)
            last_guidance = ""
            started = time.monotonic()
            next_frame_at = started
            fps_started: float | None = None
            processed_frames = 0
            failed_reads = 0
            while not self._stop_event.is_set():
                # Worker tự thoát ngay khi cả scan và gesture đều không còn cần webcam.
                if not self._lifecycle.should_run:
                    break
                # MediaPipe chạy 24 FPS mặc định; OpenGL tự nội suy 60 FPS để model vẫn mượt.
                wait_seconds = next_frame_at - time.monotonic()
                if wait_seconds > 0 and self._stop_event.wait(wait_seconds):
                    break
                frame_started = time.monotonic()
                frame_interval = 1.0 / self.target_fps
                next_frame_at = max(next_frame_at + frame_interval, frame_started)
                ok, frame = capture.read()
                if not ok:
                    failed_reads += 1
                    if failed_reads < 8:
                        time.sleep(0.08)
                        continue
                    self._set_camera_active(False)
                    self.running_changed.emit(False)
                    capture.release()
                    capture = self._open_camera()
                    if capture is None:
                        break
                    failed_reads = 0
                    self._set_camera_active(True)
                    self.running_changed.emit(True)
                    continue
                failed_reads = 0
                # Thu nhỏ trước khi mirror/color-convert để giảm bản sao RAM và tải MediaPipe.
                inference_frame = cv2.resize(
                    frame,
                    self.inference_size,
                    interpolation=cv2.INTER_AREA,
                )
                # Frame chỉ tồn tại trong RAM; mirror giúp điều khiển tự nhiên và không ghi ra đĩa.
                mirrored = cv2.flip(inference_frame, 1)
                rgb = cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB)
                rgb = np.ascontiguousarray(rgb)
                media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.monotonic() - started) * 1000)
                result = landmarker.detect_for_video(media_image, timestamp_ms)
                sampled_at = time.monotonic()
                if fps_started is None:
                    fps_started = sampled_at
                    processed_frames = 0
                else:
                    processed_frames += 1
                    sample_elapsed = sampled_at - fps_started
                    if sample_elapsed >= 1.0:
                        self.fps_sampled.emit(processed_frames / sample_elapsed)
                        fps_started = sampled_at
                        processed_frames = 0
                if not result.hand_landmarks:
                    stability.reset()
                    if self._lifecycle.gesture_enabled:
                        if self.gesture_mode == "legacy":
                            legacy_interpreter.reset()
                        elif self.gesture_mode == "grab_throw":
                            canceled = grab_interpreter.cancel()
                            if canceled.just_released:
                                self.grab_gesture.emit(canceled)
                                self.status_changed.emit(self._guidance("released"), "ready")
                        else:
                            canceled = spatial_interpreter.miss()
                            if canceled.just_released:
                                self.spatial_gesture.emit(canceled)
                                self.status_changed.emit(self._guidance("released"), "ready")
                    if self._lifecycle.scan_requested:
                        self.scan_progress.emit(0)
                        guidance = self._guidance("no_hand")
                        if guidance != last_guidance:
                            self.status_changed.emit(guidance, "waiting")
                            last_guidance = guidance
                    continue

                hand = result.hand_landmarks[0]
                points = np.asarray(
                    [(float(item.x), float(item.y), float(item.z)) for item in hand],
                    dtype=np.float32,
                )
                handedness = "Right"
                if result.handedness and result.handedness[0]:
                    handedness = result.handedness[0][0].category_name or "Right"

                if self._lifecycle.scan_requested:
                    assessment = assess_open_palm(points)
                    guidance = self._guidance(assessment.guidance_key)
                    if guidance != last_guidance:
                        self.status_changed.emit(
                            guidance, "ready" if assessment.ready else "waiting"
                        )
                        last_guidance = guidance
                    stability_update = stability.update(assessment.ready)
                    self.scan_progress.emit(stability_update.progress)
                    if stability_update.complete:
                        # Chỉ phát profile tỷ lệ; raw frame và landmark đầy đủ không được lưu.
                        profile = build_hand_profile(points, handedness)
                        self._lifecycle.complete_scan()
                        stability.reset()
                        self.scan_progress.emit(100)
                        self.scan_completed.emit(profile)
                        self.status_changed.emit("Hand profile captured.", "ready")

                if self._lifecycle.gesture_enabled:
                    if self.gesture_mode == "legacy":
                        delta = legacy_interpreter.update(points)
                        self.gesture_delta.emit(delta.yaw, delta.pitch, delta.zoom)
                    elif self.gesture_mode == "grab_throw":
                        interaction = grab_interpreter.update(points)
                        self.grab_gesture.emit(interaction)
                        if interaction.just_grabbed:
                            self.status_changed.emit(self._guidance("grabbed"), "ready")
                        elif interaction.just_released:
                            self.status_changed.emit(self._guidance("released"), "ready")
                    else:
                        interaction = spatial_interpreter.update(points)
                        self.spatial_gesture.emit(interaction)
                        if interaction.just_started:
                            guidance_key = (
                                "moving"
                                if interaction.mode is SpatialGestureMode.MOVE
                                else "transforming"
                            )
                            self.status_changed.emit(self._guidance(guidance_key), "ready")
                        elif interaction.just_released:
                            self.status_changed.emit(self._guidance("released"), "ready")
            self.status_changed.emit("Camera stopped.", "idle")
        except Exception as error:
            self.status_changed.emit(f"Vision unavailable: {error}", "error")
        finally:
            if capture is not None:
                capture.release()
            self._set_camera_active(False)
            if landmarker is not None:
                landmarker.close()
            self.running_changed.emit(False)
