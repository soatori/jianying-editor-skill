# Safe mutation and rollback

## Preconditions

- Confirm the exact draft and timeline.
- Close Jianying and its tray/background process before writing.
- Probe, inspect, and validate the current project.
- Reject mutation when the target is ambiguous, decryption is unverified, or structural errors already exist unless repair was explicitly requested.

## Transaction

1. Build a `ReplicaManifest` of positively associated files that will change; do not assume a fixed replica count.
2. Copy them into `.jianying-editor-backups/<transaction-id>/` with hashes.
3. Mutate an in-memory copy while preserving unknown keys.
4. Validate before serialization.
5. Serialize once; for encrypted content, verify encrypt/decrypt round trip.
6. Write same-directory temporary files, flush, and replace atomically.
7. Read/decrypt every target and compare decoded semantic content with the candidate. Byte equality is not required when Jianying normalizes representation.
8. Re-run project and replica-consistency validation.

If any step fails, restore all files in the manifest. Never leave a mixed old/new replica set.

## IDs and recovery data

Ordinary edits keep project and timeline IDs. Timeline cloning creates one new ID and updates only exact values in known references. Do not globally replace serialized text.

Do not delete or rename Jianying's recovery directories by default. If an observed recovery mechanism repeatedly overwrites a verified edit, stop and document it before proposing a targeted workaround.

`enable=false` is version-sensitive and is not a reliable hide guarantee. Use a preserved source plus reviewed clone/staging policy for covered subtitles.

## Track synchronization

Use `all` ripple mode when picture, production audio, captions, and overlays must stay aligned. Use explicit track IDs only when the upstream plan intentionally isolates tracks.

Split at target-time boundaries; map kept fractions into source/render timeranges when proportional mapping is valid; create IDs for extra pieces; preserve all other fields; ripple target starts; and recalculate duration.

Transitions, compound clips, speed curves, freeze frames, nested timelines, and time-remapped media may require specialized adapters. Reject an unsafe automatic cut rather than approximating it.
