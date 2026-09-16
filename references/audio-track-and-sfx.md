# Audio tracks and sound-effect closures

Sound-effect execution is a packaging decision executed by this skill. The editor must preserve the complete material closure of the selected sound segment.

Before writing an audio operation:

- identify the source segment or an existing target segment;
- verify the source media path exists;
- preserve source range, target range, volume, fades, and overlap fields unless explicitly overridden;
- include all referenced audio material records and any `beats`/related buckets used by the current draft;
- generate new IDs for copied objects and replace exact references only inside the copied closure.

After writing, validate both the audio track and material references, then read back every associated replica. A sound is not considered imported merely because an asset name or cache hash exists.
