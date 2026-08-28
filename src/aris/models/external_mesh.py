from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from aris.models.geometry import MeshGeometry

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_SPIDER_MASK_PATH = (
    PROJECT_ROOT / "assets" / "user_models" / "spider_man_mask_local.npz"
)
LOCAL_WEB_SHOOTER_PATH = PROJECT_ROOT / "assets" / "user_models" / "web_shooter_local.npz"
LOCAL_IRON_MAN_MASK_PATH = PROJECT_ROOT / "assets" / "user_models" / "iron_man_mask_local.npz"
LOCAL_IRON_MAN_HAND_PATH = PROJECT_ROOT / "assets" / "user_models" / "iron_man_hand_local.npz"
LOCAL_RASENGAN_PATH = PROJECT_ROOT / "assets" / "user_models" / "rasengan_local.npz"
LOCAL_MINATO_KUNAI_PATH = PROJECT_ROOT / "assets" / "user_models" / "minato_kunai_local.npz"
MAX_LOCAL_FACES = 150_000


@lru_cache(maxsize=8)
def _load_local_mesh(source: Path) -> MeshGeometry | None:
    """Nạp một NPZ local và từ chối dữ liệu sai trước khi chuyển cho OpenGL."""
    if not source.is_file():
        return None
    try:
        with np.load(source, allow_pickle=False) as payload:
            vertices = np.asarray(payload["vertices"], dtype=np.float32)
            faces = np.asarray(payload["faces"], dtype=np.int32)
    except (OSError, ValueError, KeyError):
        return None
    if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 3:
        return None
    if faces.ndim != 2 or faces.shape[1] != 3 or not 1 <= len(faces) <= MAX_LOCAL_FACES:
        return None
    if not np.isfinite(vertices).all() or faces.min() < 0 or faces.max() >= len(vertices):
        return None
    return MeshGeometry(
        np.ascontiguousarray(vertices),
        np.ascontiguousarray(faces),
    )


def load_local_spider_mask(path: Path | None = None) -> MeshGeometry | None:
    """Nạp Spider-Man Mask local hoặc trả None để dùng procedural fallback."""
    return _load_local_mesh(path or LOCAL_SPIDER_MASK_PATH)


def load_local_web_shooter(path: Path | None = None) -> MeshGeometry | None:
    """Nạp Web Shooter local hoặc trả None để dùng procedural fallback kèm bàn tay."""
    return _load_local_mesh(path or LOCAL_WEB_SHOOTER_PATH)


def load_local_iron_man_mask(path: Path | None = None) -> MeshGeometry | None:
    """Nạp Iron Man Mask local hoặc trả None để dùng mặt nạ procedural."""
    return _load_local_mesh(path or LOCAL_IRON_MAN_MASK_PATH)


def load_local_iron_man_hand(path: Path | None = None) -> MeshGeometry | None:
    """Nạp Iron Man Hand local hoặc trả None để dựng bàn tay giáp procedural."""
    return _load_local_mesh(path or LOCAL_IRON_MAN_HAND_PATH)


def load_local_rasengan(path: Path | None = None) -> MeshGeometry | None:
    """Nạp Rasengan local hoặc trả None để dùng quả cầu năng lượng procedural."""
    return _load_local_mesh(path or LOCAL_RASENGAN_PATH)


def load_local_minato_kunai(path: Path | None = None) -> MeshGeometry | None:
    """Nạp Minato Kunai local hoặc trả None để dùng kunai procedural."""
    return _load_local_mesh(path or LOCAL_MINATO_KUNAI_PATH)


def preload_local_meshes() -> None:
    """Nạp trước sáu mesh nhỏ vào cache để yêu cầu model đầu không block giao diện."""
    for loader in (
        load_local_spider_mask,
        load_local_web_shooter,
        load_local_iron_man_mask,
        load_local_iron_man_hand,
        load_local_rasengan,
        load_local_minato_kunai,
    ):
        loader()
