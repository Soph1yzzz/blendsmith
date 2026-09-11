<p align="center">
  <img src="docs/assets/blendsmith-readme-hero.png" alt="BlendSmith — a production control loop for AI-assisted Blender" width="100%">
</p>

<h1 align="center">BlendSmith</h1>

<p align="center"><strong>If you're giving Blender to an AI agent, put this in the loop.</strong></p>
<p align="center">Strong models can already build. BlendSmith keeps the production decisions from drifting.</p>

<p align="center">
  <a href="https://github.com/Soph1yzzz/blendsmith/releases/latest"><img src="https://img.shields.io/github/v/release/Soph1yzzz/blendsmith?style=flat-square&label=release" alt="Latest release"></a>
  <a href="https://github.com/Soph1yzzz/blendsmith/actions/workflows/ci.yml"><img src="https://github.com/Soph1yzzz/blendsmith/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Blender-5.2%20LTS-F5792A?logo=blender&logoColor=white" alt="Blender 5.2 LTS">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-4C8BF5.svg" alt="Apache-2.0"></a>
</p>

<p align="center">
  <strong><a href="README.ja.md">日本語 README</a></strong> ·
  <strong><a href="#quickstart-with-codex">Quickstart</a></strong> ·
  <strong><a href="#what-can-this-workflow-produce">Examples</a></strong> ·
  <strong><a href="#the-production-loop">Loop</a></strong> ·
  <strong><a href="#specialized-first-scratch-last">Method selection</a></strong> ·
  <strong><a href="docs/SECURITY.md">Security</a></strong> ·
  <strong><a href="docs/SPECIFICATION.md">Specification</a></strong>
</p>

If you want an AI agent to do serious Blender work, do not stop at a prompt and hope it keeps making the right decisions. **Put BlendSmith around it.**

BlendSmith is a **model-independent production control loop for Blender agents**. It does not replace the model, Blender, MCP, `bpy`, or GUI automation. It gives them production structure: **decide whether real-world knowledge is needed, turn researched facts into practice rules, decompose the job, expose method-relevant operations, choose dedicated Blender methods before scratch work, track dependencies, inspect rendered and live-GUI evidence, classify what actually went wrong, and return to the right upstream decision before continuing**.

The core idea is simple: **a visible defect does not tell you where the mistake was made**. The right response may be a local edit, a different Blender method, a Production Graph change, an upstream contract revision, or even a return to the domain knowledge that produced the requirement. BlendSmith forces that distinction before the agent is allowed to keep patching.

This is not a crutch for weak models. Capable models already make strong 3D assets. **BlendSmith is the control layer for keeping a capable model on a coherent production path across a long run.**

> Use the model for intelligence. Use BlendSmith for production discipline. If the output is wrong, do not just tell the agent to “try again” — make it return to the level where the bad decision entered the system.

## What can this workflow produce?

I am a beginner at Blender and 3D. These examples are not the result of a Blender expert standing beside the model and manually steering every modeling decision.

In my own production use, **GPT-5.6 Sol was noticeably weak at Blender when used close to its default behavior: method choice was inconsistent, dedicated Blender features were easy to miss, and review tended to stay too local.** I moved method selection, evidence review, repair, reselection, and approval into an external harness and gave the model an explicit production loop.

With the same GPT-5.6 Sol, that workflow was already producing work like this.

<table>
  <tr>
    <td align="center"><img src="assets/examples/gothic-interior.png" alt="AI-assisted Gothic interior created in Blender" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>Gothic architecture / large-scale interior</b></td>
  </tr>
</table>

<table>
  <tr>
    <td width="50%" align="center"><img src="assets/examples/ruby-ring.png" alt="Ruby ring created with the workflow" width="100%"></td>
    <td width="50%" align="center"><img src="assets/examples/emerald-ring.png" alt="Emerald ring created with the workflow" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>Jewelry / dense ornamental detail</b></td>
    <td align="center"><b>Gemstone / hard-surface asset work</b></td>
  </tr>
</table>

That is the starting point: **BlendSmith is not about teaching an AI to make 3D. It is about keeping an AI that can already make 3D from losing the production thread over a long run.**

