# BlendSmith v0.0.2 Specification

This is the authoritative public specification for BlendSmith v0.0.2.

## Product boundary

BlendSmith is a model-independent production control loop for AI-assisted Blender work. It does not replace the model, Blender, MCP, `bpy`, or GUI automation. The Core owns lifecycle authority around them: work decomposition, method selection, candidate identity, evidence, review, change-impact classification, bounded repair, upstream revision, exploratory GUI review, checkpoint/resume, exact owner approval, retention, and verified publication.

The Core has no LLM SDK and does not infer capability from model names. A bundled Codex Skill may provide a thin host-facing operating layer, but it cannot override Core validation.

Out of scope for v0.0.2: CAD workflows, domain-specific construction sequences, engineering/architecture certification, persistent cross-iteration issue-lineage state, provider-specific look-development systems, and game-engine export pipelines.

## Authority

`AI_ACCEPTED != HUMAN_ACCEPTED`.

Before owner review, BlendSmith binds the active candidate to its SHA-256 and dependency-closure manifest. `ACCEPT` must name that exact candidate SHA-256. If reviewed bytes or their pinned closure no longer match, acceptance and publication are blocked.

Owner decisions are exactly:

- `ACCEPT`
- `REQUEST_REVISION`
- `REJECT_RUN`

`REQUEST_REVISION` does not authorize an arbitrary direct edit. It enters the same Change Impact Gate used by visual and GUI review so the requested change is classified at the correct abstraction level first.

If a published result is revised, the current-publication pointer is retracted before the revision loop continues.

## Installation, environment, and capability

Installation lock records BlendSmith version, dependency versions, schema digests, and adapter versions.

Environment lock records static runtime identity such as OS, host Python, Blender executable/version, and configured runtime identity. Dynamic capability results are stored separately as timestamped snapshots.

Capability states are:

- `AVAILABLE`
- `UNAVAILABLE`
- `BROKEN`
- `UNKNOWN`

`UNKNOWN` is never treated as `UNAVAILABLE`. A capability that was available and later fails cannot be silently downgraded to bypass a gate.

Blender 5.2 LTS is the primary runtime target. Other Blender 5.x versions may proceed when runtime probing reports a compatible environment; this is not an unconditional support guarantee for every 5.x release.

## Production structure

### Work Unit Decomposition Gate

Before Method Selection, each work unit must carry:

- a stable `work_unit_id`
- intent and requirements
- rationale
- stage
- dependency edges (`depends_on`)
- `method_family_checks`
- one or more method-selectable operations

For every method family in BlendSmith's built-in catalog, each work unit must explicitly record `APPLICABLE` or `NOT_APPLICABLE` with evidence.

If a family is `APPLICABLE`, a matching method operation is required. If it is `NOT_APPLICABLE`, the work unit may not silently include that operation. This prevents a broad task such as "build the sword" from hiding symmetry/repetition/thickness work and skipping dedicated Blender methods.

Work-unit IDs and operation IDs must be unique. Unknown dependencies, self-dependencies, and graph cycles are rejected.

### Production Graph

The Method Plan is also the Production Graph. Dependency edges define which work becomes stale when an upstream structural or contract revision changes affected work units.

Validated Method Plans are immutable by SHA. Upstream changes create a new plan revision that explicitly supersedes the exact previous plan SHA.

## Method Selection Policy v2

The default policy remains:

**Specialized first, scratch last.**

Selection is performed per method operation, not merely per broad work unit.

Required discovery sources are explicitly accounted for. By default these include:

- Blender native functionality
- Geometry Node tools
- asset libraries
- extensions
- project-local catalogs
- configured adapters

A required source left `BROKEN` or `UNKNOWN` blocks selection. Relevant specialized candidates left unresolved also block fallback.

Fit policy:

- `SPECIALIZED + FULL` normally blocks general-purpose or scratch fallback.
- `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT` remains viable and must be evaluated.
- `GENERAL_PURPOSE + FULL` may displace `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT` only with an explicit evidence-backed waiver.
- `SCRATCH` is rejected while a viable non-scratch method exists.
- a selected `PARTIAL_LOCAL_REFINEMENT` method requires bounded `remaining_manual_work`.

Known built-in hints must be explicitly represented in the selection contract when relevant; omission is not a valid route to scratch construction.

