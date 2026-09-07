# Method Selection Gate

BlendSmith treats **knowing that a Blender feature exists** and **choosing the best available production method for the current work unit** as separate problems.

The gate exists to prevent an agent from immediately building geometry from scratch when a dedicated Blender feature, reusable node tool, asset, extension, adapter, or project-local generator can satisfy the requirement more directly.

## Core rule

**Specialized first, scratch last.**

For every work unit, BlendSmith requires the agent to:

1. identify the production intent and concrete requirements;
2. inspect the configured discovery sources;
3. probe candidate methods instead of relying on model memory alone;
4. prefer an available specialized method when it fully satisfies the requirements or can satisfy them with bounded local refinement;
5. use a general-purpose or scratch method only when specialized options are unavailable, broken, or insufficient for the stated requirements;
6. record only the execution decision/evidence needed to validate the choice. BlendSmith does not require private chain-of-thought or a detailed reasoning log.

A typical tree work unit therefore prefers an installed tree generator, reusable Geometry Nodes/Node Tool asset, or suitable asset-library method before manual trunk/branch construction. The generated result may still be refined locally.

## Work-unit flow

```text
BLENDER_PREFLIGHT
 -> AWAITING_METHOD_PLAN
 -> METHOD_PLAN_VALIDATED
 -> AWAITING_METHOD_SELECTION
 -> METHOD_SELECTION_VALIDATED
 -> WORKING
 -> candidate ingest
 -> evidence / visual QA
```

A method plan decomposes the requested production work into independently selectable units, for example `tree_generation`, `surface_scatter`, `symmetry`, or `thickness`.

After `method-plan` is accepted, the Core stores a normalized authoritative plan and exposes its SHA-256 as `metadata.method_plan_sha256` in the run state. The next method-selection contract must use that Core-issued SHA; callers should not hash their local input JSON because formatting/encoding may differ from the normalized authoritative bytes.

The selection contract is model-independent. For each work unit it records:

- methods considered;
- source type;
- runtime availability (`AVAILABLE`, `UNAVAILABLE`, `BROKEN`, `UNKNOWN`);
- requirement fit (`FULL`, `PARTIAL_LOCAL_REFINEMENT`, `INSUFFICIENT`, `UNKNOWN`);
- probe evidence;
- selected method;
- remaining bounded manual work.

## Discovery sources

The default policy expects these sources to be accounted for:

- `BLENDER_NATIVE`
- `GEOMETRY_NODE_TOOLS`
- `ASSET_LIBRARIES`
- `EXTENSIONS`
- `PROJECT_CATALOG`
- `ADAPTERS`

A source may be explicitly `UNAVAILABLE`. A required source left `BROKEN` or `UNKNOWN` blocks method selection because the missing information could conceal a more suitable specialized method.

Project profiles may change the required source set, but the policy remains explicit and machine-validated.

## Fallback rules

Selecting `GENERAL_PURPOSE` or `SCRATCH` is rejected when any considered `SPECIALIZED` method is both:

- `AVAILABLE`; and
- `FULL` or `PARTIAL_LOCAL_REFINEMENT` fit.

Any selection is blocked while a relevant specialized method remains `UNKNOWN` or while a required discovery source remains `BROKEN`/`UNKNOWN`. Fallback therefore happens only after the specialized search is settled.

This does not ban custom modeling. It makes custom modeling the explicit fallback when dedicated methods genuinely cannot satisfy the work unit.

## Method mismatch during visual QA

A visual problem can be either a local defect or a method-selection defect.

```text
VISUAL_REVIEW_VALIDATED
 ├─ LOCAL_REPAIR
 │    -> AWAITING_FIX_PLAN
 │
 └─ METHOD_RECONSIDERATION
      -> METHOD_RECONSIDERATION
      -> AWAITING_METHOD_SELECTION
      -> METHOD_SELECTION_VALIDATED
      -> WORKING
```

`METHOD_RECONSIDERATION` starts a new improvement iteration, clears the active candidate, and requires a new method selection before another candidate can be reviewed. The original work plan remains the authority unless the run is explicitly restarted with different requirements.

## Default method hints

BlendSmith ships a small provider-neutral hint catalog for common Blender operations such as symmetry, repetition, thickness, surface scattering, lathe/revolve work, hair, and tree generation. When a work-unit intent matches this catalog, every known hint must be explicitly accounted for in the method-selection contract; an agent cannot silently omit a known dedicated method and jump to scratch modeling. Hints are not claims that a method is installed or compatible: each hinted method still needs an explicit availability/fit result and probe evidence.
