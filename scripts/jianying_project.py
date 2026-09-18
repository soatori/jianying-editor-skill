"""Canonical inspector and safe mutation runtime for existing Jianying drafts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jy_draft_crypto import JyDraftCrypto, parse_plain_json


KNOWN_REPLICA_NAMES = ("draft_content.json", ".bak", "template-2.tmp", "draft_content.json.bak")
REPLICA_ROLE_BY_NAME = {
    "draft_content.json": "primary",
    ".bak": "writable-backup",
    "template-2.tmp": "writable-template",
    "draft_content.json.bak": "writable-backup",
}
TIMERANGE_KEYS = {"target_timerange", "source_timerange", "render_timerange"}
DEFAULT_LOCATE_TOLERANCE_US = 40_000


class ProjectError(RuntimeError):
    pass


@dataclass
class DecodedFile:
    path: Path
    value: dict[str, Any]
    encoding: str


def _json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _start(timerange: dict[str, Any] | None) -> int:
    return int((timerange or {}).get("start", 0) or 0)


def _duration(timerange: dict[str, Any] | None) -> int:
    return int((timerange or {}).get("duration", 0) or 0)


def _end(timerange: dict[str, Any] | None) -> int:
    return _start(timerange) + _duration(timerange)


def _exact_replace(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return new if value == old else value
    if isinstance(value, list):
        return [_exact_replace(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _exact_replace(item, old, new) for key, item in value.items()}
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _semantic_normalize(value: Any, parent_key: str | None = None) -> Any:
    """Normalize only representation differences Jianying commonly introduces."""
    if isinstance(value, dict):
        normalized = {
            key: _semantic_normalize(item, key)
            for key, item in value.items()
        }
        if parent_key in TIMERANGE_KEYS and "start" not in normalized:
            normalized["start"] = 0
        return normalized
    if isinstance(value, list):
        return [_semantic_normalize(item, parent_key) for item in value]
    return value


def _semantic_equal(left: Any, right: Any) -> bool:
    return _semantic_normalize(left) == _semantic_normalize(right)


def _text_from_value(value: Any) -> str:
    """Collect likely visible text without making a schema-specific assumption."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(item for item in (_text_from_value(v) for v in value) if item)
    if isinstance(value, dict):
        preferred = []
        for key in ("text", "content", "base_content", "recognize_text", "text_content"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                preferred.append(item.strip())
        if preferred:
            return " ".join(dict.fromkeys(preferred))
        return ""
    return ""


class JianyingProject:
    def __init__(self, root: str | os.PathLike[str], dll_path: str | None = None):
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ProjectError(f"Draft directory does not exist: {self.root}")
        self.dll_path = dll_path
        self._crypto: JyDraftCrypto | None = None
        self.timelines_dir = self.root / "Timelines"
        self.project_index_path = next(
            (p for p in (self.timelines_dir / "project.json", self.root / "project.json") if p.is_file()),
            None,
        )
        self.project_index = _json_file(self.project_index_path) if self.project_index_path else None
        self.layout_path = self.root / "timeline_layout.json"
        self.layout_data = _json_file(self.layout_path)

    @property
    def crypto(self) -> JyDraftCrypto:
        if self._crypto is None:
            self._crypto = JyDraftCrypto(self.dll_path)
        return self._crypto

    def decode(self, path: Path) -> DecodedFile:
        data = path.read_bytes()
        plain = parse_plain_json(data)
        if plain is not None:
            return DecodedFile(path, plain, "plaintext")
        try:
            value = self.crypto.decrypt_json(data)
        except Exception as exc:
            raise ProjectError(f"Cannot parse or decrypt {path}: {exc}") from exc
        return DecodedFile(path, value, "jianying-dll")

    def timeline_entries(self) -> list[dict[str, Any]]:
        if self.project_index and isinstance(self.project_index.get("timelines"), list):
            return [item for item in self.project_index["timelines"] if isinstance(item, dict)]
        root_content = self.root / "draft_content.json"
        if root_content.is_file():
            decoded = self.decode(root_content)
            timeline_id = str(decoded.value.get("id") or "legacy-root")
            return [{"id": timeline_id, "name": self.root.name, "is_marked_delete": False}]
        return []

    def _entry_map(self) -> dict[str, dict[str, Any]]:
        return {str(item.get("id")): item for item in self.timeline_entries() if item.get("id")}

    def active_evidence(self) -> list[dict[str, str]]:
        known = self._entry_map()
        evidence: list[dict[str, str]] = []
        if self.layout_data:
            for key in ("activeTimeline", "active_timeline_id", "timeline_id"):
                value = self.layout_data.get(key)
                if isinstance(value, str) and value in known:
                    evidence.append({"id": value, "source": f"timeline_layout.json:{key}"})
                    break
        root_content = self.root / "draft_content.json"
        if root_content.is_file():
            try:
                root_id = str(self.decode(root_content).value.get("id") or "")
                if root_id in known:
                    evidence.append({"id": root_id, "source": "root draft_content.json:id"})
            except ProjectError:
                pass
        if self.project_index:
            value = self.project_index.get("main_timeline_id")
            if isinstance(value, str) and value in known:
                evidence.append({"id": value, "source": "project index:main_timeline_id"})
        remaining = [item for item in known.values() if not item.get("is_marked_delete", False)]
        if len(remaining) == 1:
            evidence.append({"id": str(remaining[0]["id"]), "source": "sole non-deleted timeline"})
        return evidence

    def active_timeline_id(self) -> str | None:
        evidence = self.active_evidence()
        layout = next((item["id"] for item in evidence if item["source"].startswith("timeline_layout")), None)
        if layout:
            return layout
        root = next((item["id"] for item in evidence if item["source"].startswith("root ")), None)
        if root:
            return root
        main = next((item["id"] for item in evidence if "main_timeline_id" in item["source"]), None)
        if main:
            return main
        unique = {item["id"] for item in evidence}
        return next(iter(unique)) if len(unique) == 1 else None

    def resolve_timeline(self, selector: str) -> dict[str, Any]:
        entries = self.timeline_entries()
        if selector == "active":
            timeline_id = self.active_timeline_id()
            if not timeline_id:
                raise ProjectError("Active timeline is ambiguous; specify an ID or exact name")
            selector = timeline_id
        matches = [
            item for item in entries
            if str(item.get("id")) == selector or str(item.get("name")) == selector
        ]
        if len(matches) != 1:
            raise ProjectError(f"Timeline selector must match exactly one entry: {selector!r} ({len(matches)} matches)")
        return matches[0]

    def content_path(self, timeline_id: str) -> Path:
        candidate = self.timelines_dir / timeline_id / "draft_content.json"
        if candidate.is_file():
            return candidate
        root = self.root / "draft_content.json"
        if root.is_file():
            decoded = self.decode(root)
            content_id = str(decoded.value.get("id") or "")
            if content_id == timeline_id:
                return root
            # Legacy single drafts may carry an empty content id; "legacy-root"
            # is the only sanctioned alias (see timeline_entries). Matching an
            # empty id against an arbitrary selector would fail open in hybrid
            # layouts and could return the wrong timeline's content.
            if not content_id and timeline_id == "legacy-root" and not self.project_index:
                return root
        raise ProjectError(f"No primary content file found for timeline {timeline_id}")

    def _candidate_replica_paths(self, timeline_id: str, include_root_mirror: bool = True) -> list[Path]:
        """Return observed content candidates; do not assume a replica count."""
        paths: list[Path] = []
        directory = self.timelines_dir / timeline_id
        for name in KNOWN_REPLICA_NAMES:
            candidate = directory / name
            if candidate.is_file():
                paths.append(candidate)

        primary = self.content_path(timeline_id)
        if primary not in paths:
            paths.insert(0, primary)

        if include_root_mirror:
            root_primary = self.root / "draft_content.json"
            root_matches = False
            if root_primary.is_file():
                try:
                    root_matches = str(self.decode(root_primary).value.get("id") or "") == timeline_id
                except ProjectError:
                    root_matches = False
            # A root content file can represent the main/default timeline even
            # when timeline_layout points at another active timeline.  Treat it
            # as a replica only when its decoded ID positively matches.
            if root_matches:
                for name in KNOWN_REPLICA_NAMES:
                    candidate = self.root / name
                    if candidate.is_file() and candidate not in paths:
                        paths.append(candidate)
        return paths

    def replica_manifest(self, timeline_id: str, include_root_mirror: bool = True) -> dict[str, Any]:
        """Describe only positively associated observed replicas and their roles."""
        primary = self.content_path(timeline_id)
        replicas: list[dict[str, Any]] = []
        errors: list[str] = []
        for path in self._candidate_replica_paths(timeline_id, include_root_mirror):
            item: dict[str, Any] = {
                "path": str(path),
                "relative_path": str(path.relative_to(self.root)),
                "name": path.name,
                "role": REPLICA_ROLE_BY_NAME.get(path.name, "observed-content"),
                "primary": path == primary,
                "writable": path.name in KNOWN_REPLICA_NAMES,
                "sha256": _sha256(path.read_bytes()),
            }
            try:
                decoded = self.decode(path)
                item.update({
                    "encoding": decoded.encoding,
                    "content_id": str(decoded.value.get("id") or ""),
                    "associated": str(decoded.value.get("id") or "") == timeline_id,
                })
            except ProjectError as exc:
                item.update({"encoding": "unknown", "content_id": None, "associated": False})
                errors.append(f"{path}: {exc}")
            if item.get("associated"):
                replicas.append(item)
            else:
                errors.append(f"Unassociated content candidate: {path}")
        return {
            "timeline_id": timeline_id,
            "primary": str(primary),
            "replicas": replicas,
            "errors": errors,
            "count": len(replicas),
        }

    def replica_paths(self, timeline_id: str, include_root_mirror: bool = True) -> list[Path]:
        manifest = self.replica_manifest(timeline_id, include_root_mirror)
        if manifest["errors"]:
            raise ProjectError("Replica manifest is not safe: " + "; ".join(manifest["errors"]))
        return [Path(item["path"]) for item in manifest["replicas"]]

    def layout_kind(self) -> str:
        has_root = (self.root / "draft_content.json").is_file()
        has_index = self.project_index_path is not None and bool(self.timeline_entries())
        has_per_timeline = any((self.timelines_dir / str(item.get("id")) / "draft_content.json").is_file()
                               for item in self.timeline_entries())
        if has_index and has_per_timeline and has_root:
            return "hybrid"
        if has_index and has_per_timeline:
            return "multi-timeline"
        if has_root and not has_index:
            return "legacy-single"
        return "unknown"

    def probe(self) -> dict[str, Any]:
        timelines = []
        for entry in self.timeline_entries():
            timeline_id = str(entry.get("id"))
            try:
                decoded = self.decode(self.content_path(timeline_id))
                status = decoded.encoding
                duration = int(decoded.value.get("duration", 0) or 0)
                content_id = decoded.value.get("id")
                manifest = self.replica_manifest(timeline_id)
            except ProjectError as exc:
                status, duration, content_id, manifest = "unknown", None, None, {"replicas": [], "errors": [str(exc)], "count": 0}
                entry = {**entry, "error": str(exc)}
            timelines.append({
                "id": timeline_id,
                "name": entry.get("name"),
                "deleted": bool(entry.get("is_marked_delete", False)),
                "content_id": content_id,
                "encoding": status,
                "duration_us": duration,
                "replicas": manifest["replicas"],
                "replica_errors": manifest["errors"],
            })
        return {
            "root": str(self.root),
            "layout": self.layout_kind(),
            "project_index": str(self.project_index_path) if self.project_index_path else None,
            "active_timeline_id": self.active_timeline_id(),
            "active_evidence": self.active_evidence(),
            "timelines": timelines,
        }

    def inspect(self, selector: str, include_segments: bool = True) -> dict[str, Any]:
        entry = self.resolve_timeline(selector)
        timeline_id = str(entry["id"])
        decoded = self.decode(self.content_path(timeline_id))
        tracks = []
        for track in decoded.value.get("tracks", []):
            if not isinstance(track, dict):
                continue
            item = {
                "id": track.get("id"), "name": track.get("name"), "type": track.get("type"),
                "segment_count": len(track.get("segments", [])) if isinstance(track.get("segments"), list) else 0,
            }
            if include_segments:
                item["segments"] = [self._segment_summary(segment) for segment in track.get("segments", [])
                                    if isinstance(segment, dict)]
            tracks.append(item)
        materials = decoded.value.get("materials", {})
        material_counts = {
            key: len(value) for key, value in materials.items()
            if isinstance(materials, dict) and isinstance(value, list)
        }
        return {
            "id": timeline_id,
            "name": entry.get("name"),
            "encoding": decoded.encoding,
            "content_path": str(decoded.path),
            "replica_manifest": self.replica_manifest(timeline_id),
            "replica_paths": [str(path) for path in self.replica_paths(timeline_id)],
            "duration_us": int(decoded.value.get("duration", 0) or 0),
            "tracks": tracks,
            "material_counts": material_counts,
        }

    @staticmethod
    def _segment_summary(segment: dict[str, Any]) -> dict[str, Any]:
        target = segment.get("target_timerange") or {}
        source = segment.get("source_timerange") or {}
        return {
            "id": segment.get("id"), "material_id": segment.get("material_id"),
            "target_start_us": _start(target), "target_duration_us": _duration(target),
            "source_start_us": _start(source), "source_duration_us": _duration(source),
        }

    def validate(self, selector: str) -> dict[str, Any]:
        entry = self.resolve_timeline(selector)
        timeline_id = str(entry["id"])
        decoded = self.decode(self.content_path(timeline_id))
        result = validate_content(decoded.value, expected_id=timeline_id)
        manifest = self.replica_manifest(timeline_id)
        result["errors"].extend(manifest["errors"])
        replicas = [Path(item["path"]) for item in manifest["replicas"]]
        canonical = decoded.value
        for path in replicas:
            other = self.decode(path)
            if not _semantic_equal(other.value, canonical):
                result["errors"].append(f"Replica differs from primary: {path}")
        result.update({
            "timeline_id": timeline_id,
            "replicas_checked": len(replicas),
            "replica_manifest": manifest,
        })
        result["ok"] = not result["errors"]
        return result

    def locate(
        self,
        selector: str,
        *,
        segment_id: str | None = None,
        track_id: str | None = None,
        track_type: str | None = None,
        start_us: int | None = None,
        text: str | None = None,
        tolerance_us: int = DEFAULT_LOCATE_TOLERANCE_US,
    ) -> dict[str, Any]:
        """Locate segments with frame-safe time tolerance and explicit assertions."""
        if tolerance_us < 0:
            raise ProjectError("tolerance_us must be non-negative")
        entry = self.resolve_timeline(selector)
        timeline_id = str(entry["id"])
        decoded = self.decode(self.content_path(timeline_id))
        materials = decoded.value.get("materials", {})
        matches: list[dict[str, Any]] = []
        for track in decoded.value.get("tracks", []):
            if not isinstance(track, dict):
                continue
            if track_id is not None and str(track.get("id")) != track_id:
                continue
            if track_type is not None and str(track.get("type")) != track_type:
                continue
            for segment in track.get("segments", []):
                if not isinstance(segment, dict):
                    continue
                if segment_id is not None and str(segment.get("id")) != segment_id:
                    continue
                target = segment.get("target_timerange") or {}
                candidate_start = _start(target)
                if start_us is not None and abs(candidate_start - start_us) > tolerance_us:
                    continue
                segment_text = _text_from_value(segment)
                if not segment_text and isinstance(materials, dict):
                    material_id = str(segment.get("material_id") or "")
                    for bucket in materials.values():
                        if not isinstance(bucket, list):
                            continue
                        material = next(
                            (item for item in bucket if isinstance(item, dict) and str(item.get("id")) == material_id),
                            None,
                        )
                        if material:
                            segment_text = _text_from_value(material)
                            break
                if text and text not in segment_text:
                    continue
                matches.append({
                    "timeline_id": timeline_id,
                    "track_id": track.get("id"),
                    "track_type": track.get("type"),
                    "track_name": track.get("name"),
                    "segment_id": segment.get("id"),
                    "material_id": segment.get("material_id"),
                    "target_start_us": candidate_start,
                    "target_duration_us": _duration(target),
                    "text": segment_text,
                    "start_delta_us": None if start_us is None else candidate_start - start_us,
                })
        return {
            "ok": True,
            "timeline_id": timeline_id,
            "tolerance_us": tolerance_us,
            "query": {
                "segment_id": segment_id,
                "track_id": track_id,
                "track_type": track_type,
                "start_us": start_us,
                "text": text,
            },
            "matches": matches,
            "match_count": len(matches),
        }

    def resolve_locator(
        self,
        selector: str,
        locator: dict[str, Any],
        *,
        tolerance_us: int = DEFAULT_LOCATE_TOLERANCE_US,
    ) -> dict[str, Any]:
        """Resolve one upstream locator or fail closed on zero/multiple matches."""
        if not isinstance(locator, dict):
            raise ProjectError("Locator must be an object")
        result = self.locate(
            selector,
            segment_id=locator.get("segment_id"),
            track_id=locator.get("track_id"),
            track_type=locator.get("track_type"),
            start_us=next(
                (
                    locator.get(field)
                    for field in ("start_us", "target_start_us", "phrase_start_us")
                    if locator.get(field) is not None
                ),
                None,
            ),
            text=locator.get("text"),
            tolerance_us=tolerance_us,
        )
        matches = result["matches"]
        if len(matches) != 1:
            raise ProjectError(
                f"Locator did not resolve uniquely ({len(matches)} matches): {locator}"
            )
        return matches[0]

    def _assert_editor_closed(self) -> None:
        if os.name != "nt":
            return
        proc = subprocess.run(["tasklist"], capture_output=True, text=True, errors="ignore", check=False)
        lowered = proc.stdout.lower()
        active = [name for name in ("jianyingpro.exe", "jianyingprotray.exe") if name in lowered]
        if active:
            raise ProjectError("Close Jianying and its tray process before mutation: " + ", ".join(active))

    def _snapshot(self, paths: Iterable[Path]) -> tuple[Path, dict[str, Any]]:
        transaction = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        directory = self.root / ".jianying-editor-backups" / transaction
        directory.mkdir(parents=True, exist_ok=False)
        files = []
        for path in dict.fromkeys(Path(p).resolve() for p in paths):
            if not path.exists():
                continue
            relative = path.relative_to(self.root)
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            target.write_bytes(data)
            files.append({"path": str(relative), "sha256": _sha256(data)})
        manifest = {"root": str(self.root), "created_at": time.time(), "files": files}
        (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return directory, manifest

    def _encode_for(self, value: dict[str, Any], mode: str) -> bytes:
        if mode == "plaintext":
            return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if mode == "jianying-dll":
            return self.crypto.encrypt_json(value)
        raise ProjectError(f"Unsupported output encoding: {mode}")

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _restore_snapshot(self, backup: Path, manifest: dict[str, Any], created: Iterable[Path] = ()) -> None:
        for path in created:
            if path.exists():
                path.unlink()
        for item in manifest["files"]:
            relative = Path(item["path"])
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / relative, target)

    def _write_content(self, timeline_id: str, value: dict[str, Any], include_root: bool = True) -> dict[str, Any]:
        backfilled = ensure_local_material_ids(value)
        targets = self.replica_paths(timeline_id, include_root_mirror=include_root)
        if not targets:
            raise ProjectError(f"No associated replicas found for timeline {timeline_id}")
        modes = {path: self.decode(path).encoding for path in targets}
        backup, manifest = self._snapshot(targets)
        try:
            for path in targets:
                self._atomic_write(path, self._encode_for(value, modes[path]))
            for path in targets:
                if not _semantic_equal(self.decode(path).value, value):
                    raise ProjectError(f"Read-back mismatch: {path}")
        except Exception:
            self._restore_snapshot(backup, manifest)
            raise
        return {
            "backup": str(backup),
            "files_written": [str(path) for path in targets],
            "local_material_ids_backfilled": backfilled,
        }

    def rename_timeline(self, selector: str, name: str) -> dict[str, Any]:
        self._assert_editor_closed()
        if not self.project_index_path or not self.project_index:
            raise ProjectError("This layout has no timeline index to rename")
        entry = self.resolve_timeline(selector)
        paths = [self.project_index_path]
        backup, manifest = self._snapshot(paths)
        old = entry.get("name")
        entry["name"] = name
        entry["update_time"] = int(time.time() * 1_000_000)
        try:
            self._atomic_write(self.project_index_path, json.dumps(self.project_index, ensure_ascii=False,
                                                                   separators=(",", ":")).encode("utf-8"))
            reloaded = _json_file(self.project_index_path)
            if not reloaded:
                raise ProjectError("Timeline index read-back failed")
        except Exception:
            self._restore_snapshot(backup, manifest)
            raise
        return {"ok": True, "timeline_id": entry["id"], "old_name": old, "new_name": name, "backup": str(backup)}

    def clone_timeline(self, selector: str, name: str, activate: bool = False) -> dict[str, Any]:
        self._assert_editor_closed()
        if not self.project_index_path or not self.project_index:
            raise ProjectError("Timeline cloning requires a multi-timeline index")
        source_entry = self.resolve_timeline(selector)
        source_id = str(source_entry["id"])
        source_decoded = self.decode(self.content_path(source_id))
        new_id = str(uuid.uuid4()).upper()
        new_value = _exact_replace(copy.deepcopy(source_decoded.value), source_id, new_id)
        new_value["id"] = new_id
        validation = validate_content(new_value, expected_id=new_id)
        if validation["errors"]:
            raise ProjectError("Clone candidate is invalid: " + "; ".join(validation["errors"]))

        new_dir = self.timelines_dir / new_id
        new_primary = new_dir / "draft_content.json"
        changed = [self.project_index_path]
        if activate and self.layout_path.is_file():
            changed.append(self.layout_path)
        backup, manifest = self._snapshot(changed)
        created: list[Path] = []
        try:
            mode = source_decoded.encoding
            new_dir.mkdir(parents=True, exist_ok=False)
            source_replicas = self.replica_paths(source_id, include_root_mirror=False)
            for source_replica in source_replicas:
                if source_replica.parent != self.timelines_dir / source_id:
                    continue
                name_in_dir = source_replica.name
                source_replica = self.timelines_dir / source_id / name_in_dir
                destination = new_dir / name_in_dir
                self._atomic_write(destination, self._encode_for(new_value, mode))
                created.append(destination)
            if not created:
                self._atomic_write(new_primary, self._encode_for(new_value, mode))
                created.append(new_primary)

            now = int(time.time() * 1_000_000)
            new_entry = copy.deepcopy(source_entry)
            new_entry.update({"id": new_id, "name": name, "create_time": now, "update_time": now,
                              "is_marked_delete": False})
            self.project_index.setdefault("timelines", []).append(new_entry)
            self.project_index["update_time"] = now
            self._atomic_write(self.project_index_path, json.dumps(self.project_index, ensure_ascii=False,
                                                                   separators=(",", ":")).encode("utf-8"))

            if activate and self.layout_path.is_file():
                layout = self.layout_data or {}
                if "activeTimeline" in layout or not any(k in layout for k in ("active_timeline_id", "timeline_id")):
                    layout["activeTimeline"] = new_id
                elif "active_timeline_id" in layout:
                    layout["active_timeline_id"] = new_id
                else:
                    layout["timeline_id"] = new_id
                self._atomic_write(self.layout_path, json.dumps(layout, ensure_ascii=False,
                                                                separators=(",", ":")).encode("utf-8"))
                self.layout_data = layout

            if not _semantic_equal(self.decode(new_primary).value, new_value):
                raise ProjectError("New timeline read-back mismatch")
        except Exception:
            self._restore_snapshot(backup, manifest, created)
            if new_dir.exists():
                shutil.rmtree(new_dir)
            raise
        return {"ok": True, "source_timeline_id": source_id, "timeline_id": new_id, "name": name,
                "activated": activate, "backup": str(backup)}

    def apply_plan(self, selector: str, plan: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        entry = self.resolve_timeline(selector)
        timeline_id = str(entry["id"])
        if plan.get("timeline_id") and plan["timeline_id"] != timeline_id:
            raise ProjectError("Plan timeline_id does not match the selected timeline")
        if plan.get("unresolved") or plan.get("review_required"):
            raise ProjectError("Plan contains unresolved/review-only decisions")
        blocks = validate_keep_blocks(plan.get("keep_blocks"))
        decoded = self.decode(self.content_path(timeline_id))
        value = assemble_keep_blocks(decoded.value, blocks, plan.get("ripple", "all"), plan.get("track_ids") or [])
        validation = validate_content(value, expected_id=timeline_id)
        if validation["errors"]:
            raise ProjectError("Plan result is invalid: " + "; ".join(validation["errors"]))
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "timeline_id": timeline_id,
                "duration_us": value.get("duration", 0),
                "validation": validation,
                "would_change": not _semantic_equal(decoded.value, value),
                "would_write": [str(path) for path in self.replica_paths(timeline_id)],
            }
        self._assert_editor_closed()
        write = self._write_content(timeline_id, value)
        final = self.validate(timeline_id)
        if not final["ok"]:
            raise ProjectError("Post-write validation failed: " + "; ".join(final["errors"]))
        return {"ok": True, "timeline_id": timeline_id, "duration_us": value.get("duration", 0),
                "validation": final, **write}


def _material_ids(materials: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(materials, dict):
        for value in materials.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and item.get("id"):
                        result.add(str(item["id"]))
    return result


_LOCAL_ID_MATERIAL_BUCKETS = ("videos", "audios")


def ensure_local_material_ids(value: dict[str, Any]) -> int:
    """Backfill missing/empty ``local_material_id`` from the staged file name stem.

    Jianying Pro 5.9+ reports a "media missing" error when a Video/Audio material
    carries an empty ``local_material_id``. This mirrors upstream v1.7.0: derive a
    stable, non-empty id from the file name stem so the project stays self
    contained. Only absent or blank fields are filled; any existing value is
    preserved. Returns the number of fields changed.

    Caveat (inherited from upstream): the stem of two same-named files in
    different directories collides on one ``local_material_id``. Staging media
    into the draft (md5-prefixed names) or renaming avoids this.
    """
    materials = value.get("materials")
    if not isinstance(materials, dict):
        return 0
    changed = 0
    for bucket in _LOCAL_ID_MATERIAL_BUCKETS:
        items = materials.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("local_material_id") or "").strip():
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path:
                continue
            stem = os.path.splitext(os.path.basename(path.replace("\\", "/")))[0]
            if stem:
                item["local_material_id"] = stem
                changed += 1
    return changed


def validate_content(value: dict[str, Any], expected_id: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if expected_id and str(value.get("id")) != expected_id:
        errors.append(f"Content id {value.get('id')!r} does not match timeline id {expected_id!r}")
    tracks = value.get("tracks")
    if not isinstance(tracks, list):
        errors.append("tracks is not a list")
        tracks = []
    materials = _material_ids(value.get("materials", {}))
    maximum = 0
    for track_index, track in enumerate(tracks):
        if not isinstance(track, dict):
            errors.append(f"track[{track_index}] is not an object")
            continue
        segments = track.get("segments", [])
        if not isinstance(segments, list):
            errors.append(f"track[{track_index}].segments is not a list")
            continue
        intervals = []
        for segment_index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                errors.append(f"track[{track_index}].segment[{segment_index}] is not an object")
                continue
            target = segment.get("target_timerange")
            if not isinstance(target, dict):
                errors.append(f"segment {segment.get('id')} has no target_timerange")
                continue
            start, duration = _start(target), _duration(target)
            if start < 0 or duration <= 0:
                errors.append(f"segment {segment.get('id')} has invalid target range {start}+{duration}")
            end = start + duration
            maximum = max(maximum, end)
            intervals.append((start, end, segment.get("id")))
            material_id = segment.get("material_id")
            if material_id and str(material_id) not in materials:
                errors.append(f"segment {segment.get('id')} references missing material {material_id}")
            for ref in segment.get("extra_material_refs", []) or []:
                if ref and str(ref) not in materials:
                    errors.append(f"segment {segment.get('id')} references missing extra material {ref}")
        intervals.sort()
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] < previous[1] and not track.get("allow_overlap", False):
                errors.append(f"track {track.get('id')} overlaps: {previous[2]} and {current[2]}")
    declared = int(value.get("duration", 0) or 0)
    if maximum > declared:
        errors.append(f"segment end {maximum} exceeds declared duration {declared}")
    elif declared and maximum != declared:
        warnings.append(f"declared duration {declared} differs from maximum segment end {maximum}")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "maximum_end_us": maximum}


