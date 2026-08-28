from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

import numpy as np

MAX_MEMBER_BYTES = 300 * 1024 * 1024


def _mesh_tools():
    """Nạp trimesh theo nhu cầu và báo lệnh cài optional dependency khi còn thiếu."""
    try:
        import trimesh
    except ImportError as error:
        message = 'Install the optional mesh tools with: pip install -e ".[mesh]"'
        raise RuntimeError(message) from error
    return trimesh


def _read_member(bundle: zipfile.ZipFile, member: str) -> bytes:
    """Đọc đúng một member đã chỉ định và chặn file nén có kích thước bất thường."""
    archive_path = PurePosixPath(member.replace("\\", "/"))
    if (
        archive_path.is_absolute()
        or ".." in archive_path.parts
        or not archive_path.parts
        or ":" in archive_path.parts[0]
    ):
        raise ValueError(f"Unsafe archive path: {member}")
    info = bundle.getinfo(member)
    if info.is_dir() or info.file_size <= 0 or info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"Unsafe or empty archive member: {member}")
    return bundle.read(info)


def _scene_to_mesh(loaded):
    """Đổi Scene/Trimesh của trimesh thành một mesh thống nhất."""
    trimesh = _mesh_tools()
    if isinstance(loaded, trimesh.Scene):
        return loaded.to_mesh()
    return loaded


def load_stl_members(archive: Path, members: tuple[str, ...]):
    """Nạp và ghép các STL được chọn trực tiếp từ ZIP mà không giải nén ra ổ đĩa."""
    trimesh = _mesh_tools()
    meshes = []
    with zipfile.ZipFile(archive) as bundle:
        for member in members:
            payload = _read_member(bundle, member)
            loaded = trimesh.load_mesh(io.BytesIO(payload), file_type="stl", process=True)
            meshes.append(_scene_to_mesh(loaded))
    if not meshes:
        raise ValueError(f"No STL members selected from {archive}")
    return trimesh.util.concatenate(meshes)


def _transform_3mf_vertices(vertices: np.ndarray, encoded: str | None) -> np.ndarray:
    """Áp dụng ma trận transform 3MF 3×4 lên vertex theo đúng thứ tự của đặc tả."""
    if not encoded:
        return vertices
    values = np.fromstring(encoded, sep=" ", dtype=np.float64)
    if values.shape != (12,) or not np.isfinite(values).all():
        raise ValueError("Invalid 3MF build transform.")
    basis = values[:9].reshape((3, 3))
    translation = values[9:]
    return vertices @ basis + translation


def _meshes_from_3mf(payload: bytes) -> list[tuple[np.ndarray, np.ndarray]]:
    """Đọc mesh build-level từ một gói 3MF bằng thư viện chuẩn, không cần networkx."""
    with zipfile.ZipFile(io.BytesIO(payload)) as package:
        model_names = [
            name for name in package.namelist() if name.casefold().endswith(".model")
        ]
        if len(model_names) != 1:
            raise ValueError("Expected exactly one 3MF model document.")
        model_info = package.getinfo(model_names[0])
        if model_info.file_size > MAX_MEMBER_BYTES:
            raise ValueError("3MF model document is too large.")
        root = ET.fromstring(package.read(model_info))

    namespace = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    objects = {
        element.attrib["id"]: element
        for element in root.findall(f".//{namespace}resources/{namespace}object")
    }
    build = root.find(f"{namespace}build")
    if build is None:
        raise ValueError("3MF package has no build section.")

    meshes: list[tuple[np.ndarray, np.ndarray]] = []
    for item in build:
        object_id = item.attrib.get("objectid")
        element = objects.get(str(object_id))
        if element is None:
            raise ValueError(f"3MF build references missing object {object_id}.")
        mesh = element.find(f"{namespace}mesh")
        if mesh is None:
            continue
        vertices_node = mesh.find(f"{namespace}vertices")
        triangles_node = mesh.find(f"{namespace}triangles")
        if vertices_node is None or triangles_node is None:
            raise ValueError(f"3MF object {object_id} has incomplete mesh data.")
        vertices = np.asarray(
            [
                (
                    float(vertex.attrib["x"]),
                    float(vertex.attrib["y"]),
                    float(vertex.attrib["z"]),
                )
                for vertex in vertices_node
            ],
            dtype=np.float64,
        )
        faces = np.asarray(
            [
                (
                    int(triangle.attrib["v1"]),
                    int(triangle.attrib["v2"]),
                    int(triangle.attrib["v3"]),
                )
                for triangle in triangles_node
            ],
            dtype=np.int64,
        )
        vertices = _transform_3mf_vertices(vertices, item.attrib.get("transform"))
        meshes.append((vertices, faces))
    if not meshes:
        raise ValueError("3MF build contains no directly renderable mesh.")
    return meshes


def load_3mf_members(archive: Path, members: tuple[str, ...]):
    """Nạp các gói 3MF được chọn trong ZIP và ghép đúng tọa độ build của chúng."""
    trimesh = _mesh_tools()
    meshes = []
    with zipfile.ZipFile(archive) as bundle:
        for member in members:
            payload = _read_member(bundle, member)
            for vertices, faces in _meshes_from_3mf(payload):
                meshes.append(trimesh.Trimesh(vertices=vertices, faces=faces, process=True))
    if not meshes:
        raise ValueError(f"No 3MF meshes selected from {archive}")
    return trimesh.util.concatenate(meshes)


def simplify_mesh(mesh, target_faces: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Giảm polygon, loại tam giác lỗi và chuẩn hóa mesh về kích thước HUD ARIS."""
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
    vertices = (vertices - center) * (4.8 / float(extent.max()))
    triangles = vertices[faces]
    normalized_area = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]),
        axis=1,
    )
    faces = faces[normalized_area > 1e-7]
    used_vertices, compact_faces = np.unique(faces, return_inverse=True)
    vertices = vertices[used_vertices]
    faces = compact_faces.reshape((-1, 3)).astype(np.int32)
    return np.ascontiguousarray(vertices), np.ascontiguousarray(faces), source_faces


def save_local_mesh(
    archive: Path,
    output: Path,
    vertices: np.ndarray,
    faces: np.ndarray,
    source_faces: int,
) -> Path:
    """Lưu NPZ runtime local cùng hash nguồn để kiểm toán mà không đóng gói ZIP gốc."""
    source_hash = hashlib.sha256(archive.read_bytes()).hexdigest().upper()
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        vertices=np.ascontiguousarray(vertices, dtype=np.float32),
        faces=np.ascontiguousarray(faces, dtype=np.int32),
        source_faces=np.asarray([source_faces], dtype=np.int64),
        source_archive_sha256=np.asarray([source_hash]),
    )
    return output
