from pathlib import Path
from unittest.mock import MagicMock

import aris.vision.tracker as tracker_module
from aris.vision.camera_lifecycle import CameraLifecycle
from aris.vision.tracker import VisionController


def test_camera_starts_with_no_demand() -> None:
    """Kiểm tra lifecycle khởi động với camera tắt và không có scan/gesture ngầm."""
    lifecycle = CameraLifecycle()

    assert not lifecycle.should_run
    assert not lifecycle.scan_requested
    assert not lifecycle.gesture_enabled


def test_vision_controller_constructor_does_not_open_camera() -> None:
    """Kiểm tra tạo controller không sinh worker hoặc mở webcam khi app khởi động."""
    controller = VisionController(Path("unused-hand-landmarker.task"))

    assert not controller.is_running


def test_preload_starts_worker_without_requesting_camera() -> None:
    """Kiểm tra preload chỉ nạp engine và chưa tạo nhu cầu mở webcam."""
    controller = VisionController(Path("unused-hand-landmarker.task"))
    start = MagicMock()
    controller.start = start

    controller.preload()

    start.assert_called_once_with()
    assert not controller._lifecycle.should_run


def test_open_camera_falls_back_to_next_windows_backend(monkeypatch) -> None:
    """Kiểm tra webcam thử backend kế tiếp khi backend Windows đầu tiên thất bại."""
    controller = VisionController(Path("unused-hand-landmarker.task"))
    controller._lifecycle.set_gesture_enabled(True)
    failed_capture = MagicMock()
    failed_capture.isOpened.return_value = False
    ready_capture = MagicMock()
    ready_capture.isOpened.return_value = True
    video_capture = MagicMock(side_effect=[failed_capture, ready_capture])
    monkeypatch.setattr(tracker_module.cv2, "CAP_DSHOW", 101)
    monkeypatch.setattr(tracker_module.cv2, "CAP_MSMF", 102)
    monkeypatch.setattr(tracker_module.cv2, "CAP_ANY", 0)
    monkeypatch.setattr(tracker_module.cv2, "VideoCapture", video_capture)

    opened = controller._open_camera()

    assert opened is ready_capture
    assert video_capture.call_args_list[0].args == (0, 101)
    assert video_capture.call_args_list[1].args == (0, 102)
    failed_capture.release.assert_called_once_with()


def test_scan_completion_releases_camera_without_gesture() -> None:
    """Kiểm tra scan hoàn tất sẽ hết nhu cầu camera nếu gesture đang tắt."""
    lifecycle = CameraLifecycle()
    lifecycle.request_scan()

    assert lifecycle.should_run

    lifecycle.complete_scan()

    assert not lifecycle.should_run


def test_scan_completion_keeps_camera_for_gesture() -> None:
    """Kiểm tra camera tiếp tục chạy sau scan khi người dùng vẫn bật gesture."""
    lifecycle = CameraLifecycle()
    lifecycle.set_gesture_enabled(True)
    lifecycle.request_scan()
    lifecycle.complete_scan()

    assert lifecycle.should_run
    assert lifecycle.gesture_enabled

    lifecycle.set_gesture_enabled(False)

    assert not lifecycle.should_run


def test_clear_releases_all_camera_demand() -> None:
    """Kiểm tra đóng app xóa đồng thời nhu cầu scan và gesture."""
    lifecycle = CameraLifecycle()
    lifecycle.request_scan()
    lifecycle.set_gesture_enabled(True)

    lifecycle.clear()

    assert not lifecycle.should_run
