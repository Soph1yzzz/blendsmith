# Changelog

## 0.0.3 — Domain Knowledge

- Added a Domain Research Gate before production planning, with explicit accounting for real-world function, dimensions, structure, manufacturing/construction process, safety/clearance, regulation/standards, and specialist practice.
- Added SHA-bound Domain Knowledge receipts for researched findings, sources, confidence, volatility, and limitations.
- Added a Domain Practice Gate that converts actionable findings into production rules or requires an explicit reason to ignore them.
- Bound practice rules into Method Plan work units through immutable `domain_constraints`, so researched constraints cannot be silently forgotten or weakened during decomposition.
- Added confidence propagation from findings to practice rules and work-unit constraints; downstream contracts cannot claim stronger confidence than their evidence.
- Added bounded Domain Knowledge Cache with scope fingerprints, volatility-aware TTLs, cache epochs, digest checks, and recomputed validity windows.
- Kept cached knowledge non-authoritative: every run still rebuilds Domain Practice before planning.
- Added forced fresh-knowledge behavior when Change Impact or Global Reassessment explicitly returns upstream to Domain Research.
- Extended Change Impact and Global Reassessment so structural/contract failures can revisit domain assumptions before replanning.
- Extended checkpoints, resume, `blendsmith next`, CLI schemas, and the bundled Skill to preserve and expose the Domain Research → Knowledge → Practice → Method Plan authority chain.
- Preserved v0.0.2 run compatibility while requiring the new domain fields for new v0.0.3 runs.
- Added multi-domain virtual dogfood, adversarial cache/receipt tamper tests, package/wheel smoke tests, and private self-security review.

## 0.0.2 — Production Structure

- Added the Work Unit Decomposition Gate with explicit method-family accounting.
- Turned Method Plan into a dependency-aware Production Graph with cycle/unknown-dependency rejection.
- Added Method Selection Policy v2 with evidence-backed waiver support for `GENERAL_PURPOSE + FULL` over `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT`.
- Added environment-bound Method Discovery Cache for reusable discovery facts without turning cache into selection authority.
- Added Change Impact classification: `LOCAL`, `METHOD`, `STRUCTURAL`, and `CONTRACT`.
- Added Method Continuity enforcement for local repairs.
- Added upstream Method Plan revision with immutable predecessor SHA and downstream invalidation.
- Added Global Reassessment to interrupt repeated local patch stacking.
- Upgraded live GUI review into exploratory review with orbit/zoom/unseen-angle coverage and bounded quality-gain findings.
- Added same-run recovery from supported owner-action capability failures after a newer explicit reprobe.
- Added orientation-aware Evidence Profiles, including portrait evidence support.
- Added `blendsmith next` and method-cache introspection for agent-facing authoritative paths, hashes, and next actions.
- Extended checkpoints to preserve Method Plan revision and Method Selection round authority.
- Tightened cache, recovery, GUI, and contract validation based on self-security review and multi-domain virtual dogfood.
- Updated bundled Codex Skill and public documentation for the v0.0.2 loop.

## 0.0.1

Initial public release.

- Model-neutral BlendSmith CLI/Core.
- Blender 5.2 LTS runtime probing.
- Specialized-first Method Selection Gate.
- Evidence-backed visual review and bounded repair.
- Method reconsideration path for wrong production approaches.
- Live-GUI verification when capability is available.
- Exact SHA-bound owner acceptance.
- Candidate/dependency closure pinning.
- Checkpoint/resume with method-authority restoration.
- TTL retention and verified GC boundaries.
- Verified local publication.
- Bundled Codex Skill with CLI/Skill SHA and version pin checks.
