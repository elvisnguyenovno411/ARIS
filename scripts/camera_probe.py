from __future__ import annotations

import sys
import time

import cv2


def probe_camera(index: int = 0, timeout_seconds: float = 4.0) -> int:
    """Mở webcam ngắn hạn, kiểm tra frame và tuyệt đối không lưu hình ảnh."""
    camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera.release()
        print(f"CAMERA_PROBE failed index={index} reason=not_opened")
        return 1

    started = time.monotonic()
    frames = 0
    width = 0
    height = 0
    while time.monotonic() - started < timeout_seconds and frames < 12:
        ok, frame = camera.read()
        if not ok or frame is None:
            continue
        frames += 1
        height, width = frame.shape[:2]

    camera.release()
    if frames == 0:
        print(f"CAMERA_PROBE failed index={index} reason=no_frames")
        return 2

    print(f"CAMERA_PROBE ok index={index} frames={frames} resolution={width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(probe_camera(int(sys.argv[1]) if len(sys.argv) > 1 else 0))
