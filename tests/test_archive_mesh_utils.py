from __future__ import annotations

import io
import zipfile

import numpy as np
import pytest

from scripts.archive_mesh_utils import load_3mf_members, load_stl_members


def _simple_3mf() -> bytes:
    """Tạo gói 3MF tam giác nhỏ có transform để kiểm tra parser không cần networkx."""
    model = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>
          <vertex x="0" y="0" z="0"/>
          <vertex x="1" y="0" z="0"/>
          <vertex x="0" y="1" z="0"/>
        </vertices>
        <triangles><triangle v1="0" v2="1" v3="2"/></triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="1" transform="1 0 0 0 1 0 0 0 1 10 20 30"/>
  </build>
</model>
"""
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("3D/3dmodel.model", model)
    return payload.getvalue()


def test_nested_3mf_build_transform_is_preserved(tmp_path) -> None:
    """Kiểm tra loader ghép 3MF trong ZIP và giữ đúng dịch chuyển build-level."""
    archive = tmp_path / "kunai.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("part.3mf", _simple_3mf())

    mesh = load_3mf_members(archive, ("part.3mf",))

    assert len(mesh.faces) == 1
    assert np.allclose(mesh.bounds[0], (10.0, 20.0, 30.0))
    assert np.allclose(mesh.bounds[1], (11.0, 21.0, 30.0))


def test_archive_loader_rejects_parent_traversal_member(tmp_path) -> None:
    """Kiểm tra importer từ chối member cha ngay cả khi ZIP có tên đó."""
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("../mesh.stl", b"not-a-real-stl")

    with pytest.raises(ValueError, match="Unsafe archive path"):
        load_stl_members(archive, ("../mesh.stl",))
