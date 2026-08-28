from __future__ import annotations

import argparse
from pathlib import Path

from archive_mesh_utils import load_3mf_members, save_local_mesh, simplify_mesh

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "user_models" / "minato_kunai_local.npz"
ASSEMBLED_MEMBERS = (
    "Hiraishin Shaft and ring.3mf",
    "Hiraishin Blade Top.3mf",
    "Hiraishin Blade Bottom.3mf",
    "Hiraishin Handle Top.3mf",
    "Hiraishin Handle Bottom.3mf",
)


def import_minato_kunai(
    archive: Path,
    output: Path,
    target_faces: int = 14_000,
) -> Path:
    """Ghép các nửa 3MF theo tọa độ build, dựng kunai thẳng đứng và lưu local."""
    if not archive.is_file():
        raise FileNotFoundError(f"Missing Minato Kunai archive: {archive}")
    mesh = load_3mf_members(archive, ASSEMBLED_MEMBERS)
    vertices, faces, source_faces = simplify_mesh(mesh, target_faces)
    # Model dài theo X; đổi X thành Z để lưỡi hướng lên trong camera ARIS.
    oriented = vertices[:, (1, 2, 0)].copy()
    oriented[:, 1] *= -1.0
    save_local_mesh(archive, output, oriented, faces, source_faces)
    print(
        f"MINATO_KUNAI_IMPORT ok source_faces={source_faces} "
        f"optimized_faces={len(faces)} output={output}"
    )
    return output


def main() -> int:
    """Đọc tham số CLI và tạo Minato Kunai low-poly dành riêng cho máy local."""
    parser = argparse.ArgumentParser(description="Import a local Minato Kunai ZIP into ARIS.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-faces", type=int, default=14_000)
    arguments = parser.parse_args()
    import_minato_kunai(
        arguments.archive.resolve(),
        arguments.output.resolve(),
        arguments.target_faces,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
