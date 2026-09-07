---
name: blendsmith
description: >
  Operate Blender work through the installed BlendSmith CLI/Core when the user
  explicitly names BlendSmith as the mechanism to use, such as "BlendSmithを使って",
  "Use BlendSmith", or "$blendsmith". BlendSmith owns method-selection, evidence,
  review, repair, human-approval, checkpoint, retention, and publication gates.
  Do not invoke this Skill merely because a task happens to involve Blender.
metadata:
  version: "0.0.1"
---

# BlendSmith

BlendSmith is the authoritative production harness. This Skill is only the thin
Codex operating layer around the installed `blendsmith` CLI/Core.

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
   installed Skill status is `CURRENT`. A stale, modified, missing, or unsafe
   Skill is an invalid operating state; do not emulate the current Core from an
   older Skill. Ask the user to reinstall/update the Skill and restart Codex.
3. Use `blendsmith --help` and command-specific `--help` when the current CLI
   behavior is unclear.
4. Use `blendsmith schema <contract>` before authoring a JSON contract whose
   exact fields are not already known from the current run.
5. Use `blendsmith status --project <project>` to decide what operation is
   currently authorized.
6. Never bypass a rejected transition, failed integrity check, unresolved
   capability, or owner gate.

`AI_ACCEPTED != HUMAN_ACCEPTED`. Never run `owner-accept` unless the owner has
explicitly accepted the exact candidate presented for review.

## Project entry

Resolve the target Blender project from the user's request and current workspace.
If it is not yet a BlendSmith project, initialize it with:

`blendsmith init <project>`

Then capture runtime capabilities and start the run:

`blendsmith preflight --project <project> [--blender <path>]`

`blendsmith start --project <project> [--blender <path>]`

Do not attach an initial candidate before the Method Selection Gate is complete.

## Operate by current state

Always read `blendsmith status --project <project>` and advance only through the
operation accepted by the current Core state. Typical responsibilities are:

- `AWAITING_METHOD_PLAN`: decompose the requested work into concrete work units.
  Query `blendsmith method-hints --project <project> --intent <intent>` for known
  dedicated Blender methods and validate the plan against
  `blendsmith schema method_plan`. After submitting it, read
  `metadata.method_plan_sha256` from the Core result or a fresh `blendsmith status`.
  Use that exact Core-issued SHA in the method-selection contract; do not hash the
  local input JSON yourself because Core stores the authoritative normalized plan.
- `AWAITING_METHOD_SELECTION`: inspect/probe Blender native functions, Geometry
  Node tools, asset libraries, installed extensions, project catalogs, and
  configured adapters as required by project policy. Validate against
  `blendsmith schema method_selection`. Prefer a viable specialized method;
  scratch/general-purpose construction is a fallback only after specialized
  options are accounted for and exhausted.
- `WORKING`: perform the Blender work with the best available Blender/MCP/bpy/GUI
  capability. Ingest each candidate with `candidate-add` or select an existing
  active-iteration candidate with `candidate-select`.
- Evidence/review states: render and actually inspect the required evidence,
  submit contracts matching the current schemas, and do not claim visual review
  from file existence or machine checks alone.
- `AWAITING_FIX_PLAN`: keep repair bounded and address the review-selected issues.
- A visual `METHOD_RECONSIDERATION` means the production method itself was wrong;
  return through BlendSmith's method-selection flow instead of endlessly patching
  the existing geometry.
- `AWAITING_LIVE_GUI_REVIEW`: perform real Blender GUI inspection when required
  and available. Never downgrade `BROKEN` or `UNKNOWN` to `UNAVAILABLE`.
- `FINAL_AI_VALIDATION`: run `blendsmith ai-accept --project <project>` only after
  all current gates are satisfied.
- `OWNER_REVIEW`: stop and present the candidate/evidence to the owner. Wait for
  an explicit `ACCEPT`, revision request, or run rejection.
- `OWNER_ACTION_REQUIRED`: stop automatic progress and surface the recorded owner
  action instead of improvising around the failure.

When interrupted, prefer `blendsmith checkpoint` and resume through
`blendsmith resume`; do not recreate lost authority state from memory.

## Blender operation

BlendSmith decides and verifies the production lifecycle; it does not replace the
actual Blender operator. Use the best available host capability for execution:
Blender MCP, bpy/headless Blender, direct GUI/computer use, reusable assets,
Geometry Nodes, modifiers, or installed extensions.

For visual/spatial failures, inspect Blender or rendered evidence directly. For
reproducible setup and structural validation, prefer scripts/contracts that can be
rerun. Keep accepted artifact bytes and authority boundaries under BlendSmith Core.

## Completion

A successful AI-side run may reach `OWNER_REVIEW`, but that is not human approval.
Only explicit owner authority may produce human acceptance. Publication and
revision must continue through the CLI/Core rather than direct file copying or
manual pointer edits.
