"""Stage external media into a draft folder and normalize video for Jianying.

Adapted from luoluoluo22/jianying-editor-skill (upstream ~1.7.0) media helpers:
copy assets into the draft so the project stays self-contained on macOS sandbox
and Jianying Pro 5.9+, and optionally re-encode video to an H.264/yuv420p profile.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from utils import media_normalizer as _mn


class MediaStageError(RuntimeError):
    pass


def is_inside_draft(draft_root: str | os.PathLike[str], media_path: str | os.PathLike[str]) -> bool:
    abs_draft = Path(draft_root).resolve()
    abs_media = Path(media_path).resolve()
    try:
        return abs_media.is_relative_to(abs_draft)
    except ValueError:
        return False


def _safe_subdir(subdir: str) -> str:
    name = (subdir or "").strip().replace("\\", "/").strip("/")
    if not name or name in {".", ".."} or name.startswith("../") or "/../" in f"/{name}/":
        raise MediaStageError(f"Unsafe media subdir: {subdir!r}")
    if Path(name).is_absolute() or (len(name) > 1 and name[1] == ":"):
        raise MediaStageError(f"Unsafe media subdir: {subdir!r}")
    return name


def stage_local_asset(
    draft_root: str | os.PathLike[str],
    media_path: str | os.PathLike[str],
    subdir: str = "materials",
) -> Path:
    """Copy media into ``<draft>/<subdir>/`` when it lives outside the draft.

    Returns the absolute path that should be referenced from the draft.
    Already-inside paths are returned unchanged. Failures after the source is
    verified raise MediaStageError; a missing source raises FileNotFoundError.
    """
    draft = Path(draft_root)
    if not draft.is_dir():
        raise MediaStageError(f"Draft root is not a directory: {draft}")
    src = Path(media_path)
    if not src.is_file():
        raise FileNotFoundError(f"Media not found: {src}")
    src = src.resolve()
    if is_inside_draft(draft, src):
        return src

    target_dir = (draft / _safe_subdir(subdir)).resolve()
    draft_resolved = draft.resolve()
    if not is_inside_draft(draft_resolved, target_dir):
        raise MediaStageError(f"Staging directory escapes draft: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)
    stat = src.stat()
    digest = hashlib.md5(f"{src}|{stat.st_size}|{int(stat.st_mtime)}".encode("utf-8")).hexdigest()
    staged = target_dir / f"{digest}{src.suffix.lower()}"
    if staged.exists() and staged.stat().st_size == stat.st_size:
        return staged
    temp = staged.with_name(staged.name + ".tmp")
    try:
        shutil.copy2(src, temp)
        os.replace(temp, staged)
    except OSError as exc:
        if temp.exists():
            temp.unlink(missing_ok=True)
        raise MediaStageError(f"Failed to copy media into draft: {exc}") from exc
    return staged


def normalize_video_for_jianying(
    input_path: str | os.PathLike[str],
    force: bool = False,
) -> Path | None:
    """Path-returning wrapper over the shared ``utils.media_normalizer`` logic.

    Resolves the input first so the caller's "already compatible" equality holds,
    and returns None when ffprobe/ffmpeg are unavailable so staging can fall back
    to the source instead of raising.
    """
    src = Path(input_path).resolve()
    if not src.is_file():
        return None
    try:
        out = _mn.normalize_video_for_jianying(str(src), force=force)
    except (FileNotFoundError, OSError):
        return None
    return Path(out).resolve() if out is not None else None


def prepare_media_for_draft(
    draft_root: str | os.PathLike[str],
    media_path: str | os.PathLike[str],
    normalize: bool = True,
    subdir: str = "materials",
) -> dict[str, Any]:
    """Normalize (optional) then stage into the draft. Returns a report dict."""
    src = Path(media_path)
    work = src
    normalized = False
    if normalize:
        candidate = normalize_video_for_jianying(src)
        if candidate is None:
            report_note = "normalize_skipped_or_failed"
            work = src
        elif candidate != src.resolve():
            work = candidate
            normalized = True
            report_note = "normalized"
        else:
            report_note = "already_compatible"
    else:
        report_note = "normalize_disabled"

    staged = stage_local_asset(draft_root, work, subdir=subdir)
    return {
        "source": str(src.resolve()),
        "staged_path": str(staged),
        "local_material_id": Path(staged).stem,
        "inside_draft": is_inside_draft(draft_root, staged),
        "normalized": normalized,
        "note": report_note,
    }
