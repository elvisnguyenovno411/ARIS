import numpy as np
import pytest

import aris.models.scene_factory as scene_factory_module
from aris.models.catalog import ModelCatalog
from aris.models.geometry import MeshGeometry
from aris.models.scene_factory import SceneFactory


def test_every_catalog_model_has_geometry() -> None:
    """Kiểm tra mỗi model công bố đều dựng được ít nhất một mesh hợp lệ."""
    factory = SceneFactory()
    for spec in ModelCatalog().all():
        scene = factory.build(spec.key)
        assert scene.parts
        assert all(part.mesh.vertices.shape[1] == 3 for part in scene.parts)
        assert all(part.mesh.faces.shape[1] == 3 for part in scene.parts)


def test_local_spider_mask_is_preferred_when_available(monkeypatch) -> None:
    """Kiểm tra Spider-Man Mask ưu tiên mesh local tối ưu thay cho hình procedural."""
    local_mesh = MeshGeometry(
        np.asarray(((0, 0, 0), (1, 0, 0), (0, 1, 0)), dtype=np.float32),
        np.asarray(((0, 1, 2),), dtype=np.int32),
    )
    monkeypatch.setattr(
        scene_factory_module,
        "load_local_spider_mask",
        lambda: local_mesh,
    )

    scene = SceneFactory().build("spider_man_mask")

    assert len(scene.parts) == 1
    assert scene.parts[0].name == "mask_local_stl"


def test_spider_mask_keeps_procedural_fallback(monkeypatch) -> None:
    """Kiểm tra clone GitHub không có asset cá nhân vẫn dựng được mặt nạ procedural."""
    monkeypatch.setattr(
        scene_factory_module,
        "load_local_spider_mask",
        lambda: None,
    )

    scene = SceneFactory().build("spider_man_mask")

    assert scene.parts[0].name == "mask"
    assert scene.lines


def test_local_web_shooter_is_preferred_when_available(monkeypatch) -> None:
    """Kiểm tra Web Shooter ưu tiên STL local tối ưu khi file đã được nhập."""
    local_mesh = MeshGeometry(
        np.asarray(((0, 0, 0), (1, 0, 0), (0, 1, 0)), dtype=np.float32),
        np.asarray(((0, 1, 2),), dtype=np.int32),
    )
    monkeypatch.setattr(
        scene_factory_module,
        "load_local_web_shooter",
        lambda: local_mesh,
    )

    scene = SceneFactory().build("web_shooter")

    assert len(scene.parts) == 1
    assert scene.parts[0].name == "web_shooter_local_stl"


def test_web_shooter_keeps_procedural_fallback(monkeypatch) -> None:
    """Kiểm tra clone GitHub thiếu STL vẫn dựng Web Shooter procedural an toàn."""
    monkeypatch.setattr(
        scene_factory_module,
        "load_local_web_shooter",
        lambda: None,
    )

    scene = SceneFactory().build("web_shooter")

    assert any(part.name == "wrist_band" for part in scene.parts)


@pytest.mark.parametrize(
    ("model_key", "loader_name", "part_name"),
    (
        ("iron_man_mask", "load_local_iron_man_mask", "iron_man_mask_local_stl"),
        ("iron_man_hand", "load_local_iron_man_hand", "iron_man_hand_local_stl"),
        ("rasengan", "load_local_rasengan", "rasengan_local_stl"),
        ("minato_kunai", "load_local_minato_kunai", "minato_kunai_local_3mf"),
    ),
)
def test_downloaded_local_models_are_preferred(
    monkeypatch,
    model_key: str,
    loader_name: str,
    part_name: str,
) -> None:
    """Kiểm tra bốn model tải về được ưu tiên khi NPZ local hợp lệ tồn tại."""
    local_mesh = MeshGeometry(
        np.asarray(((0, 0, 0), (1, 0, 0), (0, 1, 0)), dtype=np.float32),
        np.asarray(((0, 1, 2),), dtype=np.int32),
    )
    monkeypatch.setattr(scene_factory_module, loader_name, lambda: local_mesh)

    scene = SceneFactory().build(model_key)

    assert len(scene.parts) == 1
    assert scene.parts[0].name == part_name


@pytest.mark.parametrize(
    ("model_key", "loader_name", "fallback_part"),
    (
        ("iron_man_mask", "load_local_iron_man_mask", "faceplate"),
        ("iron_man_hand", "load_local_iron_man_hand", "palm"),
        ("rasengan", "load_local_rasengan", "core"),
        ("minato_kunai", "load_local_minato_kunai", "blade"),
    ),
)
def test_downloaded_models_keep_public_procedural_fallbacks(
    monkeypatch,
    model_key: str,
    loader_name: str,
    fallback_part: str,
) -> None:
    """Kiểm tra clone công khai thiếu asset cá nhân vẫn dựng đủ bốn scene procedural."""
    monkeypatch.setattr(scene_factory_module, loader_name, lambda: None)

    scene = SceneFactory().build(model_key)

    assert any(part.name == fallback_part for part in scene.parts)
