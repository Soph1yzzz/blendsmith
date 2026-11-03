# Quality Improvement Loop (v1.1.0)

BlendSmith now retains the best **assessed** candidate across improvement iterations, checks
part-level reference targets, and can run read-only evaluated-mesh proximity probes inside
an independent Blender background process. The Core does not claim that a visual judge is
infallible. It prevents missing comparisons, stale identities, unaudited structural claims,
and promotion of an explicitly regressed candidate.

## New image-guided workflow

1. Register all source images before candidate ingestion with **reference-add**.
2. Register a **quality_targets** contract:

   blendsmith quality-targets --project PROJECT --input targets.json

3. Decompose and select methods as usual. Generate and pin a .blend candidate.
4. Render evidence as usual. Actually inspect both the original and the render.
5. Generate an identity-bound draft:

   blendsmith template --project PROJECT --contract quality_assessment

6. Complete every target result in a separate evaluator context and submit:

   blendsmith quality-assess --project PROJECT --input assessment.json

7. Continue with visual-review, GUI review when available, and normal owner approval.

**quality-status** reports registered targets, the best-so-far candidate and its exact hash.
**best-restore** reingests the pinned best into the active WORKING iteration, only when
the authorized Method Selection SHA is still identical.

Old v1.0.0 runs without quality_loop_version remain compatible. New image-guided
v1.1.0 runs require part-level targets before the first candidate.

## Reference targets

The contract pins each target to a source SHA and declares a specific part,
features to reproduce, the views to inspect, priority and whether the interpretation
is inferred. Every registered source image must have at least one target.

Example, with values supplied from **blendsmith references**:

~~~json
{
  "schema_version": 1,
  "targets": [
    {
      "target_id": "handle-profile",
      "reference_id": "front-photo",
      "reference_sha256": "<exact SHA from references>",
      "part": "handle",
      "features": ["leather band width", "fold-over attachment", "curvature"],
      "view_keys": ["front", "side"],
      "priority": "HIGH",
      "inferred": false
    }
  ],
  "geometry_checks": [
    {
      "check_id": "seam-to-leather",
      "source_objects": ["SeamThread"],
      "target_objects": ["LeatherPanel"],
      "max_distance_mm": 0.5,
      "min_source_vertices": 100
    }
  ],
  "geometry_check_rationale": "The stitches should stay close to the leather panel."
}
~~~

This 0.5 mm is an example for a particular asset, **not** a universal manufacturing
tolerance. Use real object names, correct scene units and asset-specific acceptance limits.
If no objective geometry probe is relevant, supply an empty array and an explicit reason.

The optional geometry probe checks the distance from **every evaluated source-mesh
vertex** to the nearest surface of the declared evaluated target meshes, in world
coordinates. It rejects missing meshes, insufficient vertices, too-large meshes
(over 200,000 source vertices), and failed thresholds. It does not downsample to pass.
This proximity metric cannot prove intersection-free assembly, normal orientation,
sewing load or material strength. For those, use other specialized verification.

## Candidate comparison and promotion

The quality_assessment contract binds to the active candidate, target receipt,
opened evidence and the **current** best candidate SHA. Each target records fidelity,
observed details, confidence, and the change relative to the best:

- First candidate: BASELINE.
- Later candidate: IMPROVED, UNCHANGED, REGRESSED, or INCOMPARABLE.

A PROMOTE needs a reviewer context identifier distinct from its creator,
complete feature coverage, no reported regression or incomparability, at least one
improved target for a different candidate SHA, and passing objective geometry
checks. The Core stores a SHA-bound assessment and pins the new best candidate.
A HOLD records a candidate without replacing the best.

Before visual ACCEPT, the active candidate must be the promoted best; no part
may remain MISMATCH, critical targets must be MATCH, and all declared geometry
checks must pass. These receipts are verified again for AI and owner acceptance.

The Core verifies context IDs are different; it **cannot authenticate** that the
review actually came from an independent model/session. Operators must use truly
separate evaluators and keep comparison renders comparable in camera, scale,
illumination and color management. A subjective IMPROVED label is evidence
recorded by the evaluator, not mathematical proof of superior visual quality.

## Developer validation

Do not bundle large A/B scenes or scorecards with the public package.
Keep fixed reproductions of the handbag shape/material gaps and detached stitches
in developer-owned benchmark storage. First verify the new gate catches these
known issues; then run blinded, paired, budget-matched comparisons on withheld
assets. Neither a passing contract nor one favorable A/B run guarantees universal
dominance over ordinary model-driven production.