Can it keep choosing the right methods? Notice when a local-looking defect is really an upstream problem? Inspect what fixed renders miss? Return to the right layer instead of turning the asset into patchwork? BlendSmith is built for that part.

Output quality still depends on the model, references, available Blender capabilities, and iteration. But if you already have a strong model and a way for it to operate Blender, **put BlendSmith between the two and let it govern the production loop**.

### The same direction held with the current generation

This is not a quantitative benchmark; it is a comparison from the author's own production use. But the difference I saw with GPT-5.6 Sol did not disappear when the model got stronger.

In a small internal dogfood run with **GPT-6 Astra** on an ornate sword task, the model could already produce the asset and revise an earlier candidate on its own. Even then, BlendSmith kept method discovery, exact candidate pinning, six-view evidence, exploratory live-GUI inspection, and the hard stop at `OWNER_REVIEW` inside one production loop.

**A stronger model did not make the external production loop irrelevant.** In this small test, the same general effect remained: the harness still improved how the work was structured, inspected, and handed off.

<p align="center">
  <img src="docs/assets/blendsmith-astra-dogfood.png" alt="BlendSmith GPT-6 Astra dogfood proof panel" width="100%">
</p>

## The production loop

v0.0.3 extends the production loop one level further upstream: before planning, BlendSmith can decide whether domain research is needed, bind researched knowledge into production rules, and later return to that knowledge layer when an assumption proves suspect.

```text
request
  -> Domain Research Gate
       -> NOT_REQUIRED -> continue
       -> RESEARCH_REQUIRED
            -> Domain Knowledge (fresh or valid cache)
            -> Domain Practice
  -> decompose work + bind domain_constraints
  -> Production Graph
  -> account for known method families
  -> Method Selection
  -> Blender production
  -> candidate pin
  -> render evidence
  -> visual review
       -> issue / improvement found
            -> Change Impact Gate
                 -> LOCAL      -> preserve method -> bounded Fix Plan
                 -> METHOD     -> Method Selection
                 -> STRUCTURAL -> revise Graph / Plan
                 -> CONTRACT   -> revise upstream contract / plan
                 -> when the assumption itself is suspect
                      -> Domain Research again -> fresh knowledge
       -> render accepted
            -> Exploratory Live GUI Review
                 -> orbit / zoom / unseen angles / hidden surfaces
                 -> REVISE -> Change Impact Gate
                 -> PASS   -> final AI validation
  -> AI_ACCEPTED
  -> OWNER_REVIEW
```

### Research before the production decision

For real-world or specialist-dependent assets, BlendSmith does not let the agent jump straight from the request to geometry.

The Domain Research Gate explicitly checks seven families: function, dimensions, structural relationships, construction/manufacturing process, safety/clearance, regulations/standards, and specialist practice. `NOT_REQUIRED` is allowed only after every family has been explicitly accounted for.

When research is required, findings become a SHA-bound **Domain Knowledge** receipt, then a **Domain Practice** receipt. Actionable findings must become production rules or be explicitly ignored with a reason. Those rules are copied into Method Plan work units as `domain_constraints`, including confidence and verification.

Knowledge may be cached when Core can prove scope and freshness, but cache is facts, not authority. Every run still creates fresh practice authority. If review later says the underlying assumption itself is questionable, BlendSmith can return to Domain Research and require fresh knowledge instead of feeding the same cached assumption back into the loop.


If local repairs keep stacking up, BlendSmith can interrupt them with **Global Reassessment**. The agent has to look again at the Method Plan, Production Graph, Method Selection, candidate, open issues, and repair history before it is allowed to decide that another local patch is still the right move.

This gives each kind of failure a different return path:

- **LOCAL** — the plan and method are sound; preserve the selected method and fix a bounded defect.
- **METHOD** — the construction method is wrong; reselect it instead of recreating a Blender feature by hand.
- **STRUCTURAL** — the dependency structure is wrong; revise the Production Graph and invalidate downstream work.
- **CONTRACT** — the upstream requirement itself changed or was wrong; supersede the old immutable plan instead of hiding the change in implementation.

The GUI stage is not a checkbox at the end. When available, it is an **exploratory review layer** for things fixed renders often miss: thickness, attachments, hidden surfaces, weak detail density, material response, and geometry that only looks wrong after orbiting around it.

The loop still ends deliberately at:

