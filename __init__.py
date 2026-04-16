"""Utility helpers for the imagelab package."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["reencode_with_vlc", "rename_avi_files", "extract_cardiac_keyframes"]


def __getattr__(name: str):
    if name == "reencode_with_vlc":
        from .vlc_reencode import reencode_with_vlc as func

        return func
    if name == "rename_avi_files":
        from .avi_md5_renamer import rename_avi_files as func

        return func
    if name == "extract_cardiac_keyframes":
        from .cardiac_keyframes import extract_cardiac_keyframes as func

        return func
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from .avi_md5_renamer import rename_avi_files
    from .cardiac_keyframes import extract_cardiac_keyframes
    from .vlc_reencode import reencode_with_vlc
