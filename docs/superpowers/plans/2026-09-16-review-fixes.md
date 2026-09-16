# jianying-editor Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix P0–P2 review findings **without deleting any files** — restore discoverability (description/SDO + Chinese triggers), document the folder-vs-name mismatch, reconcile version narrative, neutralize packaging-boundary conflicts in leftover references, and point SKILL.md only at the canonical runtime.

**Architecture:** Frontmatter rewrite on `SKILL.md`; body edits for canonical implementation and name/folder note; rewrite leftover `references/huazi-combination-import.md` and `references/audio-track-and-sfx.md` as boundary pointers (keep files); slim `CHANGELOG.md` header to a v3 project-ops narrative pointer; optionally add a deprecation docstring on compatibility shells. **Mass deletion of assets/data/index.html/pycache is explicitly deferred.**

**Tech Stack:** Markdown, Python 3 (stdlib only for the skill runtime)

**Spec:** `C:\Users\cbsjz\Desktop\skills\jianying-editor-skill\REVIEW.md` (sections 1.2–1.4, 2.2, 3, 5)

## Global Constraints

- **No deletions in this plan.** `assets/`, `data/`, `index.html`, `docs/images/donate/`, `__pycache__`, `agents/openai.yaml`, `.github/`, `.pre-commit-config.yaml` all stay on disk.
- Do not modify `scripts/jianying_project.py` or `scripts/jy_draft_crypto.py` behavior.
- Existing 9 tests in `tests/test_jianying_project.py` must stay green.
- Description <1024 chars, starts with trigger conditions, includes Chinese literals, keeps/extends negative triggers.
- Folder remains `jianying-editor-skill`; frontmatter `name` remains `jianying-editor` this phase — document the mismatch, do not rename the repo directory.

## File Map

| File | Change |
|------|--------|
| `SKILL.md` | Rewrite description; canonical implementation note; folder/name note |
| `references/huazi-combination-import.md` | Rewrite as boundary pointer (keep file) |
| `references/audio-track-and-sfx.md` | Rewrite as boundary pointer (keep file) |
| `CHANGELOG.md` | Replace stale product changelog body with pointer + keep filename |
| `VERSION` | Keep 3.0.0; ensure CHANGELOG mentions it |
| `scripts/jy_wrapper.py` | Optional deprecation docstring only |
| `scripts/draft_inspector.py` | Optional deprecation docstring only |

---

### Task 1: Rewrite editor description (SDO)

**Files:**
- Modify: `SKILL.md:1-4` (frontmatter)

**Interfaces:**
- Produces: new `description` for skill discovery

- [ ] **Step 1: Replace description**

```yaml
description: Use when inspecting, decrypting, validating, cloning, applying an approved plan to, or rolling back an existing Jianying Pro / 剪映 draft (草稿), including multi-timeline layouts and encrypted drafts. Triggers: draft_content.json, apply-plan, clone timeline, rollback, encrypted draft, 多时间线, 安全写回, 字幕对齐计划应用, draft_info. Do NOT use to decide spoken-content cuts, create drafts from scratch, TTS, screen recording, asset search, or packaging decisions (花字/卡点); use jianying-rough-cut and jianying-packaging for those.
```

- [ ] **Step 2: Verify**

```powershell
$line = (Select-String -Path SKILL.md -Pattern '^description:').Line
$line.Length  # <= 1024
$line -match 'Use when' -and $line -match '草稿' -and $line -match 'Do NOT'
```