```text
AI_ACCEPTED != HUMAN_ACCEPTED
```

The agent proposes actions. BlendSmith Core decides which transitions are valid. The owner decides whether the exact reviewed artifact is accepted.

## Why not just use the model?

| Common agent failure | BlendSmith response |
| --- | --- |
| The model knows a Blender feature exists, but forgets to use it | **Method-family accounting + Method Selection Gate** — every known family is explicitly marked applicable or not before production |
| A repair quietly switches from Mirror/Array/etc. to hand-built geometry | **Method Continuity Gate** — LOCAL repair must preserve the validated methods for the affected work units |
| A visible problem is actually caused by the plan, not the mesh | **Change Impact Gate** — classify it as LOCAL / METHOD / STRUCTURAL / CONTRACT before editing |
| Small fixes keep accumulating and the whole asset starts drifting | **Global Reassessment** — stop patch stacking and review the whole production context |
| Fixed renders look fine, but the object feels wrong when rotated | **Exploratory Live GUI Review** — orbit, zoom, inspect hidden angles, thickness, attachments, detail density, and material response |
| Method discovery is repeated even though the environment did not change | **Environment-bound discovery cache** — reuse only facts whose freshness Core can prove; recheck the rest |
| The model invents plausible geometry without checking how the real thing functions | **Domain Research Gate** — explicitly account for function, dimensions, structure, process, safety, standards, and specialist practice before planning |
| The same questionable assumption is reused after review says it may be wrong | **Fresh domain re-entry** — upstream reconsideration blocks immediate cache reuse and requires fresh knowledge |
| A candidate exists, so the agent declares success | **Evidence-backed review** — actual views must be opened and evaluated |
| The agent says “looks good” | **AI acceptance is separate from human acceptance** |
| A file changes after review | **SHA-bound authority** — approval names the exact reviewed bytes |
| GUI capability breaks | **No silent downgrade + fresh recovery** — same-run recovery requires a newer explicit reprobe |
| A long run is interrupted | **Checkpoint / resume** — restore validated loop authority rather than improvising from memory |

BlendSmith does not promise that every loop ends in success. It makes the outcome explicit: continue through a valid repair/reselection path, escalate an unresolved condition, or stop at the owner boundary with inspectable evidence.

## Specialized first, scratch last

Knowing that Blender has `Mirror`, `Array`, Geometry Nodes, asset libraries, extensions, or reusable node tools is not the same as selecting them at the right time.

The production loop therefore starts with method discipline rather than immediate construction.

<p align="center">
  <img src="docs/assets/blendsmith-method-selection.png" alt="BlendSmith specialized-first method selection" width="100%">
</p>

Before production, BlendSmith requires a dependency-aware Method Plan. Each work unit must explicitly account for every known method family as **APPLICABLE** or **NOT_APPLICABLE**. If `symmetry` is applicable, for example, the plan must contain a `symmetry` operation; the agent cannot hide it inside a broad “build the sword” operation and silently miss `Mirror`.

After decomposition, BlendSmith requires a machine-validated method-selection receipt. The default discovery policy accounts for:

- Blender native functionality
- Geometry Node tools
- asset libraries
- installed extensions
- project-local catalogs
- configured adapters

Known method hints must be explicitly accounted for. A relevant specialized method left `UNKNOWN`, or a required discovery source left `BROKEN` / `UNKNOWN`, blocks fallback instead of silently authorizing scratch construction.

Method discovery can be cached, but cache is deliberately **not selection authority**. BlendSmith only reuses discovery facts when Core can prove the relevant freshness boundary. Sources without a Core-owned freshness fingerprint are rechecked live rather than receiving a convenient but stale cache hit.

Method Selection v2 also distinguishes fit quality: a `SPECIALIZED + FULL` method wins by default, while `GENERAL_PURPOSE + FULL` may displace `SPECIALIZED + PARTIAL_LOCAL_REFINEMENT` only with an explicit evidence-backed waiver. Scratch remains the last fallback.
Examples of built-in discovery hints include:

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

The goal is not to ban custom modeling. It is to make custom modeling the **intentional fallback**, not the agent's first reflex.

## Quickstart with Codex

### 1. Install BlendSmith from source

