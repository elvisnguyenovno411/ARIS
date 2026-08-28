from __future__ import annotations

import argparse
from pathlib import Path

from archive_mesh_utils import load_stl_members, save_local_mesh, simplify_mesh

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "user_models" / "iron_man_hand_local.npz"
ASSEMBLED_MEMBERS = (
    "Hand.stl",
    "Hand-Arc.stl",
    "Hand-Arc-Glass.stl",
    "Middle-1.stl",
    "Middle-2.stl",
    "Middle-3.stl",
    "Pinky-1.stl",
    "Pinky-2.stl",
    "Pinky-3.stl",
    "Pointer-1.stl",
    "Pointer-2.stl",
    "Pointer-3.stl",
    "Ring-1.stl",
    "Ring-2.stl",
    "Ring-3.stl",
    "Thumb-1.stl",
    "Thumb-2.stl",
    "Thumb-3.stl",
)


def import_iron_man_hand(
    archive: Path,
    output: Path,
    target_faces: int = 16_000,
) -> Path:
    """Ghép lòng bàn tay, repulsor và các đốt ngón rồi lưu Iron Man Hand local."""
    if not archive.is_file():
        raise FileNotFoundError(f"Missing Iron Man Hand archive: {archive}")
    mesh = load_stl_members(archive, ASSEMBLED_MEMBERS)
    vertices, faces, source_faces = simplify_mesh(mesh, target_faces)
    save_local_mesh(archive, output, vertices, faces, source_faces)
    print(
        f"IRON_MAN_HAND_IMPORT ok source_faces={source_faces} "
        f"optimized_faces={len(faces)} output={output}"
    )
    return output


def main() -> int:
    """Đọc tham số CLI và tạo Iron Man Hand low-poly dành riêng cho máy local."""
    parser = argparse.ArgumentParser(description="Import a local Iron Man Hand ZIP into ARIS.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-faces", type=int, default=16_000)
    arguments = parser.parse_args()
    import_iron_man_hand(
        arguments.archive.resolve(),
        arguments.output.resolve(),
        arguments.target_faces,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