Expected: length OK; three matches True.

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "fix(editor): rewrite description for SDO and Chinese triggers"
```

---

### Task 2: Document folder/name mismatch + co-skill boundary

**Files:**
- Modify: `SKILL.md` (intro / Boundaries area)

**Interfaces:**
- Produces: explicit install/rename note; packaging ownership reminder

- [ ] **Step 1: Add naming note after the title intro**

Insert after the first intro paragraph:

```markdown
> **Install note:** this repository folder is `jianying-editor-skill`, but the skill `name` is `jianying-editor`. Installers that key on folder name should either rename the folder to `jianying-editor` after clone or keep the folder and rely on frontmatter `name` (MiMo/skill loaders use frontmatter). Do not change `name` to match the folder without coordinating sibling skills that link to `jianying-editor`.
```

- [ ] **Step 2: Strengthen packaging boundary**

In the three-skill workflow paragraph, ensure this sentence is present (add if missing):

```markdown
Visual/audio packaging (花字、上轨强调、音效、卡点) is owned by `jianying-packaging`; this skill only executes approved project mutations.
```

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "docs(editor): document folder/name mismatch and packaging boundary"
```

---

### Task 3: Neutralize leftover packaging references (keep files)

**Files:**
- Modify: `references/huazi-combination-import.md`
- Modify: `references/audio-track-and-sfx.md`

**Interfaces:**
- Consumes: REVIEW finding that these are unlinked and conflict with packaging ownership
- Produces: short boundary documents that redirect, not full packaging guides

- [ ] **Step 1: Rewrite both files**

`references/huazi-combination-import.md`:

```markdown
# Huazi combination import (legacy pointer)

This skill does **not** own flower-text (花字) combination design or packaging decisions.

- Content/structure decisions: `jianying-rough-cut`
- Visual packaging including 花字: `jianying-packaging`
- Project apply/validate/rollback of an already-approved plan: this skill (`jianying-editor`)

If an old workflow expected this file to teach packaging, treat that as obsolete. This file remains only so inbound links do not 404.
```

`references/audio-track-and-sfx.md`:

```markdown
# Audio track and SFX (legacy pointer)

Sound selection, SFX families, and packaging audio design are owned by `jianying-packaging`.

This skill (`jianying-editor`) may apply an approved plan that includes audio segments, but it does **not** choose sounds. Do not execute packaging decisions from this document.

File retained for inbound-link stability.
```

- [ ] **Step 2: Confirm SKILL.md does not newly link them as authorities**

```powershell
Select-String -Path SKILL.md -Pattern 'huazi|audio-track-and-sfx'
```

Expected: no new authority links (zero matches is fine). If SKILL.md previously linked them, remove those links in this same commit.

- [ ] **Step 3: Commit**

```bash
git add references/huazi-combination-import.md references/audio-track-and-sfx.md SKILL.md
git commit -m "docs(editor): convert leftover packaging refs to boundary pointers"
```

---

### Task 4: Version narrative single source (no delete)

**Files:**
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `VERSION` file (`3.0.0`)
- Produces: CHANGELOG that does not claim deleted product features as current

- [ ] **Step 1: Rewrite CHANGELOG header**

Keep the filename. Replace body with:

```markdown
# Changelog

## Current skill version

See `VERSION` (currently **3.0.0**).

## v3 — project-operations skill

This repository is a **project-operations skill** for existing Jianying drafts:
inspect / validate / clone / apply approved plans / rollback.

Older product features described in historical tags (TTS, screen recording,
asset cloud libraries, universal generators) are **out of scope** and are not
present in the skill runtime (`scripts/jianying_project.py` + `jy_draft_crypto.py`).

## Historical

Product-era changelogs (≤ v1.6) described a different codebase. They are not
reliable for the current skill surface. Consult git history if needed.
```

- [ ] **Step 2: Align VERSION**

```powershell
Get-Content VERSION
Select-String -Path CHANGELOG.md -Pattern '3\.0\.0'
```

