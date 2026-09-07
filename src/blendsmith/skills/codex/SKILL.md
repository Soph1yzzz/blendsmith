---
name: blendsmith
description: >
  Operate Blender work through the installed BlendSmith CLI/Core when the user
  explicitly names BlendSmith as the mechanism to use, such as "BlendSmithを使って",
  "Use BlendSmith", or "$blendsmith". BlendSmith owns production structure,
  method-selection, evidence, review, change-impact routing, repair/reselection,
  human approval, checkpoint, retention, and publication gates. Do not invoke this
  Skill merely because a task happens to involve Blender.
metadata:
  version: "0.0.2"
---

# BlendSmith

BlendSmith is the authoritative production-loop harness. This Skill is only the
thin Codex operating layer around the installed `blendsmith` CLI/Core.

## Invocation gate

Use this Skill only when the user explicitly asks to use BlendSmith as the
mechanism for the Blender task. Do not infer invocation from an ordinary Blender
request.

## Authority rule

The installed BlendSmith CLI/Core is the source of truth. Do not reproduce or
silently emulate its state machine in prompts.

Before work:

1. Run `blendsmith --version` and fail clearly if the CLI is unavailable.
2. Run `blendsmith doctor`. Continue only when it returns `ready: true` and the
   installed Skill status is `CURRENT`.
3. Use `blendsmith next --project <project>` as the primary state/introspection
   surface. It exposes the next valid action, authoritative plan/selection hashes,
   active candidate identity/path, and method-cache status.
4. Use command-specific `--help` and `blendsmith schema <contract>` whenever a
   current contract is not known exactly.
5. Never bypass a rejected transition, stale SHA, unresolved capability,
   change-impact gate, global reassessment, or owner gate.

`AI_ACCEPTED != HUMAN_ACCEPTED`. Never run `owner-accept` unless the owner has
explicitly accepted the exact candidate presented for review.

## Project entry

Resolve the target Blender project from the user's request and current workspace.
If it is not yet a BlendSmith project, initialize it with:

`blendsmith init <project>`

Then capture runtime capabilities and start the run:

`blendsmith preflight --project <project> [--blender <path>]`

`blendsmith start --project <project> [--blender <path>]`

Do not attach an initial candidate before the production structure and Method
Selection Gate are complete.

## Production structure

At `AWAITING_METHOD_PLAN`, do not submit one broad work unit when the task hides
meaningfully different method families. Decompose the work into units that have a
clear rationale, stage, dependencies, and method-selectable operations. For every
work unit, account for every method family required by the current `method_plan`
schema as `APPLICABLE` or `NOT_APPLICABLE` with concise evidence. Any family marked
`APPLICABLE` must have its own matching method operation. This accounting step is
not optional even when the overall object could be described as one thing.

The Method Plan is a dependency-aware Production Graph. Ask:

- why does this work unit exist?
- what must exist before it?
- what later work depends on it?
- which operation needs a dedicated Blender method?

A revised upstream plan must supersede the exact previous plan SHA. Never edit an
already validated Method Plan in place.

## Method discovery and selection

Use `blendsmith method-hints` for built-in dedicated-method hints. Before repeating
expensive discovery, inspect `blendsmith method-cache --project <project>
[--intent <intent>]`.

The cache contains reusable discovery facts only. It is not selection authority.
A current Method Selection contract still has to evaluate those facts against the
current requirements.

Selection policy:

- `SPECIALIZED + FULL`: normally preferred over generic construction.
- `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT` versus `GENERAL_PURPOSE + FULL`:
  general-purpose may win only with the current evidence-backed waiver required by
  the schema.
- unresolved specialized candidates block fallback.
- scratch construction remains the last fallback.

During later repair, preserve the already selected method when it still fits.
Do not start hand-building a replacement for a capability that is already the
validated method for that operation.

## Review and change routing

Evidence review and live GUI review do not jump directly into arbitrary repair.
When either review returns `REVISE`, BlendSmith enters `AWAITING_CHANGE_IMPACT`.
Classify the change at the correct abstraction level:

- `LOCAL`: bounded defect; preserve current method authority and enter Fix Plan.
- `METHOD`: current construction method is wrong; return to Method Selection.
- `STRUCTURAL`: work-unit dependencies or production structure must change; revise
  the Method Plan / Production Graph.
- `CONTRACT`: the upstream requirement itself is wrong; revise the upstream plan
  rather than hiding the change in implementation.

If local repair repeats or the change-impact contract recommends it, the Core may
enter `AWAITING_GLOBAL_REASSESSMENT`. Stop patching and reassess the current plan,
graph, methods, candidate, issues, and repair history before deciding whether to
continue locally, reselect a method, revise structure, or revise contract.

## Exploratory live GUI review

`AWAITING_LIVE_GUI_REVIEW` is exploratory visual QA, not merely proof that Blender
opened. Use real GUI/computer interaction when available:

- orbit the asset and inspect unseen angles;
- zoom into connections, thickness, ornament, and dense detail;
- inspect rear/underside/occluded surfaces;
- inspect material response where relevant;
- look for technically valid but visually underdeveloped regions;
- record only the highest-value bounded quality-gain issues allowed by the current
  project policy.

A GUI `REVISE` goes through Change Impact. Do not jump straight to hand edits.
Never downgrade `BROKEN` or `UNKNOWN` GUI capability to `UNAVAILABLE`.

## Operate by current state

Prefer `blendsmith next --project <project>` over guessing internal paths or IDs.
Typical states:

- `AWAITING_METHOD_PLAN`: author the dependency-aware Method Plan.
- `AWAITING_METHOD_SELECTION`: probe or reuse valid discovery facts and submit the
  current Method Selection contract.
- `WORKING`: perform authorized Blender work and ingest/select a candidate.
- `RENDERING_EVIDENCE`: generate and submit required evidence.
- `AWAITING_VISUAL_REVIEW`: actually open and inspect evidence, then submit review.
- `AWAITING_CHANGE_IMPACT`: classify the requested change before editing.
- `AWAITING_GLOBAL_REASSESSMENT`: reassess the whole active production decision.
- `AWAITING_FIX_PLAN`: keep repair bounded and preserve required methods.
- `AWAITING_LIVE_GUI_REVIEW`: perform exploratory Blender GUI inspection.
- `FINAL_AI_VALIDATION`: run `blendsmith ai-accept` only after all gates pass.
- `OWNER_REVIEW`: stop and present the exact candidate/evidence to the owner.
- `OWNER_ACTION_REQUIRED`: stop. Resolve the recorded condition. For a supported
  live-GUI capability failure, reprobe explicitly and then use
  `blendsmith owner-action-recover --project <project>`; do not create a new run
  merely to escape the gate.

When interrupted, prefer `blendsmith checkpoint` and `blendsmith resume`; do not
recreate lost authority from conversational memory.

## Blender operation

BlendSmith verifies the production lifecycle; it does not replace the actual
Blender operator. Use the best available host capability: Blender MCP,
`bpy`/headless Blender, direct GUI/computer use, reusable assets, Geometry Nodes,
modifiers, or installed extensions.

For reproducible setup and structural validation, prefer scripts/contracts that
can be rerun. For visual/spatial quality, inspect render evidence and the live GUI
directly. Keep accepted artifact bytes and authority boundaries under BlendSmith
Core.

## Completion

A successful AI-side run may reach `OWNER_REVIEW`, but that is not human approval.
Only explicit owner authority may produce human acceptance. Publication and
revision must continue through the CLI/Core rather than direct file copying or
manual pointer edits.
