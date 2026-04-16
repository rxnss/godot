#!/usr/bin/env python3
"""Helper to re-encode video files into MP4 using VLC's command-line interface."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_VIDEO_EXTENSIONS = (
    ".avi",
    ".mov",
    ".mkv",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".flv",
    ".m4v",
    ".ts",
)


def _quote_command(cmd: Sequence[str]) -> str:
    """Return a shell-safe string representation of a VLC command."""
    return " ".join(shlex.quote(part) for part in cmd)


def reencode_with_vlc(
    input_video: Path | str,
    output_video: Path | str | None = None,
    *,
    vlc_bin: str | None = None,
    video_bitrate: int = 2500,
    audio_bitrate: int = 160,
    audio_channels: int = 2,
    audio_samplerate: int = 44100,
    overwrite: bool = False,
    dry_run: bool = False,
    extra_vlc_args: Iterable[str] | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.Popen:
    """
    Re-encode `input_video` into MP4 format using VLC.

    Parameters mirror the CLI arguments exposed by :func:`main`. When
    `dry_run` is True, the command is only printed and not executed.
    """

    input_path = Path(input_video).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    if output_video is None:
        output_path = input_path.with_suffix(".mp4")
    else:
        output_path = Path(output_video).expanduser().resolve()

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output {output_path} already exists. "
            "Use --overwrite to allow replacing it."
        )

    vlc_binary = vlc_bin or os.environ.get("VLC_BIN", "cvlc")
    if shutil.which(vlc_binary) is None:
        raise FileNotFoundError(
            f"Could not locate VLC executable '{vlc_binary}'. "
            "Set VLC_BIN or pass --vlc-bin to point to your VLC installation."
        )

    sout = (
        "#transcode{{vcodec=h264,vb={video_bitrate},acodec=mp4a,ab={audio_bitrate},"
        "channels={audio_channels},samplerate={audio_samplerate}}}"
        ':standard{{access=file,mux=mp4,dst="{output_path}"}}'
    ).format(
        video_bitrate=video_bitrate,
        audio_bitrate=audio_bitrate,
        audio_channels=audio_channels,
        audio_samplerate=audio_samplerate,
        output_path=str(output_path),
    )

    extra = list(extra_vlc_args or ())
    cmd = [
        vlc_binary,
        str(input_path),
        "--sout",
        sout,
        "--sout-keep",
        "--no-sout-all",
        *extra,
        "vlc://quit",
    ]

    if dry_run:
        print(_quote_command(cmd))
        # Align return type with subprocess.CompletedProcess when no process runs.
        return subprocess.CompletedProcess(cmd, 0)

    return subprocess.run(cmd, check=True, text=True)


def _normalize_extensions(extensions: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize CLI-provided extensions to `.ext` lowercase format."""
    if not extensions:
        return DEFAULT_VIDEO_EXTENSIONS
    normalized: list[str] = []
    for ext in extensions:
        clean = ext.strip().lower()
        if not clean:
            continue
        if not clean.startswith("."):
            clean = f".{clean}"
        normalized.append(clean)
    return tuple(normalized) or DEFAULT_VIDEO_EXTENSIONS


def iter_videos(directory: Path, extensions: Iterable[str]) -> Iterable[Path]:
    """Yield files in *directory* that match the provided extensions."""
    allowed = set(ext.lower() for ext in extensions)
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix.lower() in allowed:
            yield path


def reencode_directory(
    directory: Path,
    *,
    extensions: Iterable[str],
    vlc_bin: str | None = None,
    video_bitrate: int = 2500,
    audio_bitrate: int = 160,
    audio_channels: int = 2,
    audio_samplerate: int = 44100,
    overwrite: bool = False,
    dry_run: bool = False,
    extra_vlc_args: Iterable[str] | None = None,
) -> list[subprocess.CompletedProcess[str] | subprocess.Popen]:
    """Re-encode every supported video file under *directory* in-place."""

    directory = directory.expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    collected = sorted(iter_videos(directory, extensions))
    if not collected:
        raise FileNotFoundError(
            f"No video files ({', '.join(extensions)}) found under {directory}"
        )

    results = []
    for video_path in collected:
        results.append(
            reencode_with_vlc(
                video_path,
                None,
                vlc_bin=vlc_bin,
                video_bitrate=video_bitrate,
                audio_bitrate=audio_bitrate,
                audio_channels=audio_channels,
                audio_samplerate=audio_samplerate,
                overwrite=overwrite,
                dry_run=dry_run,
                extra_vlc_args=extra_vlc_args,
            )
        )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Use VLC (cvlc) to re-encode a video file (or all files within a directory) "
            "into MP4 containers with H.264 video and AAC audio."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the source video file or directory to scan.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Destination MP4 path (defaults to INPUT with .mp4 extension).",
    )
    parser.add_argument(
        "--vlc-bin",
        default=None,
        help="VLC executable to call (defaults to VLC_BIN env var or 'cvlc').",
    )
    parser.add_argument(
        "--video-bitrate",
        type=int,
        default=2500,
        help="Video bitrate in kbps (default: 2500).",
    )
    parser.add_argument(
        "--audio-bitrate",
        type=int,
        default=160,
        help="Audio bitrate in kbps (default: 160).",
    )
    parser.add_argument(
        "--audio-channels",
        type=int,
        default=2,
        help="Number of audio channels in the output (default: 2).",
    )
    parser.add_argument(
        "--audio-samplerate",
        type=int,
        default=44100,
        help="Audio sample rate in Hz (default: 44100).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the VLC command without running it.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=None,
        metavar="EXT",
        help=(
            "File extensions (without dot) to include when INPUT is a directory. "
            "Defaults to common video types."
        ),
    )
    parser.add_argument(
        "--extra-vlc-arg",
        action="append",
        default=None,
        metavar="ARG",
        help="Additional argument to pass directly to VLC (can be repeated).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = args.input.expanduser()
    extra_vlc_args = args.extra_vlc_arg
    try:
        if input_path.is_dir():
            if args.output is not None:
                parser.error("--output cannot be used when INPUT is a directory.")
            extensions = _normalize_extensions(args.extensions)
            reencode_directory(
                input_path,
                extensions=extensions,
                vlc_bin=args.vlc_bin,
                video_bitrate=args.video_bitrate,
                audio_bitrate=args.audio_bitrate,
                audio_channels=args.audio_channels,
                audio_samplerate=args.audio_samplerate,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                extra_vlc_args=extra_vlc_args,
            )
        else:
            if args.extensions:
                parser.error("--extensions is only valid when INPUT is a directory.")
            reencode_with_vlc(
                input_path,
                args.output,
                vlc_bin=args.vlc_bin,
                video_bitrate=args.video_bitrate,
                audio_bitrate=args.audio_bitrate,
                audio_channels=args.audio_channels,
                audio_samplerate=args.audio_samplerate,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                extra_vlc_args=extra_vlc_args,
            )
    except Exception as exc:  # pylint: disable=broad-except
        parser.error(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