### Method Discovery Cache

The cache stores reusable discovery facts, never Method Selection authority.

Cache identity is bound to Core-owned environment/catalog/version/epoch information. v0.0.2 deliberately caches only discovery sources for which Core can prove a freshness boundary. Sources without such a fingerprint must be checked again.

A cached fingerprint written into a selection does not bypass normal Method Selection validation. The same current fingerprint semantics are revalidated when later candidate work relies on that selection.

## State model

The principal production path is:

```text
CREATED
-> INSTALLATION_PIN_RESOLVED
-> ENVIRONMENT_PIN_RESOLVED
-> CAPABILITY_PREFLIGHT
-> BLENDER_PREFLIGHT
-> AWAITING_METHOD_PLAN
-> METHOD_PLAN_VALIDATED
-> AWAITING_METHOD_SELECTION
-> METHOD_SELECTION_VALIDATED
-> WORKING
-> RENDERING_EVIDENCE
-> EVIDENCE_READY
-> AWAITING_VISUAL_REVIEW
-> VISUAL_REVIEW_VALIDATED
```

A visual `ACCEPT` continues:

```text
VISUAL_REVIEW_VALIDATED
-> RENDER_QA_ACCEPTED
-> LIVE_GUI_DECISION
```

A visual `REVISE` continues:

```text
VISUAL_REVIEW_VALIDATED
-> AWAITING_CHANGE_IMPACT
-> CHANGE_IMPACT_VALIDATED
```

When GUI capability is available:

```text
RENDER_QA_ACCEPTED
-> LIVE_GUI_DECISION
-> AWAITING_LIVE_GUI_REVIEW
-> LIVE_GUI_VALIDATED
```

GUI `PASS` continues to final AI validation. GUI `REVISE` returns to `AWAITING_CHANGE_IMPACT` instead of directly entering `WORKING`.

Final authority remains:

```text
FINAL_AI_VALIDATION
-> AI_ACCEPTED
-> OWNER_REVIEW
   -> ACCEPT(candidate_sha256)
   -> REQUEST_REVISION
   -> REJECT_RUN
```

## Change Impact Gate

A requested change from Visual Review, Live GUI Review, or Owner Revision is classified before further editing as one of:

- `LOCAL`
- `METHOD`
- `STRUCTURAL`
- `CONTRACT`

### LOCAL

The current plan and production method remain valid. The affected work units must preserve the exact validated selected methods through Method Continuity. A bounded Fix Plan then returns to `WORKING`.

### METHOD

The construction method itself is wrong. The current candidate is invalidated and the run returns through Method Selection before more production is authorized.

### STRUCTURAL

Production structure or dependencies must change. BlendSmith requires a new Method Plan revision, preserving the immutable predecessor SHA and invalidating affected downstream work before reselection and production.

### CONTRACT

The upstream requirement/plan itself must change. The old validated plan remains immutable and is superseded by a new revision before dependent work continues.

No `METHOD`, `STRUCTURAL`, or `CONTRACT` change may silently fall through to direct local editing.

## Global Reassessment

Repeated local repair must not become an infinite patch stack.

BlendSmith may enter `AWAITING_GLOBAL_REASSESSMENT` when local-repair streak policy or the Change Impact contract requires it. A valid reassessment must explicitly review:

- Method Plan
- Production Graph
- Method Selection
- current candidate
- open issues
- repair history

It may then choose:

- `CONTINUE_LOCAL`
- `RESELECT_METHOD`
- `REVISE_STRUCTURE`
- `REVISE_CONTRACT`

The selected path returns to the corresponding gate rather than editing immediately.

## Visual review

Visual review remains model-neutral and evidence-backed. It binds run/candidate identity and candidate SHA, records opened evidence, verdict, issues, regressions, uncertainties, and next action.

Visual `ACCEPT` is blocked when required evidence was not opened, a critical/high issue remains, a major regression remains, or candidate identity no longer matches reviewed bytes.

## Evidence Profiles

Evidence requirements may be view-specific. A profile can define minimum width/height and orientation such as landscape, portrait, or square. Without a view-specific profile, the default minimum is applied as long-edge/short-edge requirements so valid portrait evidence is not rejected simply because width and height were swapped.

## Exploratory Live GUI Review

