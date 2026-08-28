from aris.vision.scan_stability import ScanStability


def test_scan_requires_consecutive_stable_frames() -> None:
    """Kiểm tra scan chỉ complete sau đủ số frame đạt chuẩn liên tục."""
    stability = ScanStability(required_frames=3)

    assert not stability.update(True).complete
    assert not stability.update(True).complete
    result = stability.update(True)

    assert result.complete
    assert result.progress == 100


def test_unstable_frame_resets_scan_progress() -> None:
    """Kiểm tra một frame không đạt chuẩn xóa tiến độ cũ để tránh capture sai tư thế."""
    stability = ScanStability(required_frames=3)
    stability.update(True)
    stability.update(True)

    result = stability.update(False)

    assert result.progress == 0
    assert not result.complete
