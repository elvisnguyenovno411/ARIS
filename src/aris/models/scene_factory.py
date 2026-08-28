from __future__ import annotations

import math

import numpy as np

from aris.models.external_mesh import (
    load_local_iron_man_hand,
    load_local_iron_man_mask,
    load_local_minato_kunai,
    load_local_rasengan,
    load_local_spider_mask,
    load_local_web_shooter,
)
from aris.models.geometry import (
    CYAN,
    CYAN_EDGE,
    CYAN_SOLID,
    GOLD,
    GOLD_EDGE,
    RED,
    RED_SOLID,
    SILVER,
    VIOLET,
    LinePart,
    ModelPart,
    PointPart,
    SceneBlueprint,
    box,
    circle_points,
    cylinder,
    extruded_polygon,
    sphere,
    torus,
    transform,
)
from aris.vision.hand_geometry import HandProfile


def _hand_dimensions(profile: HandProfile | None) -> tuple[float, dict[str, float], bool]:
    """Chuyển profile tỷ lệ thành kích thước hình học đã kẹp giới hạn an toàn."""
    if profile is None:
        return (
            3.0,
            {"thumb": 2.15, "index": 3.05, "middle": 3.35, "ring": 3.0, "pinky": 2.45},
            False,
        )
    # Tỷ lệ scan được đổi sang đơn vị scene rồi clamp để model luôn nằm trong camera frustum.
    palm_length = float(np.clip(profile.palm_length * 2.15, 2.5, 4.1))
    defaults = {"thumb": 1.0, "index": 1.35, "middle": 1.5, "ring": 1.35, "pinky": 1.1}
    lengths = {
        name: float(np.clip(profile.finger_lengths.get(name, default) * 2.0, 1.7, 3.8))
        for name, default in defaults.items()
    }
    return palm_length, lengths, profile.handedness == "Left"


def _hand_parts(
    profile: HandProfile | None,
    base_color=CYAN,
    armor: bool = False,
) -> tuple[list[ModelPart], list[LinePart]]:
    """Dựng bàn tay low-poly tĩnh từ lòng bàn tay và các đoạn ngón tay."""
    palm_length, lengths, mirrored = _hand_dimensions(profile)
    mirror = -1.0 if mirrored else 1.0
    parts: list[ModelPart] = []
    lines: list[LinePart] = []
    palm_points = [
        (-1.35, -palm_length / 2),
        (1.35, -palm_length / 2),
        (1.12, palm_length / 2),
        (-1.12, palm_length / 2),
    ]
    parts.append(ModelPart("palm", extruded_polygon(palm_points, 0.58), base_color, CYAN_EDGE))
    finger_positions = {
        "index": -0.78 * mirror,
        "middle": -0.25 * mirror,
        "ring": 0.3 * mirror,
        "pinky": 0.82 * mirror,
    }
    radii = {"index": 0.24, "middle": 0.26, "ring": 0.24, "pinky": 0.2}
    for name, x_value in finger_positions.items():
        total = lengths[name]
        # Ba đốt dùng tỷ lệ 39/34/27%; tổng vẫn bằng chiều dài ngón đã suy ra từ landmark.
        segment_lengths = (total * 0.39, total * 0.34, total * 0.27)
        cursor = palm_length / 2
        for segment_index, segment_length in enumerate(segment_lengths):
            center_z = cursor + segment_length / 2
            mesh = transform(
                cylinder(radii[name], radii[name] * 0.88, segment_length, 7),
                translation=(x_value, 0, center_z),
            )
            color = RED_SOLID if armor and segment_index != 1 else (GOLD if armor else base_color)
            edge = GOLD_EDGE if armor and segment_index == 1 else CYAN_EDGE
            parts.append(ModelPart(f"{name}_{segment_index}", mesh, color, edge))
            cursor += segment_length + 0.045

    thumb_length = lengths["thumb"]
    thumb_angle = -52 * mirror
    thumb = transform(
        cylinder(0.3, 0.22, thumb_length, 7),
        translation=(-1.35 * mirror, 0, -0.25),
        rotation_degrees=(0, thumb_angle, 0),
    )
    parts.append(ModelPart("thumb", thumb, RED_SOLID if armor else base_color, CYAN_EDGE))
    if armor:
        plate = extruded_polygon(
            [(-0.95, -0.9), (0.95, -0.9), (0.78, 1.0), (0, 1.3), (-0.78, 1.0)], 0.18, -0.38
        )
        parts.append(ModelPart("armor_plate", plate, RED_SOLID, GOLD_EDGE))
        emitter = transform(sphere((0.52, 0.18, 0.52), 7, 12), translation=(0, -0.48, -0.05))
        parts.append(ModelPart("repulsor", emitter, CYAN_SOLID, CYAN_EDGE, False, True))
        for radius in (0.34, 0.58):
            lines.append(
                LinePart(
                    f"repulsor_{radius}",
                    circle_points(radius, "y", center=(0, -0.69, -0.05)),
                    CYAN_EDGE,
                    2.0,
                )
            )
    return parts, lines