def validate_keep_blocks(raw: Any) -> list[tuple[int, int]]:
    if not isinstance(raw, list) or not raw:
        raise ProjectError("keep_blocks must be a non-empty list")
    blocks: list[tuple[int, int]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ProjectError(f"keep_blocks[{index}] is not an object")
        start, end = int(item.get("start_us", -1)), int(item.get("end_us", -1))
        if start < 0 or end <= start:
            raise ProjectError(f"keep_blocks[{index}] has an invalid range")
        blocks.append((start, end))
    chronological = sorted(blocks)
    for previous, current in zip(chronological, chronological[1:]):
        if current[0] < previous[1]:
            raise ProjectError("keep_blocks overlap on the input timeline")
    return blocks


def _slice_timerange(timerange: dict[str, Any], segment_target: dict[str, Any], keep_start: int,
                     keep_end: int) -> dict[str, Any]:
    result = copy.deepcopy(timerange)
    target_duration = _duration(segment_target)
    if target_duration <= 0:
        raise ProjectError("Cannot map a zero-duration segment")
    ratio = _duration(timerange) / target_duration
    offset = keep_start - _start(segment_target)
    result["start"] = _start(timerange) + round(offset * ratio)
    result["duration"] = max(1, round((keep_end - keep_start) * ratio))
    return result


def assemble_keep_blocks(value: dict[str, Any], blocks: list[tuple[int, int]], ripple: str,
                         track_ids: list[str]) -> dict[str, Any]:
    if ripple not in ("all", "tracks"):
        raise ProjectError("ripple must be 'all' or 'tracks'")
    selected = {str(tid) for tid in track_ids}
    if ripple == "tracks" and not selected:
        raise ProjectError("track_ids are required when ripple='tracks'")
    result = copy.deepcopy(value)
    output_offsets = []
    cursor = 0
    for start, end in blocks:
        output_offsets.append(cursor)
        cursor += end - start

    for track in result.get("tracks", []):
        if ripple == "tracks" and str(track.get("id")) not in selected:
            continue
        source_segments = [segment for segment in track.get("segments", []) if isinstance(segment, dict)]
        assembled = []
        used_ids: set[str] = set()
        for (block_start, block_end), output_start in zip(blocks, output_offsets):
            for segment in source_segments:
                target = segment.get("target_timerange") or {}
                segment_start, segment_end = _start(target), _end(target)
                keep_start, keep_end = max(segment_start, block_start), min(segment_end, block_end)
                if keep_end <= keep_start:
                    continue
                piece = copy.deepcopy(segment)
                piece_target = copy.deepcopy(target)
                new_start = output_start + keep_start - block_start
                if new_start == 0 and "start" not in target:
                    piece_target.pop("start", None)
                else:
                    piece_target["start"] = new_start
                piece_target["duration"] = keep_end - keep_start
                piece["target_timerange"] = piece_target
                for key in ("source_timerange", "render_timerange"):
                    if isinstance(segment.get(key), dict) and _duration(segment[key]) > 0:
                        piece[key] = _slice_timerange(segment[key], target, keep_start, keep_end)
                original_id = str(piece.get("id") or "")
                exact = keep_start == segment_start and keep_end == segment_end and original_id not in used_ids
                if not exact or not original_id:
                    piece["id"] = str(uuid.uuid4()).upper()
                used_ids.add(str(piece.get("id")))
                assembled.append(piece)
        assembled.sort(key=lambda segment: _start(segment.get("target_timerange")))
        track["segments"] = assembled

    maximum = 0
    for track in result.get("tracks", []):
        for segment in track.get("segments", []):
            maximum = max(maximum, _end(segment.get("target_timerange")))
    result["duration"] = maximum
    return result


def _print(value: Any) -> None:
    # GBK/cp1252 piped consoles crash on Chinese/emoji output; this CLI is
    # normally invoked as a subprocess by an agent.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", help="Exact videoeditor.dll path for encrypted projects")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("probe", "inspect", "validate"):
        command = sub.add_parser(name)
        command.add_argument("draft")
        if name != "probe":
            command.add_argument("--timeline", default="active")
        if name == "inspect":
            command.add_argument("--no-segments", action="store_true")
    clone = sub.add_parser("clone-timeline")
    clone.add_argument("draft"); clone.add_argument("--source", default="active")
    clone.add_argument("--name", required=True); clone.add_argument("--activate", action="store_true")
    rename = sub.add_parser("rename-timeline")
    rename.add_argument("draft"); rename.add_argument("--timeline", required=True); rename.add_argument("--name", required=True)
    locate = sub.add_parser("locate")
    locate.add_argument("draft"); locate.add_argument("--timeline", default="active")
    locate.add_argument("--segment-id")
    locate.add_argument("--track-id")
    locate.add_argument("--track-type")
    locate.add_argument("--start-us", type=int)
    locate.add_argument("--text")
    locate.add_argument("--tolerance-us", type=int, default=DEFAULT_LOCATE_TOLERANCE_US)
    apply = sub.add_parser("apply-plan")
    apply.add_argument("draft"); apply.add_argument("--timeline", required=True); apply.add_argument("--plan", required=True)
    apply.add_argument("--apply", action="store_true", help="write changes; without this flag only dry-runs")
    stage = sub.add_parser("stage-media", help="copy external media into the draft (optional normalize)")
    stage.add_argument("draft")
    stage.add_argument("--media", required=True, help="external media file to stage into the draft")
    stage.add_argument("--subdir", default="materials")
    stage.add_argument("--no-normalize", action="store_true", help="skip video re-encode before staging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "stage-media":
        from media_stage import MediaStageError, prepare_media_for_draft

        try:
            report = prepare_media_for_draft(
                args.draft,
                args.media,
                normalize=not args.no_normalize,
                subdir=args.subdir,
            )
            result = {"ok": True, **report}
        except (MediaStageError, FileNotFoundError, OSError) as exc:
            result = {"ok": False, "error": str(exc)}
        _print(result)
        return 0 if result.get("ok") else 1

    project = JianyingProject(args.draft, args.dll)
    if args.command == "probe":
        result = project.probe()
    elif args.command == "inspect":
        result = project.inspect(args.timeline, include_segments=not args.no_segments)
    elif args.command == "validate":
        result = project.validate(args.timeline)
    elif args.command == "clone-timeline":
        result = project.clone_timeline(args.source, args.name, args.activate)
    elif args.command == "rename-timeline":
        result = project.rename_timeline(args.timeline, args.name)
    elif args.command == "locate":
        result = project.locate(
            args.timeline,
            segment_id=args.segment_id,
            track_id=args.track_id,
            track_type=args.track_type,
            start_us=args.start_us,
            text=args.text,
            tolerance_us=args.tolerance_us,
        )
    else:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8-sig"))
        result = project.apply_plan(args.timeline, plan, dry_run=not args.apply)
    _print(result)
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
