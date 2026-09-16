---
name: jianying-editor
description: Use when inspecting, decrypting, validating, cloning, applying an approved plan to, or rolling back an existing Jianying Pro / 剪映 draft (草稿), including multi-timeline layouts and encrypted drafts. Triggers: draft_content.json, apply-plan, clone timeline, rollback, encrypted draft, 多时间线, 安全写回, 字幕对齐计划应用, draft_info. Do NOT use to decide spoken-content cuts, create drafts from scratch, TTS, screen recording, asset search, or packaging decisions (花字/卡点); use jianying-rough-cut and jianying-packaging for those.
---

# Jianying Project Operations

This skill is the project-operation layer. It turns an explicit edit decision into a safe Jianying project change. It does not judge topic value, filler words, pauses, speaker roles, Q&A structure, or narrative quality.

In the three-skill workflow, `jianying-rough-cut` owns content and subtitle alignment decisions, `jianying-packaging` owns visual/audio packaging decisions, and this skill owns draft access, execution, validation, and rollback. Read-only probes may happen at any stage; writes require an approved upstream plan.

## Required workflow

1. Work from an explicit draft path whenever one is available. Never assume a fixed drive, user directory, Jianying version, or draft layout.
2. Run `scripts/jianying_project.py probe <draft-path>` before reading or changing content.
3. Read [references/architecture-and-versioning.md](references/architecture-and-versioning.md) when the layout, encryption mode, active timeline, or replica relationship is uncertain.
4. Run `inspect`, `locate`, and `validate` before any mutation. Treat unknown schema features and unresolved material references as blockers to destructive edits.
5. Keep the source timeline. Prefer cloning to a named timeline before applying cuts, subtitle alignment, or packaging unless the user explicitly requests an in-place edit.
6. For mutations, follow [references/safe-mutation.md](references/safe-mutation.md). Do not edit while Jianying or its tray process may still own the project.
7. Apply only the upstream decision. Do not infer content deletions, subtitle corrections, emphasis, template choice, or sound choice.
8. Validate the in-memory result, write atomically to the observed associated replicas, decrypt/read back, and validate again.
9. Report the affected timeline ID/name, replica manifest, backup location, files written, validation result, and rollback path.

## Canonical implementation

Use `scripts/jianying_project.py` for existing-project inspection and mutation. `scripts/draft_inspector.py` is a compatibility CLI that delegates to it. `scripts/jy_draft_crypto.py` is the only encryption backend.

Do not use older project-generation wrappers to modify an existing encrypted multi-timeline draft. They may remain for legacy draft creation, but they are not an alternate write path for this workflow.

### Read-only commands

```powershell
python scripts/jianying_project.py probe "<draft-path>"
python scripts/jianying_project.py inspect "<draft-path>" --timeline active
python scripts/jianying_project.py locate "<draft-path>" --timeline active --track-type text --start-us 767000 --tolerance-us 40000
python scripts/jianying_project.py validate "<draft-path>" --timeline active
```

### Safe timeline operations

```powershell
python scripts/jianying_project.py clone-timeline "<draft-path>" --source active --name "rough-cut-copy" --activate
python scripts/jianying_project.py rename-timeline "<draft-path>" --timeline "<id-or-name>" --name "new-name"
python scripts/jianying_project.py apply-plan "<draft-path>" --timeline "<id-or-name>" --plan "decision-plan.json"
python scripts/jianying_project.py apply-plan "<draft-path>" --timeline "<id-or-name>" --plan "decision-plan.json" --apply
```

`apply-plan` is dry-run by default; `--apply` is required to write. It accepts ordered keep blocks on the current target time axis. Deletion is represented by omitted ranges; reordering is represented by block order. It can ripple all tracks or an explicit track set. Read [references/operation-contract.md](references/operation-contract.md) before generating a plan.

`locate` uses a default ±40ms tolerance so frame-quantized starts such as `766667µs` can be found from a rounded plan time. Exact segment, track, text, and time assertions should be combined whenever possible. Programmatic adapters should use `JianyingProject.resolve_locator()` and fail closed unless exactly one match remains.

For subtitle alignment and packaging, the caller supplies a reviewed semantic plan. This skill resolves that plan against the saved draft and performs the transaction; it does not decide the corrected words, emphasis scope, template, motion, or sound family. Read [references/segment-location-and-timebase.md](references/segment-location-and-timebase.md) and [references/replica-manifest-and-transactions.md](references/replica-manifest-and-transactions.md).

## Non-negotiable invariants

- Detect plaintext versus encrypted data from file contents; never infer encryption from an app version number alone.
- Detect the project layout from observed files and references; do not assume every version uses `draft_info.json`, root-only content, or `Timelines/`.
- Missing `start` means zero only where Jianying's timerange convention permits it.
- Preserve unknown fields. Modify the smallest known structure.
- Do not change a content/timeline ID during an ordinary save.
- Generate a new ID only for a new timeline or project object, and replace exact ID values rather than arbitrary string substrings.
- Do not rename, delete, or disable Jianying recovery directories as a normal write step.
- Discover a `ReplicaManifest` from observed files and decoded IDs. Never assume that a project has exactly three or five replicas, and never broadcast one timeline's content into every backup or timeline directory.
- Use same-directory temporary files and atomic replacement. Never partially update a replica set without a rollback snapshot.
- A successful write requires semantic validation and decoded read-back of every written replica. File bytes may differ because of encoding or normalization; decoded semantic content must agree.
- `enable=false` is not a reliable hide operation. Preserve the source timeline and use a reviewed staging/clone policy when covered subtitles must be removed or covered.
- Quantize or resolve time against the current saved timeline and use ±40ms tolerance; do not require rounded decimal timestamps to match exactly.

## Validation scope

Validation must cover, where present:

- parse/decrypt success and stable round-trip;
- timeline IDs, names, active/main references, and directory relationships;
- track and segment shape;
- non-negative timeranges, positive durations, and timeline bounds;
- overlap policy per track;
- material and extra-material references;
- project duration versus segment ends;
- agreement among confirmed replicas.

For the normalized inspection model, read [references/normalized-model.md](references/normalized-model.md).

## Boundary with content editing

An upstream content-analysis skill may return `keep`, `delete`, `shorten`, `reorder`, or `review` decisions with source/target ranges. This skill checks whether those ranges can be represented safely and executes only approved operations. If a decision is ambiguous, low-confidence, or marked for review, do not apply it.