def _iron_man_mask() -> SceneBlueprint:
    """Dựng mặt nạ low-poly nhiều mảng với mắt cyan và đường viền vàng."""
    local_mesh = load_local_iron_man_mask()
    if local_mesh is not None:
        local_part = ModelPart(
            "iron_man_mask_local_stl",
            local_mesh,
            (0.08, 0.5, 0.64, 0.3),
            (0.28, 0.98, 1.0, 0.76),
            True,
            True,
        )
        return SceneBlueprint((local_part,), camera_distance=11.5, floor_z=-3.0)

    parts: list[ModelPart] = []
    face = [
        (-1.7, 1.25),
        (-1.35, 2.25),
        (0, 2.72),
        (1.35, 2.25),
        (1.7, 1.25),
        (1.35, -1.72),
        (0, -2.3),
        (-1.35, -1.72),
    ]
    parts.append(ModelPart("faceplate", extruded_polygon(face, 0.72, 0), GOLD, GOLD_EDGE))
    left_side = [(-2.0, 1.3), (-1.35, 2.25), (-1.7, 1.25), (-1.35, -1.72), (-1.85, -1.25)]
    right_side = [(-x, z) for x, z in reversed(left_side)]
    parts.extend(
        (
            ModelPart("left_shell", extruded_polygon(left_side, 0.95, 0.18), RED, CYAN_EDGE),
            ModelPart("right_shell", extruded_polygon(right_side, 0.95, 0.18), RED, CYAN_EDGE),
        )
    )
    jaw = [(-1.3, -1.2), (0, -2.3), (1.3, -1.2), (0.9, -1.65), (0, -1.95), (-0.9, -1.65)]
    parts.append(ModelPart("jaw", extruded_polygon(jaw, 0.82, -0.08), RED_SOLID, GOLD_EDGE))
    eye_lines: list[LinePart] = []
    for side in (-1, 1):
        points = np.asarray(
            [
                (0.35 * side, -0.48, 0.9),
                (1.18 * side, -0.48, 1.02),
                (0.78 * side, -0.5, 0.65),
                (0.35 * side, -0.48, 0.9),
            ],
            dtype=np.float32,
        )
        eye_lines.append(LinePart(f"eye_{side}", points, (0.75, 1, 1, 1), 4.0))
    return SceneBlueprint(tuple(parts), tuple(eye_lines), camera_distance=11.5, floor_z=-3.0)


def _spider_man_mask() -> SceneBlueprint:
    """Ưu tiên mesh STL local đã tối ưu và fallback sang mặt nạ procedural an toàn."""
    local_mesh = load_local_spider_mask()
    if local_mesh is not None:
        local_part = ModelPart(
            "mask_local_stl",
            local_mesh,
            (0.06, 0.5, 0.72, 0.26),
            (0.18, 0.96, 1.0, 0.68),
            True,
            True,
        )
        return SceneBlueprint((local_part,), camera_distance=11.5, floor_z=-3.0)

    head = transform(sphere((1.75, 1.35, 2.25), 11, 18), translation=(0, 0, 0.1))
    parts = [ModelPart("mask", head, RED, CYAN_EDGE, True, False)]
    lines: list[LinePart] = []
    for side in (-1, 1):
        eye = np.asarray(
            [
                (0.35 * side, -1.2, 0.95),
                (1.15 * side, -0.92, 1.35),
                (0.86 * side, -1.13, 0.2),
                (0.35 * side, -1.2, 0.95),
            ],
            dtype=np.float32,
        )
        lines.append(LinePart(f"eye_{side}", eye, (0.9, 1.0, 1.0, 1.0), 5.0))
    for angle in np.linspace(-70, 250, 8):
        radians = math.radians(float(angle))
        start = np.array((0, -1.38, 0.2), dtype=np.float32)
        end = np.array(
            (1.7 * math.cos(radians), -0.82, 2.0 * math.sin(radians) + 0.2), dtype=np.float32
        )
        lines.append(LinePart(f"web_ray_{angle}", np.vstack((start, end)), CYAN_EDGE, 1.2))
    for z_value, radius in ((-0.75, 1.2), (0.15, 1.58), (1.0, 1.18)):
        lines.append(
            LinePart(
                f"web_ring_{z_value}",
                circle_points(radius, "z", center=(0, -0.9, z_value)),
                CYAN_EDGE,
                1.0,
            )
        )
    return SceneBlueprint(tuple(parts), tuple(lines), camera_distance=11.5, floor_z=-3.0)