```bash
git clone https://github.com/Soph1yzzz/blendsmith.git
cd blendsmith
python -m pip install .
```

Python **3.11+** is required. Blender **5.2 LTS** is the primary runtime target.

### 2. Install the bundled Codex Skill

```bash
blendsmith skill-install
blendsmith doctor
```

`blendsmith doctor` fails closed unless the installed Skill matches the Skill bundled with the currently installed CLI/Core package.

Restart Codex after a fresh Skill install or update.

### 3. Ask Codex to use it

```text
BlendSmithを使って、この参考画像からBlenderで作って。
```

or:

```text
Use BlendSmith to build this in Blender.
```

The Skill is intentionally thin. It does not duplicate BlendSmith's lifecycle in prompt text; it queries the installed CLI/Core through `doctor`, `status`, command help, and authoritative JSON schemas. The Core remains the source of truth for every loop transition.

## What happens after invocation?

A typical production loop looks like this:

```text
preflight
  -> Domain Research Gate
       -> optional Domain Knowledge cache lookup / fresh research
       -> Domain Practice
  -> Method Plan / Production Graph + domain_constraints
  -> method-family accounting
  -> Method Selection
  -> Blender production
  -> candidate pin
  -> multi-view evidence
  -> visual review
       -> Change Impact Gate
            -> LOCAL      -> method continuity -> fix plan -> production
            -> METHOD     -> method selection
            -> STRUCTURAL -> upstream graph/plan revision
            -> CONTRACT   -> upstream contract/plan revision
       -> render accepted
            -> exploratory live GUI review
                 -> REVISE -> Change Impact Gate
                 -> PASS
  -> final AI validation
  -> AI_ACCEPTED
  -> OWNER_REVIEW
```

Repeated LOCAL repair can be interrupted by **Global Reassessment** before another patch is authorized.

At `OWNER_REVIEW`, automatic progress stops.

Human acceptance is bound to the exact candidate SHA-256 that was reviewed. BlendSmith does not infer approval from silence, an AI verdict, or a previous version of the file.

## Checkpoint and resume

Long-running Blender work should not depend on the model remembering the previous chat perfectly. BlendSmith checkpoints preserve the authority needed to resume the control loop safely: validated Domain Research / Knowledge / Practice receipts when present, method receipts, selection round, candidate closure, and integrity bindings.

A resume revalidates those bindings instead of turning stale conversational memory into authority.

## Use the Core directly

BlendSmith is not Codex-only. The CLI/Core is the authority; the Codex Skill is one adapter.

```bash
blendsmith --version
blendsmith doctor
blendsmith init <project>
blendsmith preflight --project <project>
blendsmith start --project <project>
blendsmith status --project <project>
```

Authoritative contracts can be inspected directly:

```bash
blendsmith schema domain_research
blendsmith schema domain_knowledge
blendsmith schema domain_practice
blendsmith schema method_plan
blendsmith schema method_selection
blendsmith schema visual_review
```

Useful lifecycle commands include:

```bash
blendsmith next --project <project>
blendsmith domain-research --project <project> --input domain_research.json
blendsmith knowledge-cache --project <project>
blendsmith knowledge-cache-use --project <project>
blendsmith domain-knowledge --project <project> --input domain_knowledge.json
blendsmith domain-practice --project <project> --input domain_practice.json
blendsmith method-hints --project <project> --intent symmetry
blendsmith method-cache --project <project> --intent symmetry
blendsmith method-plan --project <project> --input method_plan.json
blendsmith method-select --project <project> --input method_selection.json
blendsmith candidate-add --project <project> --candidate <scene.blend>
blendsmith evidence-begin --project <project>
blendsmith evidence-submit --project <project> --view front=<front.png>
blendsmith visual-review --project <project> --input visual_review.json
blendsmith change-impact --project <project> --input change_impact.json
blendsmith global-reassess --project <project> --input global_reassessment.json
blendsmith gui-review --project <project> --input live_gui_review.json
blendsmith owner-action-recover --project <project>
blendsmith ai-accept --project <project>
blendsmith owner-accept --project <project> --sha256 <candidate_sha256>
blendsmith checkpoint --project <project>
blendsmith resume --project <project>
blendsmith publish --project <project>
blendsmith gc --project <project>
```

