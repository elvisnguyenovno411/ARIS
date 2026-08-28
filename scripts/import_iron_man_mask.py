from __future__ import annotations

import argparse
from pathlib import Path

from archive_mesh_utils import load_stl_members, save_local_mesh, simplify_mesh

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "user_models" / "iron_man_mask_local.npz"
ASSEMBLED_MEMBERS = ("helmet.stl", "mask.stl", "back.stl", "chin.stl")


def import_iron_man_mask(
    archive: Path,
    output: Path,
    target_faces: int = 14_000,
) -> Path:
    """Ghép các vỏ mũ cùng hệ tọa độ, tối ưu và lưu Iron Man Mask local."""
    if not archive.is_file():
        raise FileNotFoundError(f"Missing Iron Man Mask archive: {archive}")
    mesh = load_stl_members(archive, ASSEMBLED_MEMBERS)
    vertices, faces, source_faces = simplify_mesh(mesh, target_faces)
    save_local_mesh(archive, output, vertices, faces, source_faces)
    print(
        f"IRON_MAN_MASK_IMPORT ok source_faces={source_faces} "
        f"optimized_faces={len(faces)} output={output}"
    )
    return output


def main() -> int:
    """Đọc tham số CLI và tạo Iron Man Mask low-poly dành riêng cho máy local."""
    parser = argparse.ArgumentParser(description="Import a local Iron Man Mask ZIP into ARIS.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-faces", type=int, default=14_000)
    arguments = parser.parse_args()
    import_iron_man_mask(
        arguments.archive.resolve(),
        arguments.output.resolve(),
        arguments.target_faces,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
