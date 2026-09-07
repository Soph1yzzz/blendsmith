<p align="center">
  <img src="docs/assets/blendsmith-readme-hero.png" alt="BlendSmith — a production loop harness for AI-assisted Blender" width="100%">
</p>

<h1 align="center">BlendSmith</h1>

<p align="center"><strong>A production loop harness for AI-assisted Blender.</strong></p>
<p align="center">Choose better methods. Inspect real evidence. Repair deliberately. Stop at human approval.</p>

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

BlendSmith is a **model-independent loop harness for Blender agents**. It does not replace the model, Blender, MCP, `bpy`, or GUI automation. It wraps them in a production loop that manages **method planning, method selection, candidate evidence, visual review, repair or method reselection, checkpointing, exact human approval, retention, and verified publication**.

The point is not to make an incapable model look capable. The point is to make capable models operate inside a repeatable control loop instead of treating each Blender task as a one-shot improvisation.

> With the arrival of **GPT-6 Astra**, modern models can already build impressive 3D assets. BlendSmith exists because **being able to build something is not the same as consistently choosing the right Blender method, inspecting the result, recovering safely, iterating deliberately, and handing an exact reviewed artifact to a human.**

## What can this workflow produce?

The private Blender harness that evolved into BlendSmith was already producing work like this with **GPT-5.6 Sol High**.

<p align="center">
  <img src="assets/examples/gothic-interior.png" alt="AI-assisted Gothic interior created in Blender" width="100%">
</p>

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

BlendSmith is the public, model-neutral harness distilled from that production workflow. Output quality still depends on the model, references, available Blender capabilities, and iteration. BlendSmith governs the **loop around production** rather than pretending to be the artist itself.

### Current-generation dogfood

A light internal dogfood run with **GPT-6 Astra** on an ornate sword task also found the harness useful. The model could already produce the asset and revise an earlier candidate on its own, while BlendSmith still added useful production discipline through method discovery, exact candidate pinning, six-view evidence, live-GUI verification, and a hard stop at `OWNER_REVIEW`.

<p align="center">
  <img src="docs/assets/blendsmith-astra-dogfood.png" alt="BlendSmith GPT-6 Astra dogfood proof panel" width="100%">
</p>

## The production loop

Open-ended AI 3D work becomes more reliable when creation, inspection, correction, and authority are part of the same explicit loop.

<p align="center">
  <img src="docs/assets/blendsmith-control-loop.png" alt="BlendSmith production control loop" width="100%">
</p>

A review does not merely answer “good or bad.” It decides what kind of next move is justified:

- **Local repair** — the method is sound; fix a bounded defect and re-enter production.
- **Method reselection** — the approach itself is wrong; return to method selection instead of hand-patching forever.
- **AI acceptance** — machine-side gates passed; advance to the human authority boundary.

That review-and-repair loop ends deliberately at:

```text
AI_ACCEPTED != HUMAN_ACCEPTED
```

The agent can propose progress. BlendSmith Core decides whether that progress is valid. The owner decides whether the exact reviewed artifact is accepted.

## Why BlendSmith?

| Common agent failure | BlendSmith response |
| --- | --- |
| The model knows a Blender feature exists, but forgets to use it | **Method Selection Gate** — specialized methods are evaluated before production |
| A candidate exists, so the agent declares success | **Evidence-backed review** — actual views must be opened and evaluated |
| Endless hand-tweaking after choosing the wrong approach | **Method reconsideration** — loop back to method selection instead of patching forever |
| The agent says “looks good” | **AI acceptance is separate from human acceptance** |
| A file changes after review | **SHA-bound authority** — approval names the exact reviewed bytes |
| GUI capability breaks | **No silent downgrade** — `BROKEN` / `UNKNOWN` cannot be disguised as `UNAVAILABLE` |
| A long run is interrupted | **Checkpoint / resume** — restore validated loop authority rather than improvising from memory |
| Old heavy artifacts accumulate forever | **TTL + verified GC** — only eligible managed data can be cleaned up |

