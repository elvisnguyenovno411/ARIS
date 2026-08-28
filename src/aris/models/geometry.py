from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

type Color = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class MeshGeometry:
    """Chứa đỉnh và mặt tam giác độc lập với thư viện giao diện/OpenGL."""

    vertices: np.ndarray
    faces: np.ndarray


@dataclass(frozen=True, slots=True)
class ModelPart:
    """Mô tả một mảnh mesh cùng màu hologram và thiết lập cạnh."""

    name: str
    mesh: MeshGeometry
    color: Color
    edge_color: Color = (0.12, 0.95, 1.0, 0.9)
    draw_edges: bool = True
    smooth: bool = False


@dataclass(frozen=True, slots=True)
class LinePart:
    """Mô tả một đường phát sáng dùng cho lưới, mắt hoặc vòng năng lượng."""

    name: str
    points: np.ndarray
    color: Color
    width: float = 1.5
    mode: str = "line_strip"


@dataclass(frozen=True, slots=True)
class PointPart:
    """Mô tả tập hạt nhỏ dùng để tạo chiều sâu cho hiệu ứng hologram."""

    name: str
    points: np.ndarray
    color: Color
    size: float = 3.0


@dataclass(frozen=True, slots=True)
class SceneBlueprint:
    """Gom mesh, đường và hạt của một model để renderer tạo OpenGL item."""

    parts: tuple[ModelPart, ...]
    lines: tuple[LinePart, ...] = ()
    points: tuple[PointPart, ...] = ()
    camera_distance: float = 13.0
    floor_z: float = -3.2


CYAN: Color = (0.08, 0.88, 1.0, 0.28)
CYAN_SOLID: Color = (0.1, 0.9, 1.0, 0.72)
CYAN_EDGE: Color = (0.18, 0.96, 1.0, 0.95)
RED: Color = (0.95, 0.08, 0.12, 0.3)
RED_SOLID: Color = (0.9, 0.1, 0.08, 0.62)
GOLD: Color = (1.0, 0.62, 0.08, 0.52)
GOLD_EDGE: Color = (1.0, 0.78, 0.25, 0.95)
SILVER: Color = (0.55, 0.78, 0.86, 0.4)
VIOLET: Color = (0.52, 0.18, 1.0, 0.4)


def box(
    size: tuple[float, float, float], center: tuple[float, float, float] = (0, 0, 0)
) -> MeshGeometry:
    """Tạo hình hộp tam giác hóa với kích thước và tâm cho trước."""
    sx, sy, sz = (value / 2 for value in size)
    cx, cy, cz = center
    vertices = np.array(
        [
            (cx - sx, cy - sy, cz - sz),
            (cx + sx, cy - sy, cz - sz),
            (cx + sx, cy + sy, cz - sz),
            (cx - sx, cy + sy, cz - sz),
            (cx - sx, cy - sy, cz + sz),
            (cx + sx, cy - sy, cz + sz),
            (cx + sx, cy + sy, cz + sz),
            (cx - sx, cy + sy, cz + sz),
        ],
        dtype=np.float32,
    )
    faces = np.array(
        [
            (0, 2, 1),
            (0, 3, 2),
            (4, 5, 6),
            (4, 6, 7),
            (0, 1, 5),
            (0, 5, 4),
            (1, 2, 6),
            (1, 6, 5),
            (2, 3, 7),
            (2, 7, 6),
            (3, 0, 4),
            (3, 4, 7),
        ],
        dtype=np.int32,
    )
    return MeshGeometry(vertices, faces)


def extruded_polygon(
    points_xz: list[tuple[float, float]],
    depth: float,
    center_y: float = 0.0,
) -> MeshGeometry:
    """Đùn một đa giác trong mặt phẳng XZ theo trục Y thành mesh kín."""
    if len(points_xz) < 3:
        raise ValueError("An extruded polygon requires at least three points.")
    half = depth / 2
    front = [(x, center_y - half, z) for x, z in points_xz]
    back = [(x, center_y + half, z) for x, z in points_xz]
    vertices = np.asarray(front + back, dtype=np.float32)
    count = len(points_xz)
    faces: list[tuple[int, int, int]] = []
    for index in range(1, count - 1):
        faces.append((0, index + 1, index))
        faces.append((count, count + index, count + index + 1))
    for index in range(count):
        following = (index + 1) % count
        faces.append((index, following, count + following))
        faces.append((index, count + following, count + index))
    return MeshGeometry(vertices, np.asarray(faces, dtype=np.int32))