def _web_shooter(profile: HandProfile | None) -> SceneBlueprint:
    """Ưu tiên Web Shooter STL local và fallback sang thiết bị procedural trên tay."""
    local_mesh = load_local_web_shooter()
    if local_mesh is not None:
        local_part = ModelPart(
            "web_shooter_local_stl",
            local_mesh,
            (0.06, 0.48, 0.62, 0.3),
            (0.18, 0.96, 1.0, 0.72),
            True,
            True,
        )
        return SceneBlueprint((local_part,), camera_distance=12.0, floor_z=-3.4)

    hand_parts, hand_lines = _hand_parts(profile)
    parts = hand_parts
    band = transform(
        torus(1.15, 0.18, 18, 6), rotation_degrees=(90, 0, 0), translation=(0, 0, -1.55)
    )
    parts.append(ModelPart("wrist_band", band, SILVER, CYAN_EDGE))
    housing = box((1.35, 0.62, 0.75), center=(0, -0.52, -1.1))
    parts.append(ModelPart("housing", housing, SILVER, CYAN_EDGE))
    nozzle = transform(
        cylinder(0.25, 0.18, 0.72, 8), translation=(0, -0.86, -0.75), rotation_degrees=(90, 0, 0)
    )
    parts.append(ModelPart("nozzle", nozzle, CYAN_SOLID, CYAN_EDGE))
    trigger = box((0.5, 0.18, 0.22), center=(0, -0.87, -0.45))
    parts.append(ModelPart("trigger", trigger, (1.0, 0.2, 0.16, 0.65), GOLD_EDGE))
    return SceneBlueprint(tuple(parts), tuple(hand_lines), camera_distance=15.0, floor_z=-3.5)


def _iron_man_hand(profile: HandProfile | None) -> SceneBlueprint:
    """Ưu tiên Iron Man Hand STL local và fallback sang bàn tay giáp procedural."""
    local_mesh = load_local_iron_man_hand()
    if local_mesh is not None:
        local_part = ModelPart(
            "iron_man_hand_local_stl",
            local_mesh,
            (0.08, 0.5, 0.64, 0.3),
            (0.28, 0.98, 1.0, 0.76),
            True,
            True,
        )
        return SceneBlueprint((local_part,), camera_distance=12.0, floor_z=-3.4)
    parts, lines = _hand_parts(profile, RED, armor=True)
    return SceneBlueprint(tuple(parts), tuple(lines), camera_distance=15.0, floor_z=-3.5)


