# Changelog

## Unreleased (PR #1 review fixes)
- **Windows GBK consoles**: `utils.formatters` (imported by nearly every product
  script) and the ops CLIs now reconfigure stdout/stderr to UTF-8 with
  `errors="replace"`, so emoji/Chinese prints never raise `UnicodeEncodeError`
  when invoked as a piped subprocess without `PYTHONUTF8=1`.
- **Single staging implementation**: `MediaOpsMixin._stage_local_asset` delegates
  to `media_stage.stage_local_asset` (`md5(path|size|mtime)` naming, atomic
  replace). Removes the stale-copy hazard of the old size-only check and the
  duplicate differently-named staged copies the two implementations produced.
- `find_jianying_dll`: an explicit `JIANYING_VIDEOEDITOR_DLL` now short-circuits
  the newest-version scan (and errors loudly if the pinned file is missing).
- `content_path`: empty content ids only match the sanctioned `legacy-root`
  alias in index-less layouts; no fail-open matching in hybrid drafts.
- `_probe_video`: ffprobe missing/hanging no longer crashes media import
  (30s timeout, probe failure means "skip normalization").
- Documented known trade-offs: `local_material_id` stem collisions, `MsvcString`
  per-call leak in the crypto backend.

## v1.7.0+crypto-ops.1
Merge of the fork's decryption / project-operations layer onto the upstream
`luoluoluo22` v1.7.0 base (product generation kept intact).
- **Decryption backend** `scripts/jy_draft_crypto.py`: ctypes calls into the
  installed Jianying `videoeditor.dll` (`encrypt`/`decrypt`/`enable`) with a
  mandatory decrypt round-trip before any write. Windows only.
- **Operations CLI** `scripts/jianying_project.py`: `probe`/`inspect`/`locate`/
  `validate`/`clone-timeline`/`rename-timeline`/`apply-plan`/`stage-media` over
  hybrid `Timelines/` layouts and observed `ReplicaManifest`.
- **Pro 5.9+ `local_material_id` backfill in the ops path**: `ensure_local_material_ids`
  runs at the `_write_content` funnel so every write (apply-plan / clone) emits a
  stable non-empty `local_material_id` from the staged file-name stem for video and
  audio materials, matching the v1.7.0 product-layer fix. Materials with no `path`
  are left untouched. `prepare_media_for_draft` now reports a suggested
  `local_material_id`.
- `references/*.md` (8) and `tests/test_jianying_project.py` (19 tests) ported.

## v1.7.0 - 2026-09-11
- **Draft Self-containment & Media Missing Fix** (Contributed by @shaozheliu, #23):
  - Fixed JianYing Pro 5.9+ "media missing" error caused by empty `local_material_id` and external transient file cleanup.
  - Generates stable, non-empty `local_material_id` based on filename stem for `VideoMaterial` and `AudioMaterial`.
  - Automatically stages imported assets into the draft's internal directory to ensure self-contained project bundles.
  - Removed dummy cloud music fallbacks (`cloud_music_xxx.mp3`); aborts cleanly on download failure to prevent corrupted drafts.
- **macOS Compatibility & Resilient Media Probing** (Contributed by @twodogegg, #20):
  - Added primary detection for modern macOS JianYing draft root and `.agents` skill installations.
  - Added `ffprobe` fallback probing when `pymediainfo` or `libmediainfo` is unavailable.
  - Added video geometry and codec normalization for odd dimensions or incompatible streams.
  - Added safe platform detection for auto exporter with clear unsupported notices on non-Windows environments.
  - Expanded unit test coverage with 19 test cases.

## v1.6.0 - 2026-04-19
- **Core Enhancements**:
  - **Intelligent TTS (Narrated Subtitles)**: Unified `add_narrated_subtitles` API for one-click script-to-video workflow.
  - **Auto-healing System**: Modernized draft generator to support `draft_info.json` (v5.9+) and automatic repair of corrupted projects.
- **MacOS Compatibility**:
  - Full path resolution for Apple Silicon and Intel Macs.
  - Integrated `avfoundation` for high-performance screen recording on macOS.
- **Ecosystem Tools**:
  - `build_cloud_music_library.py`: Automated scanning of local drafts to index used cloud assets.
  - `web_recorder.py`: Pro-grade recording engine for web-based VFX assets.
- **Bug Fixes & API Polish**:
  - Fixed `pyJianYingDraft` export issues for `Transition`, `Filter`, and `Mask`.
  - Refactored `VfxOpsMixin` to use correct segment-level API calls.
  - Improved error handling for cloud music fallbacks.

## v1.5.0 - 2026-03-04
- Security hardening:
  - sanitized draft project names and blocked path traversal/out-of-root delete.
  - restored TLS verification for SAMI TTS by default.
  - added cloud download URL/header/size guards.
- API/CLI standardization:
  - unified machine-readable `--json` output for key scripts.
  - added strict mode for validator (`--strict`).
  - centralized runtime config (`scripts/utils/config.py`).
- Quality engineering:
  - expanded unit tests for security guards.
  - added repo hygiene and data schema checks.
  - added CI lint/format/test/schema pipeline.
- Repo organization:
  - removed tracked runtime artifacts and cache binaries.
  - added compatibility wrappers and common logger utility.
