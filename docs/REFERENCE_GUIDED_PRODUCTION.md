# Reference-guided production (v1.0.0)

When an image is supplied as an actual production target, it must survive the
entire BlendSmith lifecycle. Saving a render without ever looking back at the
source photograph is **not** a reference-guided workflow.

## Register before candidate ingestion

```sh
blendsmith reference-add --project <project> --id front-target --image <photo.png>
blendsmith references --project <project>
```

Core validates the image, copies it to a run-owned immutable path and records
the SHA-256, dimensions and required-in-Blender policy. Candidate closures also
include a copy of every pinned reference. References are registered before the
first candidate, not after an unfavorable comparison.

**Default policy:** if the image is a reference to be retained in the scene,
pack its original image bytes into the saved Blender file before candidate
ingestion. In Blender Python, a file-backed image can normally be packed with
`image.pack()`. Pack before saving, and test the saved file by reopening it.
For a source that is *only* a visual mood/composition reference, use
`reference-add ... --comparison-only`; comparison still applies.

## Required render-to-reference review

Open the pinned image and the corresponding evidence render at review time.
Use `blendsmith template --project <project> --contract visual_review` for a
candidate-identity-bound draft. Complete each `reference_comparisons` item
**from actual observation**:

```json
{
  "reference_id": "front-target",
  "reference_sha256": "<the SHA returned by blendsmith references>",
  "view_keys": ["front"],
  "observations": [
    "Main silhouette and camera framing match the provided photograph.",
    "Rear debris is more uniform than in the photograph."
  ],
  "fidelity": "ACCEPTABLE_DEVIATION",
  "accepted_deviations": [
    "Rear debris distribution was not a required target in this brief."
  ]
}
```

All referenced view keys must also be present in `opened_evidence`. A reviewer
must record one entry **for every** pinned image. Any unresolved MISMATCH or a
stale reference SHA blocks `ACCEPT`. The contract can verify the consistency
of this evidence; it cannot mechanically prove a human or model's subjective
visual assessment is correct.

## Final Blender-file audit

Before `AI_ACCEPTED`, Core independently reopens the **pinned candidate** in
Blender background mode with auto-execution disabled. It checks that the scene
loaded, all used FILE/SEQUENCE/MOVIE images resolve, and each required reference
has a used packed image with exactly the source SHA-256. A failed audit blocks
acceptance. A hash-bound audit receipt is checked again before owner acceptance
and publication.

The Blender re-open is an additional integrity check, **not** a replacement for
the render comparison or exploratory GUI review.

## Other v1.0.0 workflow changes

- `blendsmith next --compact`: minimal state and next action, without the
  full method cache payload.
- `blendsmith template --contract quick_tune` creates an identity-bound
  *unfinished* parameter-tuning draft.
- `blendsmith quick-tune --input ...` submits the normal LOCAL impact and
  Fix Plan in one operation, restricted to non-blocking, nonstructural small
  adjustments. It does not change the Blender model or bypass reviews.
- `method_family_default` in a Method Plan permits a common NOT_APPLICABLE
  reason and sparse exceptions; Core expands it into the same complete method
  accounting as before.
- Known method-hint enumeration can be skipped only after selecting a verified
  fully fitting dedicated method; fallback remains fail-closed.
- Reviewers can report any number of defects. Fix Plan still prioritizes at
  most two primary issues. Four LOCAL repairs by default, repeated issue IDs,
  major regressions or a requested reassessment trigger a broader review.

Older runs without pinned references retain their earlier review contracts,
while new image-guided runs require the additional comparison and scene audit.
Internal A/B model benchmarking remains outside the public package.
