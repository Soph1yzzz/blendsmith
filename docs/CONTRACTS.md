# BlendSmith Contracts

BlendSmith keeps the core model-independent. External reviewers and host integrations communicate through JSON contracts; the core validates those contracts and keeps lifecycle authority.

Runtime schemas are stored in `src/blendsmith/schemas/` and use JSON Schema Draft 2020-12.

## Core contracts

- `project.schema.json` — project policy and fixed limits.
- `run.schema.json` — authoritative run state.
- `state_event.schema.json` — append-only state transition event.
- `capability_report.schema.json` — timestamped runtime capability snapshot.
- `method_plan.schema.json` — work-unit decomposition before candidate generation.
- `method_selection.schema.json` — probed specialized-first method choice for every work unit.
- `candidate_manifest.schema.json` — pinned `.blend` plus dependency closure, method-selection binding, and digests.
- `visual_review.schema.json` — evidence-based external visual review.
- `fix_plan.schema.json` — bounded repair plan addressing at most two primary issues.
- `live_gui_review.schema.json` — live Blender GUI observation result.
- `owner_decision.schema.json` — `ACCEPT`, `REQUEST_REVISION`, or `REJECT_RUN`.
- `owner_action_required.schema.json` — bounded-failure escalation packet.
- `checkpoint.schema.json` — resumable verified snapshot.
- `retention_record.schema.json` — PIN/TTL lifecycle record.
- `provenance.schema.json` — optional dependency/source provenance.
- `publication_manifest.schema.json` — exact-byte publication record.

## Model-neutral review design

The core does not require a particular model name or internal reasoning format. Method selection records execution evidence rather than private reasoning, and reviews report observable outputs such as:

- which evidence was actually opened,
- candidate identity and SHA-256,
- verdict,
- structured issues and severity,
- regressions,
- uncertainties,
- next action.

Reviewer perspectives such as structure, surface, or reference comparison are policy/profile concerns. They are not hard-coded as model identities in the core schema.

## Authority rules

A valid JSON document is not automatically authorized to advance a run. Runtime invariants additionally bind contracts to the active run, active method plan/selection, active candidate, current candidate SHA, required evidence, current capability state, and owner gate.

In particular, `owner_decision: ACCEPT` must name the exact SHA-256 presented for owner review.

## Schema and runtime validation

BlendSmith validates Draft 2020-12 structure plus runtime invariants. Date-time formats are checked with `jsonschema` format checking. Filesystem paths contained in persisted state are not trusted solely because they passed schema validation; they are checked again against managed storage boundaries before use.
