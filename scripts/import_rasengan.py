from __future__ import annotations

import argparse
from pathlib import Path

from archive_mesh_utils import load_stl_members, save_local_mesh, simplify_mesh

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "user_models" / "rasengan_local.npz"


def import_rasengan(
    archive: Path,
    output: Path,
    target_faces: int = 6_000,
) -> Path:
    """Tối ưu STL Rasengan trong ZIP thành mesh năng lượng local nhẹ cho HUD."""
    if not archive.is_file():
        raise FileNotFoundError(f"Missing Rasengan archive: {archive}")
    mesh = load_stl_members(archive, ("my_model.stl",))
    vertices, faces, source_faces = simplify_mesh(mesh, target_faces)
    save_local_mesh(archive, output, vertices, faces, source_faces)
    print(
        f"RASENGAN_IMPORT ok source_faces={source_faces} "
        f"optimized_faces={len(faces)} output={output}"
    )
    return output


def main() -> int:
    """Đọc tham số CLI và tạo Rasengan low-poly dành riêng cho máy local."""
    parser = argparse.ArgumentParser(description="Import a local Rasengan ZIP into ARIS.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-faces", type=int, default=6_000)
    arguments = parser.parse_args()
    import_rasengan(
        arguments.archive.resolve(),
        arguments.output.resolve(),
        arguments.target_faces,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
