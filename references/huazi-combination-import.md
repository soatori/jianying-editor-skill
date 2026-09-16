# Flower-text combination import

Flower-text presets are version-sensitive composite objects. Use a saved, working prototype from the current or explicitly approved template draft.

- Discover the combination through the segment's `extra_material_refs`; do not assume the visible material ID is the combination root.
- Copy the complete nested combination and referenced materials before changing text or timing.
- Preserve the animation/material shell and replace exact copied references with new IDs.
- Validate the resulting layer order and read back the visible text fields.
- Reject a preset when its font record is null, its font path points outside the current machine, or its `frid` is null without a valid same-group fallback.
- Prefer `fonts[0].path` from a validated same-group font record over a material-level `font_path`.

Font fallback is a local capability check, not a hardcoded user-directory rule. Record the selected path and fallback reason in the packaging verification report.
