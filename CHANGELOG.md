# Changelog

## Current skill version

See `VERSION` (currently **3.1.0**).

## v3.1 — media staging helper

Ported the useful subset of upstream `luoluoluo22/jianying-editor-skill` ~1.7.0
media helpers without restoring the product shell:

- `scripts/media_stage.py` — copy external media into `<draft>/materials/` and
  optional H.264/yuv420p normalize via ffmpeg/ffprobe.
- CLI: `stage-media` on `scripts/jianying_project.py`.

Still out of scope: JyWrapper, TTS, auto-export, cloud libraries, recording.

## v3 — project-operations skill

This repository is a **project-operations skill** for existing Jianying drafts:
inspect / validate / clone / apply approved plans / rollback.

Older product features described in historical tags (TTS, screen recording,
asset cloud libraries, universal generators) are **out of scope** and are not
present in the skill runtime (`scripts/jianying_project.py` + `jy_draft_crypto.py`).

## Historical

Product-era changelogs (≤ v1.6) described a different codebase. They are not
reliable for the current skill surface. Consult git history if needed.
