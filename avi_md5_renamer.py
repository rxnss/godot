#!/usr/bin/env python3
"""Rename AVI files to MD5-based filenames and record the mapping.

Each `.avi` discovered within the source directory is moved into the destination
directory with a new filename that is the MD5 digest of its relative path.
Records are persisted in a manifest text file where each line contains
`<new_filename>,<original_relative_path>`.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path
from typing import Iterable, Sequence, Tuple


def iter_avi_files(source_dir: Path) -> Iterable[Path]:
    """Yield AVI files beneath *source_dir* (case-insensitive suffix match)."""
    for path in source_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".avi":
            yield path


def md5_for_relative_path(relative_path: Path) -> str:
    """Return the hex digest for the relative path string."""
    rel_str = relative_path.as_posix()
    return hashlib.md5(rel_str.encode("utf-8")).hexdigest()


def rename_avi_files(
    source_dir: Path,
    destination_dir: Path,
    manifest_path: Path,
    *,
    overwrite_manifest: bool = False,
    dry_run: bool = False,
    dry_run_manifest: bool = False,
) -> Tuple[Tuple[str, Path], ...]:
    """
    Move AVI files from *source_dir* to *destination_dir* using MD5 filenames.

    Returns an immutable tuple of `(new_filename, original_relative_path)` pairs.
    """

    source_dir = source_dir.expanduser().resolve()
    destination_dir = destination_dir.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    if manifest_path.exists() and not overwrite_manifest:
        raise FileExistsError(
            f"Manifest file {manifest_path} already exists. "
            "Use --overwrite-manifest to replace it."
        )

    records: list[tuple[str, Path]] = []

    file_iter = sorted(iter_avi_files(source_dir))
    if not file_iter:
        raise FileNotFoundError(f"No .avi files found under {source_dir}")

    if dry_run:
        for src in file_iter:
            relative_path = src.relative_to(source_dir)
            digest = md5_for_relative_path(relative_path)
            new_filename = f"{digest}.avi"
            target_path = destination_dir / new_filename
            records.append((new_filename, relative_path))
            print(f"[DRY RUN] {src} -> {target_path}")

        if dry_run_manifest:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with manifest_path.open("w", encoding="utf-8") as handle:
                for new_filename, relative_path in records:
                    handle.write(f"{new_filename},{relative_path.as_posix()}\n")
        return tuple(records)

    destination_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", encoding="utf-8") as handle:
        for src in file_iter:
            relative_path = src.relative_to(source_dir)
            digest = md5_for_relative_path(relative_path)
            new_filename = f"{digest}.avi"
            target_path = destination_dir / new_filename

            if target_path.exists():
                raise FileExistsError(
                    f"Destination file already exists: {target_path} "
                    f"(from relative path {relative_path})"
                )

            shutil.move(str(src), str(target_path))

            records.append((new_filename, relative_path))
            handle.write(f"{new_filename}\t{relative_path.as_posix()}\n")


    return tuple(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rename .avi files to MD5-based names and record a mapping file."
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory to scan recursively for AVI files.",
    )
    parser.add_argument(
        "destination_dir",
        type=Path,
        help="Directory where renamed files will be stored.",
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Output text file where new_name,relative_path mappings are stored.",
    )
    parser.add_argument(
        "--overwrite-manifest",
        action="store_true",
        help="Allow replacing an existing manifest file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned moves without performing them.",
    )
    parser.add_argument(
        "--dry-run-manifest",
        action="store_true",
        help="When used with --dry-run, still create the manifest file.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rename_avi_files(
            args.source_dir,
            args.destination_dir,
            args.manifest,
            overwrite_manifest=args.overwrite_manifest,
            dry_run=args.dry_run,
            dry_run_manifest=args.dry_run_manifest,
        )
    except Exception as exc:  # pylint: disable=broad-except
        parser.error(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