Expected: VERSION is `3.0.0`; CHANGELOG mentions 3.0.0.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(editor): rewrite changelog as v3 project-ops narrative"
```

---

### Task 5: Deprecation markers on compatibility shells (no delete)

**Files:**
- Modify: `scripts/jy_wrapper.py`
- Modify: `scripts/draft_inspector.py`

**Interfaces:**
- Produces: explicit deprecation without breaking imports/CLI

- [ ] **Step 1: Annotate jy_wrapper.py**

Prepend after the existing module docstring (or replace docstring) with:

```python
"""Compatibility imports for existing-project operations.

DEPRECATED: prefer `from jianying_project import ...` directly.
Retained for inbound imports; not an alternate write path.
"""
```

Keep all re-exports unchanged.

- [ ] **Step 2: Annotate draft_inspector.py**

```python
"""Compatibility entry point for the canonical Jianying project runtime.

DEPRECATED: prefer `python scripts/jianying_project.py <command> ...`.
Retained so old docs/commands keep working.
"""
```

Keep `if __name__ == "__main__": raise SystemExit(main())` unchanged.

- [ ] **Step 3: Smoke that CLI still works**

```powershell
Set-Location C:\Users\cbsjz\Desktop\skills\jianying-editor-skill
& $env:MIMO_PYTHON scripts\draft_inspector.py
```

Expected: usage/error exit from `main()` — not ImportError. (No draft path required for this smoke.)

- [ ] **Step 4: Run editor tests**

```powershell
& $env:MIMO_PYTHON -m unittest discover -s tests -v
```

Expected: 9 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/jy_wrapper.py scripts/draft_inspector.py
git commit -m "docs(editor): mark compatibility shells deprecated, keep behavior"
```

---

### Task 6: CI/pre-commit honesty (docs-only, no delete)

**Files:**
- Modify: `.pre-commit-config.yaml` (if present and points at missing files)
- Modify: `.github/workflows/ci.yml` (comment only — do not remove the file)

**Interfaces:**
- Produces: comments/notes that current CI targets are stale; do not rewrite CI logic this phase unless trivial

- [ ] **Step 1: Inspect targets**

```powershell
Select-String -Path .pre-commit-config.yaml,.github/workflows\ci.yml -Pattern 'test_wrapper|api_validator|tools/' -ErrorAction SilentlyContinue
```

- [ ] **Step 2: Add a banner comment**

At the top of each file that references missing paths, add:

```yaml
# STALE: this config still names scripts/tests that were removed during
# skill-ification. Runtime under test is scripts/jianying_project.py +
# scripts/jy_draft_crypto.py + tests/test_jianying_project.py.
# Deletion/rewrite of this CI config is deferred (review plan Deferred section).
```

(YAML comments only — do not change hooks/jobs this phase.)

- [ ] **Step 3: Commit**

```bash
git add .pre-commit-config.yaml .github/workflows/ci.yml
git commit -m "docs(editor): mark stale CI/pre-commit targets, defer rewrite"
```

---

## Deferred (NOT in this plan — user said 先不删除)

Execute only after explicit user approval in a later plan:

1. Delete `__pycache__/**` (incl. orphan pyc under core/utils/vendor) — ~1.43 MB
2. Delete `assets/**` — ~5.04 MB
3. Delete `data/*.csv` — ~0.27 MB
4. Delete `index.html`
5. Delete `docs/images/donate/**`
6. Delete or fully rewrite `.github/workflows/ci.yml` + `.pre-commit-config.yaml` to only lint/test live files
7. Delete `agents/openai.yaml`
8. Delete `scripts/jy_wrapper.py` / `scripts/draft_inspector.py` after SKILL.md no longer mentions them
9. Delete empty `scripts/core/`, `scripts/utils/`, `scripts/vendor/` shells
10. Rename folder `jianying-editor-skill` → `jianying-editor` (coordinate with packaging/rough-cut links)

## Done criteria

- [ ] Description has Use when + 草稿/剪映 triggers + full negatives
- [ ] Folder/name mismatch documented
- [ ] Leftover packaging refs are pointers, not competing authorities
- [ ] CHANGELOG matches VERSION 3.0.0 project-ops story
- [ ] Compatibility shells marked deprecated but still work
- [ ] Stale CI/pre-commit clearly marked
- [ ] 9 editor tests still pass
- [ ] Zero files deleted