Policy is `required_if_capable`.

- `AVAILABLE`: GUI review is required before AI acceptance.
- `UNAVAILABLE`: render-only completion may proceed through the explicit unavailable path.
- `BROKEN` / `UNKNOWN`: cannot justify a silent skip.

A GUI `PASS` requires all of the following:

- exact candidate identity and SHA
- verified Blend path
- dirty-state check
- actual viewport interaction
- orbit and zoom exploration
- at least one viewpoint outside the fixed render set (for example unseen angle, backside, or underside)
- at least three coverage categories
- at least three observed GUI views
- concrete observations
- no blocking issue
- no ignored medium/high quality-gain opportunity

GUI review also has a bounded meaningful-quality-gain issue budget.

## Repair policy

A Fix Plan addresses at most two primary issues. Local repair must preserve methods authorized by the preceding `LOCAL` Change Impact decision.

`max_variants_per_iteration = 3`; this remains a per-iteration cap rather than a lifetime run-wide cap.

## Owner Action Recovery

`OWNER_ACTION_REQUIRED` is fail-closed. v0.0.2 supports same-run recovery for supported capability failures only when a newer explicit capability observation proves the recorded condition was repaired.

An older/stale capability snapshot, a non-explicit probe, `BROKEN`, `UNKNOWN`, or a different unsupported failure category cannot authorize same-run recovery.

Recovery returns to the recorded last healthy decision point; it does not jump to acceptance or publication.

## Agent introspection

`blendsmith next --project <project>` exposes the next valid action plus relevant authoritative identities such as current Method Plan/Selection SHA, candidate identity, candidate path, and candidate SHA. Agents should use this surface instead of guessing managed paths or IDs.

## Retry

`max_retries = 3`: one initial attempt plus at most three retries, for at most four total attempts. Integrity, safety, authority, path-boundary, ambiguous owner state, destructive-overwrite, provenance/license uncertainty, and secret-exposure failures are not blindly retried.

## Checkpoint and resume

A checkpoint pins validated Method Plan and Method Selection snapshots, their SHA bindings and revision/round identity, candidate closure where present, iteration, and resume state.

Resume revalidates the checkpoint, method identities, candidate manifest, closure digest, and canonical candidate before restoring authority. Conversational memory is not treated as lifecycle authority.

## Retention and GC

Retention classes remain:

- `PINNED_INSTALLATION`
- `PINNED_ENVIRONMENT`
- `PINNED_ACTIVE_CHECKPOINT`
- `PINNED_CURRENT_FINAL`
- `EPHEMERAL`
- `EPHEMERAL_SUPERSEDED_FINAL`
- `LIGHTWEIGHT_HISTORY`

There is no manual pin feature.

GC acts only on eligible expired ephemeral records inside managed storage that still match recorded integrity data and are no longer authoritative.

## Publication

`PUBLISHED` means the current local BlendSmith publication was produced from the exact human-accepted candidate closure.

Publication uses staging and exact-byte verification. Candidate/dependency hashes must still match the accepted closure before the current-publication pointer changes. A revision retracts the current pointer before the revision loop continues.

## Codex Skill boundary

The bundled Codex Skill is a thin adapter. It must not emulate a successful transition the CLI/Core rejected. `blendsmith doctor` verifies the installed Skill bytes/version against the installed package, and a fresh Skill install/update requires a host restart because Core cannot prove the host reloaded new Skill bytes.

Owner acceptance is never inferred by the Skill.

## Acceptance coverage

Tests cover, among other cases:

- decomposition family accounting and graph-cycle rejection
- per-operation Method Selection and specialized-first policy v2
- evidence-backed waiver behavior
- cache fingerprint validation and stale invalidation
- Method Continuity during LOCAL repair
- Change Impact routing for LOCAL/METHOD/STRUCTURAL/CONTRACT
- immutable upstream plan revision and downstream invalidation
- Global Reassessment context requirements
- exploratory GUI PASS/REVISE rules and quality-gain bounds
- same-run owner-action recovery requiring a newer explicit reprobe
- portrait/landscape Evidence Profiles
- SHA-bound owner acceptance and post-review mutation blocking
- checkpoint/resume authority restoration
- dependency-closure pinning, GC boundaries, and exact-byte verified publication
