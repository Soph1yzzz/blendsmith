# BlendSmith Contracts

BlendSmith keeps lifecycle authority in deterministic Core code. External reviewers and host integrations communicate through JSON contracts; a valid JSON document is not automatically authorized to advance a run.

Runtime schemas live in `src/blendsmith/schemas/` and use JSON Schema Draft 2020-12.

## Core contracts

- `project.schema.json` — project policy, fixed limits, evidence profiles, method/cache and production-structure settings.
- `run.schema.json` — authoritative run state.
- `state_event.schema.json` — append-only state-transition event.
- `capability_report.schema.json` — timestamped runtime capability snapshot.
- `method_plan.schema.json` — Work Unit Decomposition Gate + dependency-aware Production Graph.
- `method_selection.schema.json` — probed method choice for every method operation, with policy-v2 waiver support.
- `candidate_manifest.schema.json` — pinned `.blend` plus dependency closure, Method Plan/Selection bindings, and digests.
- `visual_review.schema.json` — evidence-backed external visual review.
- `change_impact.schema.json` — classifies requested change depth as `LOCAL`, `METHOD`, `STRUCTURAL`, or `CONTRACT`.
- `global_reassessment.schema.json` — whole-production-context reassessment after local repair should pause.
- `fix_plan.schema.json` — bounded local repair plan that preserves authorized methods.
- `live_gui_review.schema.json` — exploratory live Blender GUI observation result.
- `owner_decision.schema.json` — `ACCEPT`, `REQUEST_REVISION`, or `REJECT_RUN`.
- `owner_action_required.schema.json` — bounded-failure escalation packet with failure timestamp.
- `checkpoint.schema.json` — resumable verified snapshot including method-plan revision and selection round.
- `retention_record.schema.json` — PIN/TTL lifecycle record.
- `provenance.schema.json` — optional dependency/source provenance.
- `publication_manifest.schema.json` — exact-byte publication record.

## Model-neutral design

The Core validates observable production information rather than a model name or internal reasoning format. Contracts may record:

- run/candidate identity and SHA-256;
- which evidence was actually opened;
- production work units, dependencies, operations, and method-family applicability;
- method availability/fit and probe evidence;
- visual/GUI observations and issues;
- requested change depth;
- the exact method IDs a local repair must preserve;
- whole-plan reassessment decisions;
- owner decisions and publication identity.

BlendSmith does not require private chain-of-thought.

## Authority rules

Schema validation is only the first layer. Runtime invariants additionally bind contracts to the active:

- run and state;
- Method Plan revision and SHA;
- Method Selection round and SHA;
- environment/cache fingerprint where cached facts are cited;
- candidate ID, candidate SHA, and dependency closure;
- review source and issue IDs;
- capability snapshot;
- owner authority boundary.

Examples:

- a `LOCAL` Change Impact contract must preserve exactly the selected methods for affected work units;
- a `METHOD` change must request reselection;
- a revised Method Plan must supersede the exact previous plan SHA;
- a GUI `PASS` must prove exploratory coverage, not merely file existence;
- same-run capability recovery requires a capability observation newer than the failure and explicitly probed;
- `owner_decision: ACCEPT` must name the exact candidate SHA presented for owner review.

## Schema and runtime validation

BlendSmith validates Draft 2020-12 structure plus runtime invariants. Date-time formats are checked with `jsonschema` format checking and important timestamps are reparsed by Core.

Filesystem paths contained in persisted state are never trusted solely because they passed schema validation; managed-path, symlink/reparse, digest, and candidate-closure checks are applied again before use.
