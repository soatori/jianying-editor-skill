# Segment location and timebase

## Time matching

Jianying may store a frame-quantized boundary such as `766667µs` when a plan was written as `0.767s`. Locate by the current stored time with a default ±40ms tolerance and then assert additional identity: track, segment, material, and visible text where available.

Use the current saved draft as the source of truth. Do not reconstruct a location from an old report or require decimal timestamps to match exactly.

## Locator order

Prefer the strongest available combination:

1. exact timeline and segment ID;
2. track ID/type plus time tolerance;
3. track plus text/material assertion plus time tolerance;
4. human review when more than one candidate remains.

`locate` is read-only and returns all matches. `resolve_locator()` is the shared adapter entry point; it returns one match only and raises a safety error for zero or multiple matches. A caller must treat that error as a review condition rather than guessing.

## Timerange conventions

- Missing `start` means zero only where Jianying's timerange convention permits it.
- Newly created multi-segment tracks should emit explicit starts and cumulative positions.
- Read-back may normalize the first zero start away; compare semantic timeranges, not raw JSON shape.
- Any local picture-lock boundary must record whether it was chosen from a shot boundary, natural pause, word boundary, or manual marker.
