# BlendSmith Security Model

BlendSmith manages local Blender artifacts, lifecycle state, evidence, and publication pointers. Its safety model is intentionally conservative around filesystem boundaries, artifact identity, and owner authority.

## Trust boundary

BlendSmith is designed to protect against accidental corruption, stale state, unsafe path handling, malformed external contracts, and unsafe automatic retries. It does not provide cryptographic protection against a malicious local user who already has arbitrary write access to the BlendSmith project and can rewrite every state file.

## Filesystem safety

- Managed paths are checked to remain inside the intended BlendSmith storage root.
- Symlinks, Windows junctions, and other reparse points are rejected in managed storage operations.
- Candidate and checkpoint closures are copied from explicit manifests rather than recursively trusting unrelated files.
- GC only considers expired ephemeral records whose current digest still matches the recorded digest.
- Pinned paths block overlapping GC targets.
- Publication uses a staging directory, verifies every copied digest, and only then swaps the verified directory into `publication/current`.

## Artifact identity

Human acceptance is bound to the exact reviewed candidate SHA-256. A changed candidate, changed dependency closure, or mismatched publication copy blocks acceptance/publication rather than silently updating the accepted artifact.

Method decisions are also integrity-bound: a method-selection receipt names the SHA-256 of its work plan, and each ingested candidate manifest names the SHA-256 of the exact method-selection receipt that governed its production. Changing either receipt after candidate ingest blocks later evidence/acceptance gates.

Candidate metadata, method contracts, checkpoint metadata, retention records, and publication manifests are validated before use. State paths derived from persisted metadata are checked against their expected managed locations before file access.

## Method-selection safety

Configured discovery sources must be accounted for before production begins. A required discovery source left `BROKEN`/`UNKNOWN`, or a relevant specialized method left `UNKNOWN`, blocks method selection rather than silently authorizing a general-purpose/scratch fallback.

External agents provide probe evidence through structured contracts; BlendSmith validates the policy and identity bindings but cannot cryptographically prove that a remote/model-produced observation was truthful. Hosts should use real Blender/tool inspection for discovery evidence rather than model memory alone.

## Capability safety

`AVAILABLE`, `UNAVAILABLE`, `BROKEN`, and `UNKNOWN` have distinct meanings. `BROKEN` and `UNKNOWN` cannot be treated as `UNAVAILABLE` to bypass required GUI review.

Capability snapshots are validated contracts. Blender runtime probing is bounded to one initial attempt plus at most three retries when the probe is broken. Host-provided capability observations should come from a trusted host/owner integration; autonomous agents should not fabricate capability states to bypass QA.

## Retry safety

BlendSmith only retries operations classified as retry-safe. Probe operations may use the bounded retry helper. Mutating MCP/tool operations are not blindly repeated because idempotency cannot be assumed.

Safety, authority, integrity, path-boundary, destructive-overwrite, and unknown-owner-state failures are not converted into retryable transport failures.

## MCP boundary

BlendSmith does not embed a general MCP client SDK. Host integrations inject a transport and an explicit allowlist of tool names. Calls outside that allowlist are rejected. Safety failures are propagated rather than downgraded to transient capability failures.

## Configured Blender executable

A configured Blender executable is executed with `--version` during probing using `shell=False`. Only configure a Blender binary you trust. BlendSmith does not attempt to establish publisher authenticity for arbitrary executables supplied by the local user.

## Codex Skill installation

The bundled Codex Skill is installed only to the fixed user Skill location under `CODEX_HOME` (when configured) or `~/.codex/skills/blendsmith/SKILL.md`. BlendSmith does not expose an arbitrary destination argument. Existing modified files are not overwritten unless `--force` is explicit. The destination and its existing parent path components are checked for symlinks, Windows junctions, and other reparse points before writing, and the installed bytes are verified against the bundled SHA-256.

`blendsmith doctor` fails closed unless the installed Skill bytes exactly match the Skill bundled with the currently installed CLI/Core package. This prevents a current CLI from being driven by a stale or locally modified operating Skill. The CLI cannot prove that Codex has reloaded newly written Skill bytes, so a fresh Skill install/update still requires a Codex restart. The Skill remains an operating adapter; it cannot override Core authority checks.

## Concurrent writers

BlendSmith uses atomic JSON replacement for authoritative JSON state, but v0.0.1 is designed for a single active writer per project. A hostile process that can continuously mutate files between verification and filesystem operations is outside the protection boundary. Run one BlendSmith orchestrator per project at a time.

## Reporting security issues

When publishing this repository, add the project-specific private security reporting channel or GitHub Security Advisory instructions appropriate for the repository owner.
