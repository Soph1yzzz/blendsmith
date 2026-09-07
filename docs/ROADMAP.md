# BlendSmith Roadmap

BlendSmith v0.0.1 established the model-neutral production loop: method selection, evidence-backed review, repair or method reselection, checkpointing, live-GUI verification, exact human approval, retention, and verified publication.

The next release focuses on a problem surfaced by real agent dogfooding: a production loop is only as good as the structure of the work that enters it.

## v0.0.2 — Production Structure

### Release theme

Move from a flat list of work units toward an explicit production structure that captures **what should exist, why it exists, what it depends on, and what must be validated before later work is allowed to rely on it**.

The goal is not to force every Blender task into the same construction recipe. The goal is to make decomposition and dependency reasoning part of the Core contract rather than leaving them entirely to the agent.

### Work Unit Decomposition Gate

Composite work units should not silently hide multiple production methods inside one broad task.

BlendSmith should be able to require finer decomposition when a work unit spans meaningfully different responsibilities or method families—for example geometry, symmetry, ornament, materials, structural support, or presentation.

This is intended to reduce cases where an agent knows a dedicated Blender method exists but never evaluates it because the work unit was defined too broadly.

### Production Graph

Extend the method plan from a flat `work_units[]` list into a dependency-aware production graph.

Planned capabilities:

- explicit work-unit dependencies
- prerequisites that must be satisfied before dependent work proceeds
- stage-aware validation
- deterministic graph re-entry after repair or method reselection
- graph state that survives checkpoint/resume

A production graph should answer questions such as:

- What must exist before this work unit is valid?
- What does this work unit depend on?
- Which later work becomes stale if this unit is revised?
- Which validation gates must pass before downstream work continues?

### Construction Sequence

Architecture and other structure-heavy tasks benefit from reasoning about build order rather than jumping directly to the finished shell.

The initial architecture-oriented sequence is expected to cover:

1. site / access
2. foundation
3. primary structure
4. floors / circulation
5. roof structure
6. enclosure
7. openings / systems
8. finishes
9. presentation

The sequence is not merely a checklist. Each stage should establish the reasons and dependencies that later stages rely on.

### Structural Integrity

Add explicit checks for structural and attachment failures such as:

- unsupported or floating elements
- broken or implausible attachments
- dependent geometry with no valid support relationship
- openings or decorative elements that invalidate the surrounding structure
- later-stage work that no longer matches revised upstream geometry

The first target is practical production coherence, not engineering certification.

### Method Selection Policy v2

Keep **specialized first, scratch last**, while making the policy more precise.

Planned behavior:

- `SPECIALIZED + FULL` remains strongly preferred and normally blocks generic fallback.
- `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT` must still be evaluated, but a `GENERAL_PURPOSE + FULL` method may be selected with an explicit evidence-backed waiver when it is the better fit.
- unresolved relevant specialized methods still block fallback.
- scratch remains the final fallback, not the default.

This preserves the core rule without turning "specialized first" into "specialized always".

### Owner Action Recovery

Improve recovery after capability or environment problems.

When an `OWNER_ACTION_REQUIRED` condition is genuinely resolved and the relevant capability is successfully reprobed, BlendSmith should be able to prove a safe re-entry path into the same run when possible instead of forcing the agent to recreate lifecycle state manually.

Recovery must remain fail-closed: a repaired environment does not automatically authorize acceptance, publication, or stale state reuse.

### Agent UX and Introspection

Reduce the amount of `.blendsmith/` internals that an agent needs to discover manually.

Candidate improvements include:

- a direct "what is the next valid action?" status/introspection surface
- canonical candidate-path lookup
- clearer schema aliases and command discoverability
- authoritative Core-issued hashes exposed where the next command needs them
- less manual transfer of run IDs, plan hashes, and internal paths

The Skill should remain thin; the CLI/Core stays authoritative.

### Evidence Profiles

Make evidence requirements aware of view intent and orientation rather than relying on one generic minimum rectangle.

Examples:

- portrait front views
- landscape environment views
- detail crops
- side/profile validation
- stage-specific structural evidence

Evidence should remain strict enough to prevent low-information review while avoiding accidental rejection of otherwise valid portrait or detail views.

### Issue Lineage

Track review issues across iterations as first-class lifecycle data.

Planned states include:

- open
- resolved
- deferred
- regressed
- superseded

This should make multi-iteration repair loops easier to audit without requiring the agent to manually reconstruct which issue from an earlier review is still active.

## v0.0.3+

Candidates for later releases:

- CAD recommendation and capability probing
- CAD intermediate retention / GC using the existing checkpoint and TTL model
- richer domain profiles beyond architecture
- look-development provider expansion
- additional Blender backends and adapters
- benchmark harnesses for measuring success rate, iteration count, and quality deltas
- blind A/B evaluation of harnessed vs. non-harnessed workflows

CAD is intentionally deferred from v0.0.2 so the production-structure and recovery layers can be made solid first.
