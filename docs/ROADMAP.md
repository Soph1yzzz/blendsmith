# BlendSmith Roadmap

BlendSmith v0.0.1 established the model-neutral production loop: method selection, evidence-backed review, bounded repair or method reselection, checkpointing, live-GUI verification, exact human approval, retention, and verified publication.

v0.0.2 moves the loop one level upstream. A visible defect is no longer assumed to be a local mesh problem: BlendSmith can return to the method, production structure, or upstream contract that actually introduced the bad decision.

## v0.0.2 — Production Structure

### Shipped

- **Work Unit Decomposition Gate** — every work unit must account for each known method family as `APPLICABLE` or `NOT_APPLICABLE`; applicable families require explicit method-selectable operations.
- **Production Graph** — work units carry rationale, stage, and dependency edges; graph cycles and unknown dependencies are rejected.
- **Method Selection Policy v2** — `SPECIALIZED + FULL` remains the default priority, while `GENERAL_PURPOSE + FULL` may displace `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT` only with an evidence-backed waiver. Scratch remains the final fallback.
- **Method Continuity Gate** — a `LOCAL` repair must preserve the validated methods for the affected work units.
- **Change Impact Gate** — review findings are classified as `LOCAL`, `METHOD`, `STRUCTURAL`, or `CONTRACT` before editing continues.
- **Upstream revision and graph invalidation** — structural/contract changes supersede the immutable previous Method Plan and invalidate affected downstream work before production resumes.
- **Global Reassessment** — repeated local repair can force a whole-production-context review before another local patch is authorized.
- **Exploratory Live GUI Review** — GUI review requires real exploratory coverage such as orbit, zoom, and an unseen viewpoint; meaningful quality-gain findings cannot be ignored in a `PASS`.
- **Owner Action same-run recovery** — supported capability failures can re-enter the same run only after a newer explicit reprobe proves the condition was repaired.
- **Evidence Profiles** — evidence can use orientation-aware per-view profiles instead of one global width/height rectangle.
- **Agent introspection** — `blendsmith next` exposes the next valid action plus authoritative candidate/method identities instead of requiring the agent to guess internal paths.
- **Bounded Method Discovery Cache** — reusable discovery facts are environment-bound and non-authoritative. Sources without a Core-owned freshness fingerprint must be checked again.

### Deliberately not in v0.0.2

The following ideas remain useful, but are not part of the v0.0.2 release contract:

- domain-specific construction sequences
- architecture-specific structural/coherence profiles
- persistent first-class issue lineage (`OPEN`, `RESOLVED`, `DEFERRED`, `REGRESSION`, `SUPERSEDED`)
- CAD recommendation or CAD intermediate workflows

v0.0.2 keeps the production-structure layer model-neutral rather than claiming engineering or architecture-domain certification.

## v0.0.3+

Candidates for later releases:

- construction-sequence / domain-profile support for architecture and other structure-heavy tasks
- richer structural/coherence validation built on the Production Graph
- persistent issue lineage across iterations
- CAD recommendation and capability probing
- CAD intermediate retention / GC using the existing checkpoint and TTL model
- richer look-development provider support
- additional Blender backends and adapters
- source-specific freshness fingerprints that safely widen discovery-cache coverage
- benchmark harnesses for measuring success rate, iteration count, and quality deltas
- blind A/B evaluation of harnessed vs. non-harnessed workflows
