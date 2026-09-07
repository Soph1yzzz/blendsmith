# BlendSmith v0.0.1 Specification

This is the authoritative public specification for BlendSmith v0.0.1.

## Product boundary
BlendSmith orchestrates Blender production from method selection through candidate evidence, structured visual review, bounded repair, optional live-GUI verification, explicit owner approval, retention, and verified local publication. The core has no LLM SDK and does not infer capability from model names. A bundled Codex Skill may provide a thin host-facing operating layer, but lifecycle authority remains in the installed BlendSmith CLI/Core.

Out of scope for v0.0.1: CAD workflows, construction sequencing, domain-specific structural logic, provider-specific look-development systems, and game-engine export pipelines.

## Authority
`AI_ACCEPTED != HUMAN_ACCEPTED`.

Before owner review, BlendSmith records the candidate SHA-256 and dependency-closure manifest. `ACCEPT` must name that exact SHA-256. If the artifact changes after review, acceptance and publication are blocked. Acceptance metadata is stored separately from the accepted artifact bytes.

Owner decisions are exactly:
- `ACCEPT`
- `REQUEST_REVISION`
- `REJECT_RUN`

A normal "fix this" response is `REQUEST_REVISION`, not `REJECT_RUN`.

When revision is requested after acceptance/publication, BlendSmith retracts the current-publication pointer, seeds and pins a replacement generation, demotes the previous final to `EPHEMERAL_SUPERSEDED_FINAL`, applies the configured TTL (24 hours by default), keeps lightweight history, and continues from the new generation.

## Installation, environment, capability
Installation lock records BlendSmith version, dependency versions, schema digests, and adapter versions.

Environment lock records static runtime identity such as OS, host Python, Blender executable/version, Blender embedded Python identity when available, and configured adapter/provider identities. Capability results are not part of the environment lock.

Capability is dynamic and stored as timestamped snapshots. States are `AVAILABLE`, `UNAVAILABLE`, `BROKEN`, and `UNKNOWN`. `UNKNOWN` is never treated as `UNAVAILABLE`. A capability that was available and later fails becomes `BROKEN`; it must not be silently downgraded to bypass QA.

## Blender support
Blender 5.2 LTS is the primary v0.0.1 runtime target. Other Blender 5.x versions may proceed when runtime probing reports a compatible environment; this is not an unconditional support guarantee for every 5.x release.

## State model
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
   -> AWAITING_FIX_PLAN -> FIX_PLAN_VALIDATED -> WORKING
   -> RENDER_QA_ACCEPTED
-> LIVE_GUI_DECISION
   -> AWAITING_LIVE_GUI_REVIEW -> LIVE_GUI_VALIDATED
   -> FINAL_AI_VALIDATION
-> AI_ACCEPTED
-> OWNER_REVIEW
   -> REQUEST_REVISION -> OWNER_REVISION_REQUESTED -> NEW_GENERATION_SEEDED -> WORKING
   -> REJECT_RUN -> OWNER_REJECTED_RUN
   -> ACCEPT(candidate_sha256) -> HUMAN_ACCEPTED_SHA_LOCKED