def _rasengan(profile: HandProfile | None) -> SceneBlueprint:
    """Dựng nhiều lớp cầu trên lòng bàn tay để tạo cảm giác năng lượng xoáy."""
    local_mesh = load_local_rasengan()
    if local_mesh is not None:
        local_part = ModelPart(
            "rasengan_local_stl",
            local_mesh,
            (0.06, 0.62, 0.86, 0.28),
            (0.38, 0.98, 1.0, 0.8),
            True,
            True,
        )
        return SceneBlueprint((local_part,), camera_distance=11.5, floor_z=-3.0)

    hand_parts, hand_lines = _hand_parts(profile, (0.04, 0.58, 0.7, 0.16))
    sphere_center = (0.0, -1.45, 0.0)
    energy_parts = (
        ModelPart(
            "core",
            transform(sphere((0.72, 0.72, 0.72), 8, 12), translation=sphere_center),
            (0.5, 0.98, 1.0, 0.75),
            CYAN_EDGE,
            False,
            True,
        ),
        ModelPart(
            "shell",
            transform(sphere((1.55, 1.55, 1.55), 10, 16), translation=sphere_center),
            (0.05, 0.72, 1.0, 0.16),
            CYAN_EDGE,
            True,
            False,
        ),
        ModelPart(
            "outer_shell",
            transform(sphere((1.9, 1.9, 1.9), 8, 12), translation=sphere_center),
            (0.18, 0.4, 1.0, 0.08),
            CYAN_EDGE,
            True,
            False,
        ),
    )
    energy_lines = (
        LinePart(
            "orbit_x",
            circle_points(2.15, "x", center=sphere_center),
            (0.2, 0.9, 1.0, 0.86),
            2.0,
        ),
        LinePart(
            "orbit_y",
            circle_points(1.95, "y", center=sphere_center),
            (0.65, 0.95, 1.0, 0.72),
            1.6,
        ),
        LinePart(
            "orbit_z",
            circle_points(1.75, "z", center=sphere_center),
            (0.25, 0.55, 1.0, 0.65),
            1.4,
        ),
    )
    rng = np.random.default_rng(42)
    directions = rng.normal(size=(96, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    radii = rng.uniform(1.75, 2.45, size=(96, 1))
    particle_positions = directions * radii + np.asarray(sphere_center)
    particles = PointPart(
        "energy_particles",
        particle_positions.astype(np.float32),
        (0.45, 0.95, 1.0, 0.8),
        3.2,
    )
    return SceneBlueprint(
        tuple(hand_parts) + energy_parts,
        tuple(hand_lines) + energy_lines,
        (particles,),
        camera_distance=15.0,
        floor_z=-3.5,
    )


def _minato_kunai() -> SceneBlueprint:
    """Dựng kunai ba mũi, cán quấn và vòng chuôi bằng primitive low-poly."""
    local_mesh = load_local_minato_kunai()
    if local_mesh is not None:
        local_part = ModelPart(
            "minato_kunai_local_3mf",
            local_mesh,
            (0.08, 0.48, 0.66, 0.3),
            (0.24, 0.96, 1.0, 0.78),
            True,
            True,
        )
        return SceneBlueprint((local_part,), camera_distance=11.5, floor_z=-3.2)

    blade_points = [
        (-0.25, 0),
        (-1.45, 1.15),
        (-0.52, 1.05),
        (0, 2.75),
        (0.52, 1.05),
        (1.45, 1.15),
        (0.25, 0),
    ]
    blade = extruded_polygon(blade_points, 0.28, -0.05)
    handle = transform(cylinder(0.28, 0.28, 2.6, 8), translation=(0, 0, -1.3))
    ring = transform(
        torus(0.55, 0.13, 18, 6), rotation_degrees=(90, 0, 0), translation=(0, 0, -2.9)
    )
    tag = box((1.05, 0.12, 0.62), center=(0, -0.08, -0.55))
    parts = (
        ModelPart("blade", blade, SILVER, CYAN_EDGE),
        ModelPart("handle", handle, VIOLET, CYAN_EDGE),
        ModelPart("ring", ring, VIOLET, CYAN_EDGE),
        ModelPart("tag", tag, (0.9, 0.82, 0.52, 0.35), GOLD_EDGE),
    )
    wrap_lines = tuple(
        LinePart(
            f"wrap_{index}",
            circle_points(0.31, "z", 24, center=(0, 0, -0.25 - index * 0.32)),
            GOLD_EDGE,
            1.2,
        )
        for index in range(8)
    )
    return SceneBlueprint(parts, wrap_lines, camera_distance=12.5, floor_z=-3.8)


class SceneFactory:
    """Tạo scene blueprint procedural cho từng model trong catalog beta."""

    def build(self, model_key: str, profile: HandProfile | None = None) -> SceneBlueprint:
        """Dựng model theo khóa và áp dụng tỷ lệ tay nếu model cần gắn bàn tay."""
        if model_key == "hand_scan":
            parts, lines = _hand_parts(profile)
            return SceneBlueprint(tuple(parts), tuple(lines), camera_distance=15.0, floor_z=-3.5)
        if model_key == "iron_man_mask":
            return _iron_man_mask()
        if model_key == "iron_man_hand":
            return _iron_man_hand(profile)
        if model_key == "spider_man_mask":
            return _spider_man_mask()
        if model_key == "web_shooter":
            return _web_shooter(profile)
        if model_key == "rasengan":
            return _rasengan(profile)
        if model_key == "minato_kunai":
            return _minato_kunai()
        raise KeyError(f"Unknown ARIS model: {model_key}")
