# Replica manifests and transactions

## Replica discovery

The editor must derive the writable set from the current draft, not from a fixed rule such as “three files” or “five files”. A replica is associated with a timeline only when its decoded content ID matches the selected timeline ID.

`jianying_project.py replica_manifest()` reports:

- path and path relative to the draft;
- role (`primary`, `writable-backup`, `writable-template`, or observed content);
- plaintext/encrypted encoding;
- decoded content ID;
- association and writable status;
- SHA-256 of the bytes at probe time.

An unreadable or ID-mismatched content candidate is a safety error. Do not silently omit it and continue writing.

## Transaction sequence

Every write follows:

```text
probe → inspect/locate → assertions → dry-run → snapshot
→ in-memory validation → same-directory atomic writes
→ decoded read-back of every associated replica → validation
```

The snapshot contains every file that will change and a manifest of original hashes. On any failure, restore the complete snapshot before reporting failure.

The root-level `draft_content.json` is a replica only when its decoded ID positively matches the target timeline. A root file for another timeline is never updated merely because it is nearby or named similarly.

## Compatibility

The observed names `draft_content.json`, `.bak`, `template-2.tmp`, and `draft_content.json.bak` are candidate names, not a promise that all four exist or that every draft uses the same set. Future names require positive decoded association before they can be added to a write set.