BlendSmith does not promise that every loop ends in success. It makes the outcome explicit: continue through a valid repair/reselection path, escalate an unresolved condition, or stop at the owner boundary with inspectable evidence.

## Specialized first, scratch last

Knowing that Blender has `Mirror`, `Array`, Geometry Nodes, asset libraries, extensions, or reusable node tools is not the same as selecting them at the right time.

The production loop therefore starts with method discipline rather than immediate construction.

<p align="center">
  <img src="docs/assets/blendsmith-method-selection.png" alt="BlendSmith specialized-first method selection" width="100%">
</p>

Before production, BlendSmith requires work-unit planning and a machine-validated method-selection receipt. The default discovery policy accounts for:

- Blender native functionality
- Geometry Node tools
- asset libraries
- installed extensions
- project-local catalogs
- configured adapters

Known method hints must be explicitly accounted for. A relevant specialized method left `UNKNOWN`, or a required discovery source left `BROKEN` / `UNKNOWN`, blocks fallback instead of silently authorizing scratch construction.

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
  -> method plan
  -> method selection
  -> Blender production
  -> candidate pin
  -> multi-view evidence
  -> visual review
       -> local repair -> production, or
       -> method reconsideration -> method selection
  -> live GUI review when available
  -> AI_ACCEPTED
  -> OWNER_REVIEW
```

At `OWNER_REVIEW`, automatic progress stops.

Human acceptance is bound to the exact candidate SHA-256 that was reviewed. BlendSmith does not infer approval from silence, an AI verdict, or a previous version of the file.

## Checkpoint and resume

Long-running Blender work should not depend on the model remembering the previous chat perfectly. BlendSmith checkpoints preserve the authority needed to resume the control loop safely: validated method receipts, selection round, candidate closure, and integrity bindings.

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
blendsmith schema method_plan
blendsmith schema method_selection
blendsmith schema visual_review
```

Useful lifecycle commands include:

```bash
blendsmith method-hints --project <project> --intent symmetry
blendsmith method-plan --project <project> --input method_plan.json
blendsmith method-select --project <project> --input method_selection.json
blendsmith candidate-add --project <project> --candidate <scene.blend>
blendsmith evidence-begin --project <project>
blendsmith evidence-submit --project <project> --view front=<front.png>
blendsmith visual-review --project <project> --input visual_review.json
blendsmith gui-review --project <project> --input live_gui_review.json
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
- **Specialized first, scratch last.** Viable dedicated methods take precedence over generic construction.
- **Exact method authority.** Candidate manifests bind the exact Method Selection SHA, which binds the exact Method Plan SHA.
- **Validated receipts are immutable.** Editing an accepted plan or selection behind the lifecycle causes an integrity failure.
- **Evidence is real input to review.** Visual acceptance requires opened evidence; file existence alone is not visual review.
- **Repair and reselection are different loop paths.** A local defect does not automatically justify keeping a bad production method.
- **Live GUI verification is concrete.** A GUI `PASS` requires path, dirty-state, interaction, and observed-view evidence.
- **Human authority is explicit and SHA-bound.** Only the owner can accept the exact reviewed candidate.
- **Retries are bounded.** Retry-safe operations get an initial attempt plus at most three retries; unsafe ambiguity escalates.
- **Checkpoints preserve authority.** Method receipts and candidate closure are pinned and revalidated on resume.
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

**v0.0.1** is the first public release. It includes the model-neutral Core/CLI, production-loop state machine, Method Selection Gate, evidence and visual-review contracts, bounded repair, method reconsideration, live-GUI verification, owner authority, checkpoint/resume, retention/GC, verified local publication, and the bundled Codex Skill.

Next: **v0.0.2 — Production Structure**, focused on decomposition, dependency-aware production graphs, construction sequence, structural integrity, safer recovery, and agent-facing introspection. See the [roadmap](docs/ROADMAP.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
