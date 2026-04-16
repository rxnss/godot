#!/usr/bin/env python3
"""Extract bright/dim key frames from cardiac ultrasound videos."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np

# Default extensions that will be scanned within source directories.
DEFAULT_EXTENSIONS = (
    ".avi",
    ".mov",
    ".mp4",
    ".mpg",
    ".mpeg",
    ".mkv",
    ".m4v",
    ".wmv",
)


@dataclass(frozen=True)
class KeyFrame:
    """Metadata describing a detected key frame."""

    frame_index: int
    frame_type: str  # "max" (bright) or "min" (dim)
    cycle_index: int
    brightness: float
    output_path: Path


def _normalize_extensions(extensions: Iterable[str] | None) -> tuple[str, ...]:
    if not extensions:
        return DEFAULT_EXTENSIONS
    normalized: list[str] = []
    for ext in extensions:
        clean = ext.strip().lower()
        if not clean:
            continue
        if not clean.startswith("."):
            clean = f".{clean}"
        normalized.append(clean)
    return tuple(normalized) or DEFAULT_EXTENSIONS


def _iter_videos(source_dir: Path, extensions: Iterable[str]) -> Iterable[Path]:
    allowed = set(ext.lower() for ext in extensions)
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in allowed:
            yield path


def _compute_brightness_series(video_path: Path) -> list[float]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    brightness: list[float] = []
    success, frame = cap.read()
    while success:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness.append(float(gray.mean()))
        success, frame = cap.read()
    cap.release()
    if not brightness:
        raise RuntimeError(f"No frames decoded from {video_path}")
    return brightness


def _find_local_extrema(
    series: Sequence[float],
    *,
    neighborhood: int,
    min_gap: int,
    min_contrast: float,
    mode: str,
) -> list[int]:
    """Return frame indices that qualify as local maxima/minima."""

    assert mode in {"max", "min"}
    comparator = max if mode == "max" else min
    extremal_indices: list[int] = []
    last_selected = -min_gap
    n = len(series)

    for idx, value in enumerate(series):
        window_start = max(0, idx - neighborhood)
        window_end = min(n, idx + neighborhood + 1)
        window = series[window_start:window_end]
        if not window:
            continue
        extremal_value = comparator(window)
        if value != extremal_value:
            continue
        if idx - last_selected < min_gap:
            continue
        neighborhood_mean = float(np.mean(window))
        contrast = (value - neighborhood_mean) if mode == "max" else (neighborhood_mean - value)
        if contrast < min_contrast:
            continue
        extremal_indices.append(idx)
        last_selected = idx
    return extremal_indices


def _pair_cycles(maxima: Sequence[int], minima: Sequence[int]) -> list[tuple[int, int]]:
    """Pair maxima with the next minima to approximate cardiac cycles."""

    paired: list[tuple[int, int]] = []
    min_pos = 0
    for max_idx in maxima:
        while min_pos < len(minima) and minima[min_pos] <= max_idx:
            min_pos += 1
        if min_pos >= len(minima):
            break
        paired.append((max_idx, minima[min_pos]))
        min_pos += 1
    return paired


def _write_frame(
    image: np.ndarray,
    output_path: Path,
    *,
    image_format: str,
    jpeg_quality: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ext = image_format.lower()
    params: list[int] = []
    if ext in {"jpg", "jpeg"}:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
    elif ext == "png":
        params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
    success = cv2.imwrite(str(output_path), image, params)
    if not success:
        raise RuntimeError(f"Failed to write frame to {output_path}")


def _capture_frames(
    video_path: Path,
    keyframes: Sequence[KeyFrame],
    *,
    image_format: str,
    jpeg_quality: int,
) -> None:
    if not keyframes:
        return
    targets: dict[int, list[KeyFrame]] = {}
    for meta in keyframes:
        targets.setdefault(meta.frame_index, []).append(meta)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to reopen video for saving frames: {video_path}")

    frame_idx = 0
    success, frame = cap.read()
    remaining = set(targets.keys())
    while success and remaining:
        if frame_idx in targets:
            for meta in targets[frame_idx]:
                _write_frame(
                    frame,
                    meta.output_path,
                    image_format=image_format,
                    jpeg_quality=jpeg_quality,
                )
            remaining.remove(frame_idx)
        frame_idx += 1
        success, frame = cap.read()
    cap.release()
    if remaining:
        raise RuntimeError(
            f"Could not capture requested frames {sorted(remaining)} from {video_path}"
        )


def extract_key_frames_for_video(
    video_path: Path,
    *,
    relative_path: Path,
    output_root: Path,
    neighborhood: int,
    min_gap: int,
    min_contrast: float,
    image_format: str,
    jpeg_quality: int,
    dry_run: bool,
    skip_if_exists: bool = True,
) -> list[KeyFrame]:
    """Detect key frames for a single video and optionally save them."""

    brightness = _compute_brightness_series(video_path)
    maxima = _find_local_extrema(
        brightness,
        neighborhood=neighborhood,
        min_gap=min_gap,
        min_contrast=min_contrast,
        mode="max",
    )
    minima = _find_local_extrema(
        brightness,
        neighborhood=neighborhood,
        min_gap=min_gap,
        min_contrast=min_contrast,
        mode="min",
    )
    pairs = _pair_cycles(maxima, minima)
    if not pairs:
        return []

    dest_dir = (output_root / relative_path.parent).resolve()
    video_stem = relative_path.stem
    image_format = image_format.lower().lstrip(".")

    keyframes: list[KeyFrame] = []
    for cycle_index, (max_idx, min_idx) in enumerate(pairs, start=1):
        max_path = (
            dest_dir
            / f"{video_stem}_c{cycle_index:02d}_f{max_idx:04d}_b.{image_format}"
        )
        min_path = (
            dest_dir
            / f"{video_stem}_c{cycle_index:02d}_f{min_idx:04d}_d.{image_format}"
        )
        keyframes.append(
            KeyFrame(
                frame_index=max_idx,
                frame_type="bright",
                cycle_index=cycle_index,
                brightness=brightness[max_idx],
                output_path=max_path,
            )
        )
        keyframes.append(
            KeyFrame(
                frame_index=min_idx,
                frame_type="dim",
                cycle_index=cycle_index,
                brightness=brightness[min_idx],
                output_path=min_path,
            )
        )

    if skip_if_exists:
        all_exist = all(meta.output_path.exists() for meta in keyframes)
        if all_exist:
            print(f"[SKIP] Frames already exist for {video_path}")
            return keyframes

    if dry_run:
        for meta in keyframes:
            print(
                f"[DRY RUN] {video_path} frame {meta.frame_index} "
                f"({meta.frame_type}) -> {meta.output_path}"
            )
        return keyframes

    _capture_frames(
        video_path,
        keyframes,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
    )
    return keyframes


def extract_cardiac_keyframes(
    source_dir: Path,
    output_dir: Path,
    *,
    extensions: Iterable[str] | None = None,
    neighborhood: int = 8,
    min_gap: int = 5,
    min_contrast: float = 8.0,
    image_format: str = "jpg",
    jpeg_quality: int = 95,
    dry_run: bool = False,
    max_videos: int | None = None,
    skip_if_exists: bool = True,
) -> dict[Path, list[KeyFrame]]:
    """Extract bright/dim key frames for every cardiac video under *source_dir*."""

    source_dir = source_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    extensions = _normalize_extensions(extensions)
    results: dict[Path, list[KeyFrame]] = {}
    count = 0
    failures: dict[Path, str] = {}
    for video_path in _iter_videos(source_dir, extensions):
        relative_path = video_path.relative_to(source_dir)
        count += 1
        print(f"[INFO] Processing ({count}) {relative_path}")
        try:
            keyframes = extract_key_frames_for_video(
                video_path,
                relative_path=relative_path,
                output_root=output_dir,
                neighborhood=neighborhood,
                min_gap=min_gap,
                min_contrast=min_contrast,
                image_format=image_format,
                jpeg_quality=jpeg_quality,
                dry_run=dry_run,
                skip_if_exists=skip_if_exists,
            )
        except Exception as exc:  # pylint: disable=broad-except
            failures[relative_path] = str(exc)
            print(f"[WARN] Failed to process {relative_path}: {exc}")
            continue
        results[relative_path] = keyframes
        if max_videos is not None and count >= max_videos:
            break
    if failures:
        failed_list = ", ".join(str(path) for path in failures)
        print(f"[WARN] Completed with {len(failures)} failures: {failed_list}")
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Detect bright/dim key frames from cardiac ultrasound videos within "
            "a source directory. Each cycle produces two frames saved beside the video."
        )
    )
    parser.add_argument("source_dir", type=Path, help="Directory containing videos.")
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory where extracted frames will be written.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=None,
        metavar="EXT",
        help="Video extensions to scan (defaults to common types).",
    )
    parser.add_argument(
        "--neighborhood",
        type=int,
        default=8,
        help="Half-window size (in frames) for local max/min detection.",
    )
    parser.add_argument(
        "--min-gap",
        type=int,
        default=5,
        help="Minimum frame distance between detected extrema.",
    )
    parser.add_argument(
        "--min-contrast",
        type=float,
        default=8.0,
        help="Minimum brightness difference from local mean to keep an extremum.",
    )
    parser.add_argument(
        "--image-format",
        choices=("jpg", "jpeg", "png"),
        default="jpg",
        help="Image format for saved frames.",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=95,
        help="JPEG quality (only used when --image-format=jpg/jpeg).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned extractions without writing files.",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        help="Optional limit for the number of videos to process.",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Reprocess videos even if output frames already exist.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        extract_cardiac_keyframes(
            args.source_dir,
            args.output_dir,
            extensions=args.extensions,
            neighborhood=args.neighborhood,
            min_gap=args.min_gap,
            min_contrast=args.min_contrast,
            image_format=args.image_format,
            jpeg_quality=args.jpeg_quality,
            dry_run=args.dry_run,
            max_videos=args.max_videos,
            skip_if_exists=not args.no_skip_existing,
        )
    except Exception as exc:  # pylint: disable=broad-except
        parser.error(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