def sphere(radii: tuple[float, float, float], rows: int = 10, columns: int = 16) -> MeshGeometry:
    """Tạo ellipsoid low-poly với số hàng/cột được giới hạn để chạy mượt."""
    rows = max(4, rows)
    columns = max(6, columns)
    rx, ry, rz = radii
    vertices: list[tuple[float, float, float]] = []
    for row in range(rows + 1):
        phi = math.pi * row / rows
        for column in range(columns):
            theta = 2 * math.pi * column / columns
            vertices.append(
                (
                    rx * math.sin(phi) * math.cos(theta),
                    ry * math.sin(phi) * math.sin(theta),
                    rz * math.cos(phi),
                )
            )
    faces: list[tuple[int, int, int]] = []
    for row in range(rows):
        for column in range(columns):
            following = (column + 1) % columns
            first = row * columns + column
            second = row * columns + following
            third = (row + 1) * columns + column
            fourth = (row + 1) * columns + following
            faces.extend(((first, third, second), (second, third, fourth)))
    return MeshGeometry(np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.int32))


def cylinder(
    radius_bottom: float,
    radius_top: float,
    length: float,
    segments: int = 8,
) -> MeshGeometry:
    """Tạo hình trụ hoặc trụ thuôn low-poly dọc trục Z với hai nắp kín."""
    segments = max(5, segments)
    vertices: list[tuple[float, float, float]] = []
    half = length / 2
    for z_value, radius in ((-half, radius_bottom), (half, radius_top)):
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), z_value))
    vertices.extend(((0, 0, -half), (0, 0, half)))
    bottom_center = segments * 2
    top_center = bottom_center + 1
    faces: list[tuple[int, int, int]] = []
    for index in range(segments):
        following = (index + 1) % segments
        faces.extend(
            (
                (index, segments + index, following),
                (following, segments + index, segments + following),
                (bottom_center, following, index),
                (top_center, segments + index, segments + following),
            )
        )
    return MeshGeometry(np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.int32))


def torus(
    major_radius: float,
    minor_radius: float,
    major_segments: int = 18,
    minor_segments: int = 6,
) -> MeshGeometry:
    """Tạo vòng xuyến low-poly quanh trục Z dùng cho vòng tay hoặc chuôi kunai."""
    vertices: list[tuple[float, float, float]] = []
    for major in range(major_segments):
        theta = 2 * math.pi * major / major_segments
        for minor in range(minor_segments):
            phi = 2 * math.pi * minor / minor_segments
            radial = major_radius + minor_radius * math.cos(phi)
            vertices.append(
                (radial * math.cos(theta), radial * math.sin(theta), minor_radius * math.sin(phi))
            )
    faces: list[tuple[int, int, int]] = []
    for major in range(major_segments):
        next_major = (major + 1) % major_segments
        for minor in range(minor_segments):
            next_minor = (minor + 1) % minor_segments
            a = major * minor_segments + minor
            b = next_major * minor_segments + minor
            c = major * minor_segments + next_minor
            d = next_major * minor_segments + next_minor
            faces.extend(((a, b, c), (c, b, d)))
    return MeshGeometry(np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.int32))


def transform(
    mesh: MeshGeometry,
    translation: tuple[float, float, float] = (0, 0, 0),
    rotation_degrees: tuple[float, float, float] = (0, 0, 0),
    scale: tuple[float, float, float] = (1, 1, 1),
) -> MeshGeometry:
    """Áp dụng scale, Euler rotation XYZ và translation vào một mesh mới."""
    vertices = mesh.vertices.astype(np.float64, copy=True)
    vertices *= np.asarray(scale, dtype=np.float64)
    rx, ry, rz = np.radians(rotation_degrees)
    rotation_x = np.array(
        ((1, 0, 0), (0, math.cos(rx), -math.sin(rx)), (0, math.sin(rx), math.cos(rx)))
    )
    rotation_y = np.array(
        ((math.cos(ry), 0, math.sin(ry)), (0, 1, 0), (-math.sin(ry), 0, math.cos(ry)))
    )
    rotation_z = np.array(
        ((math.cos(rz), -math.sin(rz), 0), (math.sin(rz), math.cos(rz), 0), (0, 0, 1))
    )
    vertices = vertices @ (rotation_z @ rotation_y @ rotation_x).T
    vertices += np.asarray(translation, dtype=np.float64)
    return MeshGeometry(vertices.astype(np.float32), mesh.faces.copy())


def circle_points(
    radius: float,
    axis: str = "z",
    count: int = 80,
    center: tuple[float, float, float] = (0, 0, 0),
) -> np.ndarray:
    """Tạo các điểm vòng tròn đóng để vẽ quỹ đạo hoặc họa tiết hologram."""
    cx, cy, cz = center
    angles = np.linspace(0, math.tau, count, dtype=np.float32)
    if axis == "x":
        points = np.column_stack((np.zeros_like(angles), np.cos(angles), np.sin(angles)))
    elif axis == "y":
        points = np.column_stack((np.cos(angles), np.zeros_like(angles), np.sin(angles)))
    else:
        points = np.column_stack((np.cos(angles), np.sin(angles), np.zeros_like(angles)))
    points *= radius
    points += np.asarray((cx, cy, cz), dtype=np.float32)
    return points.astype(np.float32)
