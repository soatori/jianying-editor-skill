# Normalized inspection model

The inspection layer exposes a stable summary without rewriting native project data.

## Project

- `root`
- `layout`: `legacy-single`, `multi-timeline`, `hybrid`, or `unknown`
- per-file `encryption`: `plaintext`, `jianying-dll`, or `unknown`
- discovered project index
- active candidates with evidence
- unambiguous active timeline ID when available
- normalized timelines

## Timeline

- `id`, `name`, `deleted`
- primary content path and confirmed replica paths
- `duration_us`
- track/material summaries
- untouched native decoded object when explicitly requested

## Track and segment

- track: `id`, `type`, `name`, `segment_count`
- segment: `id`, `material_id`, target start/duration, source start/duration

Absent native fields remain absent. A normalized default such as target start zero is for reading and validation only; serialization must not add fields merely because the normalized view contains them.

