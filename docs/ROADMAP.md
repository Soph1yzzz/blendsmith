# BlendSmith Roadmap

BlendSmith evolves by moving production decisions upstream without turning the Core into a domain-specific expert system.

## v0.0.3 — Domain Knowledge

v0.0.3 adds a knowledge layer before production structure. The loop can now ask whether real-world or specialist knowledge is needed, acquire or safely reuse that knowledge, convert it into actionable practice rules, and bind those rules into work-unit constraints before Method Selection begins.

Shipped:

- Domain Research Gate with seven explicitly accounted risk families
- Domain Knowledge receipts with sources, findings, confidence, volatility, and limitations
- Domain Practice Gate with actionable-rule / explicit-ignore accounting
- `domain_constraints` bound from practice rules into Method Plan work units
- confidence propagation that prevents downstream confidence laundering
- scope- and freshness-bound Domain Knowledge Cache
- cache reuse for facts without reusing practice authority
- forced fresh research after an explicit upstream domain-knowledge reconsideration
- Domain Research re-entry from STRUCTURAL / CONTRACT changes
- domain authority in checkpoints, resume, `blendsmith next`, CLI schemas, and the bundled Skill
- v0.0.2 run compatibility
- multi-domain virtual dogfood and adversarial self-security coverage

The key rule is: **research before a production decision when geometry depends on real-world knowledge; if that assumption later proves suspect, return to the knowledge layer instead of patching around it.**

## v0.0.2 — Production Structure

v0.0.2 moved review one level upstream from local repair:

- Work Unit Decomposition Gate
- Production Graph
- Method Selection Policy v2
- bounded Method Discovery Cache
- Change Impact: LOCAL / METHOD / STRUCTURAL / CONTRACT
- Method Continuity
- Global Reassessment
- Exploratory Live GUI Review
- same-run Owner Action recovery
- Evidence Profiles and agent introspection

## Later candidates

Useful directions that are intentionally not part of the v0.0.3 release contract:

- contract-template generation to reduce JSON ceremony without weakening gates
- construction-sequence / richer domain profiles for architecture and other structure-heavy tasks
- source-specific freshness proofs that safely widen cache coverage
- persistent first-class issue lineage across iterations
- CAD recommendation / capability probing and optional intermediate retention
- richer look-development providers and Blender backends/adapters
- benchmark harnesses for success rate, iteration count, and quality deltas
- blind A/B evaluation of harnessed vs. non-harnessed workflows

BlendSmith does not claim engineering, architectural, manufacturing, safety, or regulatory certification. Domain knowledge is evidence carried into a production contract, not a substitute for a qualified professional where one is required.
