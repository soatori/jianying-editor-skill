# Timeline operation contract

`apply-plan` consumes ordered keep blocks on the current target timeline. The CLI is dry-run by default; pass `--apply` only after the plan and preconditions have been reviewed:

```json
{
  "version": 1,
  "timeline_id": "optional-explicit-id",
  "ripple": "all",
  "keep_blocks": [
    {"start_us": 0, "end_us": 12000000, "label": "opening"},
    {"start_us": 18000000, "end_us": 30000000, "label": "answer"}
  ],
  "track_ids": []
}
```

- Blocks use the pre-edit target time axis and half-open ranges.
- Blocks must be positive and may not overlap. Their listed order is output order.
- `ripple: "all"` applies the assembly to every track.
- `ripple: "tracks"` requires explicit `track_ids`; untouched tracks keep their timing and can make a reordered program invalid.
- Plans containing unresolved, low-confidence, or review-only decisions are not executable.
- This contract carries implementation ranges, not editorial reasoning.
- Time assertions should be resolved against the saved draft with `locate` and a default ±40ms tolerance; rounded decimal seconds are not exact identifiers.
- The write target is the associated `ReplicaManifest` discovered by `jianying-editor`, not a fixed number of filenames.
- CLI stdout is exactly one JSON document: script mode flushes the result and exits via `TerminateProcess`, which skips `videoeditor.dll` detach notifications so its buffered bytenn/mobilecv2 banners never land after the JSON. Consumers that embed the runtime in-process (not script mode) should still parse with `json.JSONDecoder().raw_decode` as a belt-and-braces measure.
- Subtitle-alignment and packaging plans are translated to current draft locators by an adapter. This contract does not authorize the editor to invent semantic or visual decisions.
