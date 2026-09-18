"""Stage external media into a draft folder and normalize video for Jianying.

Adapted from luoluoluo22/jianying-editor-skill (upstream ~1.7.0) media helpers:
copy assets into the draft so the project stays self-contained on macOS sandbox
and Jianying Pro 5.9+, and optionally re-encode video to an H.264/yuv420p profile.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


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


def _norm_output_path(input_path: Path) -> Path:
    cache_dir = input_path.parent / "__jycache__"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{input_path.stem}.__jy_norm__.mp4"


def _is_cache_fresh(src: Path, dst: Path) -> bool:
    if not dst.is_file():
        return False
    try:
        return dst.stat().st_mtime >= src.stat().st_mtime
    except OSError:
        return False


def _probe_video(input_path: Path) -> dict[str, Any] | None:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,pix_fmt",
        "-of", "json", str(input_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        streams = json.loads(proc.stdout or "{}").get("streams", [])
    except json.JSONDecodeError:
        return None
    return streams[0] if streams else None


def should_normalize_video_for_jianying(input_path: str | os.PathLike[str]) -> bool:
    """True when re-encode is required; False when already friendly or probe failed."""
    info = _probe_video(Path(input_path))
    if not isinstance(info, dict) or not info:
        return False
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    return (
        info.get("codec_name") != "h264"
        or info.get("pix_fmt") != "yuv420p"
        or width <= 0
        or height <= 0
        or width % 16 != 0
        or height % 2 != 0
    )


def normalize_video_for_jianying(
    input_path: str | os.PathLike[str],
    force: bool = False,
) -> Path | None:
    """Return a Jianying-friendly MP4 path, or the source when already OK.

    Needs ``ffmpeg`` and ``ffprobe`` on PATH. Returns None when tools are
    missing, conversion fails, or a required re-encode cannot run.
    """
    src = Path(input_path).resolve()
    if not src.is_file():
        return None
    if not force:
        probe = _probe_video(src)
        if probe is None:
            return None
        if not should_normalize_video_for_jianying(src):
            return src

    dst = _norm_output_path(src)
    if _is_cache_fresh(src, dst):
        return dst

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-map", "0:v:0", "-map", "0:a?",
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(dst),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not dst.is_file():
        return None
    return dst


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
