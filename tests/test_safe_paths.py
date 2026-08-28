from pathlib import Path

import pytest

from aris.desktop.safe_paths import SafePathPolicy, UnsafePathError


def test_path_inside_root_is_allowed(tmp_path: Path) -> None:
    """Kiểm tra file trong thư mục gốc được phép truy cập."""
    file_path = tmp_path / "demo.txt"
    file_path.write_text("demo", encoding="utf-8")
    policy = SafePathPolicy([tmp_path])
    assert policy.require_allowed(file_path) == file_path.resolve()


def test_path_outside_root_is_rejected(tmp_path: Path) -> None:
    """Kiểm tra đường dẫn ngoài allowlist luôn bị từ chối."""
    safe = tmp_path / "safe"
    safe.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    policy = SafePathPolicy([safe])
    with pytest.raises(UnsafePathError):
        policy.require_allowed(outside)


@pytest.mark.parametrize("extension", (".mp3", ".wav", ".mp4", ".mkv"))
def test_personal_audio_and_video_are_never_discovered(
    tmp_path: Path,
    extension: str,
) -> None:
    """Đảm bảo file media cá nhân bị chặn dù đang nằm trong một safe root khác."""
    media = tmp_path / f"private{extension}"
    media.write_bytes(b"private media")
    policy = SafePathPolicy([tmp_path])

    assert not policy.is_allowed(media)
    assert policy.find("private") == []
    with pytest.raises(UnsafePathError):
        policy.require_allowed(media)
