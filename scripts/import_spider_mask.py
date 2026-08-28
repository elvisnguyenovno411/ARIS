from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "user_models" / "spider_man_mask_local.npz"
FRONT_FILENAME = "obj_6_MASK-FRONT1.STL.stl"


def simplify_stl(source: Path, target_faces: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Nạp STL, giảm polygon bằng quadric decimation và trả mesh đã chuẩn hóa."""
    try:
        import trimesh
    except ImportError as error:
        message = 'Install the optional mesh tools with: pip install -e ".[mesh]"'
        raise RuntimeError(message) from error

    loaded = trimesh.load_mesh(source, process=True)
    if isinstance(loaded, trimesh.Scene):
        mesh = loaded.to_geometry()
    else:
        mesh = loaded
    source_faces = int(len(mesh.faces))
    desired_faces = max(2_000, min(source_faces, int(target_faces)))
    if source_faces > desired_faces:
        mesh = mesh.simplify_quadric_decimation(face_count=desired_faces)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    triangles = vertices[faces]
    doubled_area = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]),
        axis=1,
    )
    faces = faces[doubled_area > 1e-8]
    canonical_faces = np.sort(faces, axis=1)
    _, unique_indices = np.unique(canonical_faces, axis=0, return_index=True)
    faces = faces[np.sort(unique_indices)]
    used_vertices, compact_faces = np.unique(faces, return_inverse=True)
    vertices = vertices[used_vertices]
    faces = compact_faces.reshape((-1, 3)).astype(np.int32)
    bounds_min = vertices.min(axis=0)
    bounds_max = vertices.max(axis=0)
    center = (bounds_min + bounds_max) * 0.5
    extent = np.maximum(bounds_max - bounds_min, 1e-6)
    # Giữ Z là chiều cao và đưa cạnh lớn nhất về khoảng 4.8 đơn vị scene ARIS.
    vertices = (vertices - center) * (4.8 / float(extent.max()))
    normalized_triangles = vertices[faces]
    normalized_area = np.linalg.norm(
        np.cross(
            normalized_triangles[:, 1] - normalized_triangles[:, 0],
            normalized_triangles[:, 2] - normalized_triangles[:, 0],
        ),
        axis=1,
    )
    faces = faces[normalized_area > 1e-7]
    used_vertices, compact_faces = np.unique(faces, return_inverse=True)
    vertices = vertices[used_vertices]
    faces = compact_faces.reshape((-1, 3)).astype(np.int32)
    return np.ascontiguousarray(vertices), np.ascontiguousarray(faces), source_faces


def import_mask(source_dir: Path, output: Path, target_faces: int = 18_000) -> Path:
    """Chuyển phần mặt trước STL thành NPZ low-poly local mà không sửa file gốc."""
    source = source_dir / FRONT_FILENAME
    if not source.is_file():
        raise FileNotFoundError(f"Missing Spider-Man mask front STL: {source}")
    vertices, faces, source_faces = simplify_stl(source, target_faces)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        vertices=vertices,
        faces=faces,
        source_faces=np.asarray([source_faces], dtype=np.int64),
    )
    print(
        f"SPIDER_MASK_IMPORT ok source_faces={source_faces} "
        f"optimized_faces={len(faces)} output={output}"
    )
    return output


def main() -> int:
    """Đọc tham số CLI và tạo asset Spider-Man Mask tối ưu dành riêng cho máy local."""
    parser = argparse.ArgumentParser(description="Import a local Spider-Man mask STL into ARIS.")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-faces", type=int, default=18_000)
    arguments = parser.parse_args()
    import_mask(arguments.source_dir.resolve(), arguments.output.resolve(), arguments.target_faces)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