-> CURRENT_FINAL_PINNED
-> PUBLICATION_STAGING
-> PUBLISHED
```

External-agent work uses explicit waiting states. Returned contracts are validated before advancing.

## Codex Skill boundary

BlendSmith v0.0.1 includes a bundled Codex Skill for explicit `BlendSmith` invocation. The Skill is not a second specification and must not emulate successful state transitions when the CLI/Core rejects them. Before operating, it requires `blendsmith doctor` to report an on-disk `CURRENT` Skill whose bundled metadata version matches the installed CLI/Core version. It then inspects the current `status`, CLI help, and authoritative schemas exposed by `blendsmith schema <contract>`. A fresh Skill install/update requires a Codex restart because the CLI cannot prove host reload. Owner acceptance remains an explicit human authority action and is never inferred by the Skill.

## Method selection
Before an external agent begins a new initial candidate, BlendSmith requires a work-unit plan and a validated method selection. The default policy is **specialized first, scratch last**.

For each work unit, the selection contract records discovery-source status, candidate method availability, requirement fit, probe evidence, the selected method, and bounded remaining manual work. `AVAILABLE` specialized methods with `FULL` or `PARTIAL_LOCAL_REFINEMENT` fit take precedence over `GENERAL_PURPOSE` or `SCRATCH` methods. A relevant specialized candidate left `UNKNOWN`, or a required discovery source left `BROKEN`/`UNKNOWN`, blocks selection until the uncertainty is resolved or explicitly unavailable.

The default discovery-source policy accounts for Blender native functionality, Geometry Node tools, asset libraries, extensions, project-local catalogs, and configured adapters. A source may be explicitly unavailable. For work-unit intents covered by BlendSmith's provider-neutral method catalog, every known dedicated-method hint must be explicitly accounted for as evaluated; omission is not a valid route to scratch modeling. The contract records execution evidence only and does not require private reasoning logs.

When visual review returns `REVISE` with `revision_strategy=METHOD_RECONSIDERATION`, BlendSmith starts a new improvement iteration, clears the active candidate, and returns to method selection instead of entering the local fix-plan loop. `revision_strategy=LOCAL_REPAIR` keeps the existing bounded repair path.

See `docs/METHOD_SELECTION.md` for the full gate contract.

## Visual review contract
The core review schema is model-neutral. It requires run/candidate identity, reviewed SHA-256, verdict, opened evidence, issues, regressions, uncertainties, and next action. Reviewer perspectives may be selected by profile and are not hard-coded into the core schema.

Acceptance is blocked when required evidence was not opened, a critical/high issue remains, a major regression remains, or candidate SHA no longer matches the reviewed SHA.

## Repair policy
A repair iteration addresses at most two primary issues. `max_variants_per_iteration = 3`; this is a per-iteration cap, not a lifetime run-wide cap.

## Live GUI review
Policy is `required_if_capable`.
- `AVAILABLE`: GUI review required before AI acceptance.
- `UNAVAILABLE`: render-only completion allowed with explicit skip record and `render_verified` assurance.
- `BROKEN`: bounded retry, then owner escalation if unresolved.
- `UNKNOWN`: cannot justify a skip.

A GUI `PASS` requires correct Blend path verification, dirty-state check, actual viewport interaction, at least one observed view, matching candidate SHA-256, and no blocking GUI issue.

## Retry
`max_retries = 3`: one initial attempt plus at most three retries, for at most four total attempts. Integrity, safety, authority, path-boundary, unknown-owner-state, destructive-overwrite, provenance/license uncertainty, and secret-exposure failures escalate without blind retry.

After retry exhaustion, BlendSmith records an owner-action packet containing failure category, failed operation, attempts/retries, last healthy state, checkpoint reference, relevant evidence, requested owner action, resume instructions, and final/publication safety status.

## Retention
Classes:
- `PINNED_INSTALLATION`
- `PINNED_ENVIRONMENT`
- `PINNED_ACTIVE_CHECKPOINT`
- `PINNED_CURRENT_FINAL`
- `EPHEMERAL`
- `EPHEMERAL_SUPERSEDED_FINAL`
- `LIGHTWEIGHT_HISTORY`

There is no manual-pin feature in v0.0.1.

Pinned checkpoints and finals protect a dependency closure, not only the root `.blend`. A pinned closure contains the root candidate, required dependency files, per-file SHA-256 values, a deterministic closure digest, and source identity metadata.

A new checkpoint is materialized and verified before the previous active checkpoint is demoted. The same ordering applies to a replacement generation after revision.

GC acts only on expired ephemeral records that are no longer referenced, are not current accepted results, still match their recorded digest, and are within BlendSmith-managed storage. Ambiguous paths are refused.

## Publication
`PUBLISHED` means the current local BlendSmith result was published from the exact human-accepted bytes and is the active publication managed by this project.

Publication uses staging plus verification. Candidate and dependency hashes must match the accepted closure before the current-publication pointer changes. A revision retracts that pointer immediately.

## Provenance
BlendSmith may record source, author, license, source reference, SHA-256, and notes for dependencies/external assets. When a project policy requires provenance, unknown required provenance blocks verified publication.

## Interruption and resume
An interruption is not a quality failure. BlendSmith creates a pinned checkpoint with run state, iteration, unresolved issues, review/fix-plan references, candidate closure, and next action. Resume revalidates checkpoint and candidate identity before returning to the saved active state.

## Acceptance coverage
Tests must cover method-gate ordering, specialized-first fallback enforcement, `UNKNOWN` handling, per-work-unit selection, method-mismatch re-entry, SHA-bound owner acceptance, post-review mutation blocking, revision retraction, replacement-generation ordering, capability downgrade prevention, strict GUI PASS rules, initial+3 retry behavior, review evidence gates, repair/variant budgets, checkpoint replacement, dependency-closure pinning, GC boundary/digest checks, and exact-byte verified publication.
