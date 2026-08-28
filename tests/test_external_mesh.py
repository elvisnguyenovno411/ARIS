from __future__ import annotations

import numpy as np

from aris.models.external_mesh import load_local_spider_mask, load_local_web_shooter


def test_valid_local_npz_loads_as_mesh(tmp_path) -> None:
    """Kiểm tra asset local hợp lệ được nạp bằng NumPy mà không cần thư viện STL runtime."""
    path = tmp_path / "mask.npz"
    np.savez_compressed(
        path,
        vertices=np.asarray(((0, 0, 0), (1, 0, 0), (0, 1, 0)), dtype=np.float32),
        faces=np.asarray(((0, 1, 2),), dtype=np.int32),
    )

    mesh = load_local_spider_mask(path)

    assert mesh is not None
    assert mesh.vertices.shape == (3, 3)
    assert mesh.faces.shape == (1, 3)


def test_invalid_local_face_indices_use_fallback(tmp_path) -> None:
    """Kiểm tra face trỏ ra ngoài vertex bị từ chối thay vì làm renderer crash."""
    path = tmp_path / "broken-mask.npz"
    np.savez_compressed(
        path,
        vertices=np.asarray(((0, 0, 0), (1, 0, 0), (0, 1, 0)), dtype=np.float32),
        faces=np.asarray(((0, 1, 99),), dtype=np.int32),
    )

    assert load_local_spider_mask(path) is None


def test_valid_local_web_shooter_npz_loads_as_mesh(tmp_path) -> None:
    """Kiểm tra Web Shooter NPZ local dùng chung lớp kiểm tra an toàn của mesh ngoài."""
    path = tmp_path / "web-shooter.npz"
    np.savez_compressed(
        path,
        vertices=np.asarray(((0, 0, 0), (1, 0, 0), (0, 1, 0)), dtype=np.float32),
        faces=np.asarray(((0, 1, 2),), dtype=np.int32),
    )

    mesh = load_local_web_shooter(path)

    assert mesh is not None
    assert mesh.vertices.shape == (3, 3)
    assert mesh.faces.shape == (1, 3)
