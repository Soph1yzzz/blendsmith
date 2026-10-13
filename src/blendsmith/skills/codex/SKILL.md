---
name: blendsmith
description: >
  Operate Blender work through the installed BlendSmith CLI/Core when the user
  explicitly names BlendSmith as the mechanism to use, such as "BlendSmithを使って",
  "Use BlendSmith", or "$blendsmith". BlendSmith owns domain-research decisions,
  evidence-backed domain practice, production structure, method-selection, review,
  change-impact routing, repair/reselection, human approval, checkpoint, retention,
  and publication gates. Do not invoke this
  Skill merely because a task happens to involve Blender.
metadata:
  version: "1.0.0"
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
3. Use `blendsmith next --project <project> --compact` for the ordinary
   state/introspection surface. It exposes the next action and active candidate.
   Use the full `next` response for authoritative plan/selection hashes and
   method-cache details when needed.
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

When actual live Blender GUI use has been observed before the run, record that
capability explicitly during preflight with `--live-gui AVAILABLE`. Do not
invent an observation, treat UNKNOWN as UNAVAILABLE, or bypass the existing
reprobe/recovery protocol if GUI status later changes.

Do not attach an initial candidate before Domain Research, production structure,
and Method Selection gates are complete.

## Reference-guided production (v1.0.0)

When the user provides one or more visual references, register every image
before the first candidate: `blendsmith reference-add --project <project>
--id <id> --image <image>`. Use `blendsmith references --project <project>`
to verify the immutable source SHA and managed path. A supplied reference
cannot silently be ignored. Core pins a copy of each image and bundles it with
each candidate as a dependency.

By default, the reference must also be a **packed image** inside the exact
saved .blend file; do not rely on an external file path surviving after delivery.
If a visual reference is intentionally outside the .blend, explicitly add it
with `--comparison-only` (comparison remains mandatory).

At visual review actually inspect the pinned source image AND the corresponding
render. Report a `reference_comparisons` entry for every source, with matching
SHA, inspected render view keys, concrete differences and a fidelity judgment.
Unresolved reference MISMATCH cannot be accepted; explain acceptable deviations.
Core will independently reopen the pinned .blend in Blender and reject missing
used images and missing/unpacked required references before AI acceptance.
Get identity-bound starter JSON with `blendsmith template --project <project>
--contract visual_review`; complete the observations only after viewing images.

## Domain research and practice

A new run begins at `AWAITING_DOMAIN_RESEARCH`. Do not automatically browse or
research every asset. First decide whether the requested production depends on
real-world function, dimensions, structural relationships, construction or
manufacturing process, safety/clearance, standards, or specialist practice.

If none of those matter and the asset is genuinely aesthetic, submit
`NOT_REQUIRED` with concise evidence. Otherwise submit `RESEARCH_REQUIRED` and
split only the unresolved domain questions into bounded topics. Each topic records
why it matters and whether the knowledge is `STABLE`, `SLOW_CHANGING`, or
`CURRENT`.

At `AWAITING_DOMAIN_KNOWLEDGE`, inspect:

`blendsmith knowledge-cache --project <project>`

A valid cache may reuse previously verified facts for the exact research scope.
Use `blendsmith knowledge-cache-use --project <project>` when valid. `MISS`,
`STALE`, or `INVALID` requires fresh evidence. The knowledge cache is never final
production authority: every run still enters `AWAITING_DOMAIN_PRACTICE`.

Fresh `domain_knowledge` should record sources and concise findings, not hidden
reasoning. Every actionable finding must then become a `domain_practice` rule or
be explicitly ignored with a reason. The practice contract turns external facts
into concrete requirements and verification checks.

Do not stop at “research completed.” The next Method Plan must bind the exact
practice SHA and map every practice rule into one or more work-unit
`domain_constraints`. A researched constraint cannot silently disappear or be
weakened during planning.

## Production structure

At `AWAITING_METHOD_PLAN`, do not submit one broad work unit when the task hides
meaningfully different method families. Decompose the work into units that have a
clear rationale, stage, dependencies, and method-selectable operations. For every
work unit, account for every method family required by the current `method_plan`
schema as `APPLICABLE` or `NOT_APPLICABLE` with concise evidence. Any family marked
`APPLICABLE` must have its own matching method operation. This accounting step is
not optional even when the overall object could be described as one thing.

The Method Plan is a dependency-aware Production Graph. Ask:

- what real purpose does this work unit serve?
- which domain-practice rules constrain it?
- what must exist before it?
- what later work depends on it?
- which operation needs a dedicated Blender method?

A v1.0.0 method plan can use graph-wide `method_family_default` for shared
NOT_APPLICABLE evidence, with explicit sparse work-unit exceptions. Core expands
it to the complete validated contract; unaccounted families remain forbidden.

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

When one fully fitting, available specialized method has already been explicitly
probed and selected, Core no longer requires manually enumerating every catalog
alternative. This exception does not authorize scratch/general fallback while
specialized candidates are unknown.

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

For `STRUCTURAL` or `CONTRACT`, set `revisit_domain_knowledge: true` when the new
evidence suggests the underlying real-world assumption or expert practice is
wrong or incomplete. BlendSmith will return to Domain Research before planning.
Do not keep patching geometry against a suspect domain assumption.

If local repair repeats or the change-impact contract recommends it, the Core may
enter `AWAITING_GLOBAL_REASSESSMENT`. Stop patching and reassess the current domain
assumptions/practice, plan, graph, methods, candidate, issues, and repair history
before deciding whether to continue locally, reselect a method, revise structure,
revise contract, or return all the way to Domain Research.

For bounded parameter-only adjustments, `blendsmith quick-tune --project
<project> --input <quick_tune.json>` creates the ordinary LOCAL change-impact
and Fix Plan receipts in one CLI operation. Do not use it for geometry changes,
structural issues, high-severity defects or owner revisions. Repeated issues,
major regressions and accumulated repairs still cause whole-plan reassessment.

## Exploratory live GUI review

`AWAITING_LIVE_GUI_REVIEW` is exploratory visual QA, not merely proof that Blender
opened. Use real GUI/computer interaction when available:

- orbit the asset and inspect unseen angles;
- zoom into connections, thickness, ornament, and dense detail;
- inspect rear/underside/occluded surfaces;
- inspect material response where relevant;
- look for technically valid but visually underdeveloped regions;
- record ALL observed issues, including quality-gain opportunities, without
  suppressing problems to fit a batch limit. Fix Plan still limits primary
  repairs per iteration, but the issue history preserves every observation.

A GUI `REVISE` goes through Change Impact. Do not jump straight to hand edits.
Never downgrade `BROKEN` or `UNKNOWN` GUI capability to `UNAVAILABLE`.

## Operate by current state

Prefer `blendsmith next --project <project>` over guessing internal paths or IDs.
Typical states:

- `AWAITING_DOMAIN_RESEARCH`: decide whether domain research is actually needed.
- `AWAITING_DOMAIN_KNOWLEDGE`: inspect valid cache facts or collect bounded fresh evidence.
- `AWAITING_DOMAIN_PRACTICE`: convert actionable findings into production rules.
- `AWAITING_METHOD_PLAN`: map purpose, dependencies, domain constraints, and method operations.
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