The CLI rejects unauthorized transitions instead of relying on the agent to remember the rules.

## Core guarantees

- **Loop authority lives in Core.** The agent proposes actions; the deterministic Core validates state transitions.
- **Domain assumptions are explicit.** Function, dimensions, structure, process, safety, standards, and specialist practice are accounted for before planning; `NOT_REQUIRED` is fail-closed.
- **Knowledge becomes authority through contracts, not prose.** Research findings are SHA-bound, actionable findings must become practice rules or be explicitly ignored, and work-unit constraints preserve the rule requirement, confidence, and verification.
- **Knowledge cache is bounded.** Reuse restores facts only; current-run Domain Practice is rebuilt, and explicit upstream reconsideration requires fresh knowledge.
- **Decomposition is explicit.** Every known method family is accounted for before a work unit can enter Method Selection.
- **Production structure is explicit.** Work units carry rationale, stage, and dependency edges; upstream revision can invalidate downstream work.
- **Specialized first, scratch last.** Viable dedicated methods take precedence over generic construction, with a narrow evidence-backed waiver for full-fit general methods over partial specialized ones.
- **Method continuity survives repair.** LOCAL fixes must preserve the methods already authorized for the affected work units.
- **Change depth is classified before editing.** LOCAL, METHOD, STRUCTURAL, and CONTRACT changes return to different levels of the loop.
- **Patch stacking is bounded by a global view.** Repeated local repair can force reassessment of the whole production context.
- **Exact method authority.** Candidate manifests bind the exact Method Selection SHA, which binds the exact Method Plan SHA.
- **Validated receipts are immutable.** Upstream revisions supersede prior SHA-bound plans instead of rewriting them in place.
- **Evidence is real input to review.** Visual acceptance requires opened evidence; file existence alone is not visual review.
- **Live GUI review is exploratory.** `PASS` requires orbit, zoom, an unseen viewpoint, concrete observations, and multiple coverage categories; meaningful quality-gain issues cannot be ignored.
- **Recovery needs fresh evidence.** A GUI owner-action can resume the same run only after a newer explicit capability reprobe.
- **Discovery cache is bounded.** Cached facts are evidence only, and sources without a provable freshness boundary must be checked again.
- **Human authority is explicit and SHA-bound.** Only the owner can accept the exact reviewed candidate.
- **Retries are bounded.** Retry-safe operations get an initial attempt plus at most three retries; unsafe ambiguity escalates.
- **Checkpoints preserve authority.** Domain Research / Knowledge / Practice, Method receipts, and candidate closure are pinned and revalidated on resume.
- **GC is constrained.** Cleanup is limited to verified expired records inside managed storage.
- **Contracts are model-neutral.** BlendSmith validates information and state, not a model-specific reasoning format.

## Project layout

```text
<project>/
├─ blendsmith.project.json
├─ .blendsmith/
│  ├─ install/
│  ├─ capabilities/
│  ├─ runs/
│  └─ history/
└─ publication/
   └─ current/
```

`.blendsmith/` is operational state and should normally remain outside source control. `publication/current/` is the verified current local publication managed by BlendSmith.

## Documentation

- [Specification](docs/SPECIFICATION.md)
- [Method Selection Gate](docs/METHOD_SELECTION.md)
- [Security model](docs/SECURITY.md)
- [Contracts](docs/CONTRACTS.md)
- [Roadmap](docs/ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## Development

```bash
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m pytest -q
```

CI covers Python 3.11 / 3.12 on Windows and Ubuntu.

## Status

**v0.0.3 — Domain Knowledge** is the current release.

It adds a knowledge layer before Production Structure: Domain Research decides whether specialist knowledge is required, Domain Knowledge records source-backed findings and confidence, Domain Practice turns actionable findings into production rules, and Method Plan binds them into work-unit constraints. If a later STRUCTURAL or CONTRACT failure reveals that the assumption itself may be wrong, the loop can return all the way to fresh Domain Research instead of patching around stale knowledge.

**v0.0.2 — Production Structure** remains available as the release that introduced decomposition, Production Graph, Change Impact, Method Continuity, Global Reassessment, exploratory GUI review, and bounded method discovery caching. **v0.0.1** remains the first public release.

## License

Apache License 2.0. See [LICENSE](LICENSE).
