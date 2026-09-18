# Architecture and version detection

Treat Jianying project support as capability detection, not a version-number table.

## Probe order

1. Resolve the supplied path and confirm it is a directory.
2. Inventory known anchors without assuming they all exist: root content and metadata files, timeline indexes, layout files, per-timeline content, and template-style content files.
3. For each content candidate, try UTF-8 JSON parsing after BOM and whitespace removal.
4. If parsing fails, mark it `encrypted-or-unknown`; on Windows, test the supported Jianying DLL backend. A decryption failure remains `unknown`.
5. Classify the observed layout as `legacy-single`, `multi-timeline`, `hybrid`, or `unknown`.

App release numbers are evidence, not the adapter selector. Old projects may retain old layouts after the app is upgraded.

## Active timeline resolution

Collect candidates and their evidence from `timeline_layout.json`, the timeline index main/default reference, a root content ID matching an indexed timeline, and the sole non-deleted timeline.

When candidates disagree, report the conflict. Do not silently choose the newest directory or final index entry. Mutation requires an explicit timeline ID/name unless one active candidate is unambiguous.

## Replica association

Associate a file with a timeline only when it lives under that timeline's indexed directory, its decoded content ID equals the timeline ID, or the active-mirror rule is supported by matching active references and content IDs.

Do not assume a fixed number of replicas. Write only associated files that already exist, except the primary file of a newly cloned timeline.

## Encryption backend

Encrypted support is detected by a successful call to Jianying's installed `videoeditor.dll` exports and a verified encrypt/decrypt round trip. The backend is Windows-only. Plaintext projects remain readable and writable on other platforms.

If exported symbols change, stop after read-only probing. Do not guess a cipher, key, or container format.

