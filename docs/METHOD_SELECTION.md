# Method Selection Gate

BlendSmith treats **knowing that a Blender feature exists**, **decomposing work so the feature is visible to the planner**, and **choosing the best available production method** as separate problems.

v0.0.2 therefore puts Method Selection behind a Work Unit Decomposition Gate.

## Core rule

**Specialized first, scratch last.**

But v0.0.2 applies that rule per method-selectable operation, not merely per broad work unit.

## 1. Decompose before selecting

Every work unit must include rationale, stage, dependencies, method-family checks, and one or more method operations.

For every built-in method family, the plan must record:

- `APPLICABLE`, or
- `NOT_APPLICABLE`

with evidence.

If `symmetry` is `APPLICABLE`, a matching `symmetry` operation must exist. An agent cannot submit one broad operation such as `build_sword` and silently hide symmetry, repetition, thickness, or edge-rounding work inside it.

The Method Plan is also the dependency-aware Production Graph. Unknown dependencies, self-dependencies, duplicate operation IDs, and graph cycles are rejected.

## 2. Probe methods for every operation

For each method operation, the selection contract records:

- candidate methods
- source type
- runtime availability (`AVAILABLE`, `UNAVAILABLE`, `BROKEN`, `UNKNOWN`)
- requirement fit (`FULL`, `PARTIAL_LOCAL_REFINEMENT`, `INSUFFICIENT`, `UNKNOWN`)
- probe evidence
- selected method
- bounded remaining manual work when applicable
- an evidence-backed specialized waiver when policy requires one

The contract records execution evidence only. BlendSmith does not require private chain-of-thought or a model-specific reasoning log.

## Discovery sources

The default policy expects these sources to be explicitly settled:

- `BLENDER_NATIVE`
- `GEOMETRY_NODE_TOOLS`
- `ASSET_LIBRARIES`
- `EXTENSIONS`
- `PROJECT_CATALOG`
- `ADAPTERS`

A source may be explicitly `UNAVAILABLE`. A required source left `BROKEN` or `UNKNOWN` blocks selection because the missing information may conceal a more suitable specialized method.

Known method hints from the provider-neutral catalog must also be explicitly represented when relevant.

## Method Selection Policy v2

### Specialized + FULL

An `AVAILABLE` specialized method with `FULL` requirement fit normally blocks general-purpose and scratch fallback.

### Specialized + PARTIAL_LOCAL_REFINEMENT

A partial specialized method remains viable. If it is selected, the contract must record bounded `remaining_manual_work`.

A `GENERAL_PURPOSE + FULL` method may be selected over `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT`, but only with an explicit evidence-backed waiver explaining why the full-fit general method is the better production choice.

### Scratch

`SCRATCH` is the final fallback. It is rejected while a viable specialized or general-purpose method exists.

### Unknowns

A relevant specialized candidate left unresolved, or a required discovery source left `BROKEN` / `UNKNOWN`, blocks fallback.

## Discovery cache

Method discovery can be expensive, but cached discovery must not become stale authority.

BlendSmith therefore caches **discovery facts only**. The cache:

- is bound to a Core-owned environment/catalog/version/epoch fingerprint;
- is not Method Selection authority;
- is accepted only for sources whose freshness Core can prove;
- does not remove the requirement to re-evaluate the current operation requirements;
- is revalidated again when later candidate work depends on that selection.

Sources without a Core-owned freshness fingerprint are checked again instead of receiving a convenient cache hit.

## Method continuity during repair

A `LOCAL` Change Impact decision means the plan and selected method remain valid.

Before a local Fix Plan is accepted, BlendSmith resolves all methods selected for the affected work units. The Fix Plan must preserve that exact method set.

This prevents a repair from quietly abandoning `Mirror`, `Array`, Geometry Nodes, or another validated method and recreating the same behavior by hand.

## Method reconsideration

When Change Impact classifies a problem as `METHOD`, the current candidate is invalidated and the run returns through Method Selection before more production is authorized.

```text
AWAITING_CHANGE_IMPACT
-> CHANGE_IMPACT_VALIDATED
-> METHOD_RECONSIDERATION
-> AWAITING_METHOD_SELECTION
-> METHOD_SELECTION_VALIDATED
-> WORKING
```

The run may also reach Method Selection after Global Reassessment chooses `RESELECT_METHOD`.

## Upstream structure/contract revision

`STRUCTURAL` and `CONTRACT` changes do not belong in Method Selection alone. They return to `AWAITING_METHOD_PLAN`, where a new plan revision must explicitly supersede the exact previous plan SHA. Affected downstream graph nodes are invalidated before another Method Selection round.

## Default method hints

BlendSmith ships a small provider-neutral catalog for common operations, including:

```text
symmetry        -> Mirror
repetition      -> Array / Geometry Nodes
surface scatter -> Geometry Nodes
thickness       -> Solidify
lathe / revolve -> Screw
edge rounding   -> Bevel
hair            -> Geometry Nodes / Node Tool
tree generation -> extension / Node Tool / asset-library discovery
```

Hints are discovery targets, not claims that a method is installed or suitable. Availability and fit still require explicit evidence.
