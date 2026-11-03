"""Reference-target and candidate-quality contracts for the v1.1.0 production loop.

The Core checks identities, coverage and objective structural probes. Visual
judgements remain external observations, never a computed quality guarantee.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import validate_contract
from .errors import ContractError, IntegrityError
from .hashing import sha256_file
from .paths import atomic_write_json, ensure_within


def validate_targets(payload: dict[str, Any], references: list[dict[str, Any]]) -> dict[str, Any]:
    validate_contract("quality_targets", payload)
    by_ref = {item["reference_id"]: item for item in references}
    if not by_ref:
        raise ContractError("Reference feature targets require registered reference images")
    seen: set[str] = set()
    covered: set[str] = set()
    for target in payload["targets"]:
        target_id = target["target_id"]
        if target_id in seen:
            raise ContractError(f"Duplicate reference feature target: {target_id}")
        seen.add(target_id)
        reference = by_ref.get(target["reference_id"])
        if reference is None or target["reference_sha256"] != reference["sha256"]:
            raise IntegrityError(f"Unknown or stale reference for target: {target_id}")
        covered.add(target["reference_id"])
    if covered != set(by_ref):
        raise ContractError(f"Missing feature targets for references: {sorted(set(by_ref) - covered)}")
    ids: set[str] = set()
    for check in payload["geometry_checks"]:
        if check["check_id"] in ids:
            raise ContractError(f"Duplicate geometry check: {check['check_id']}")
        ids.add(check["check_id"])
        if set(check["source_objects"]) & set(check["target_objects"]):
            raise ContractError("Contact check source and target object names must be distinct")
    return payload


def store_targets(run_dir: Path, payload: dict[str, Any], references: list[dict[str, Any]]) -> str:
    validate_targets(payload, references)
    path = ensure_within(run_dir, run_dir / "references" / "quality_targets.json")
    if path.exists():
        raise ContractError("Reference targets are immutable after first registration")
    atomic_write_json(path, payload)
    return sha256_file(path)


def verified_targets(
    run_dir: Path,
    expected_sha256: str | None,
    references: list[dict[str, Any]],
) -> dict[str, Any] | None:
    path = ensure_within(run_dir, run_dir / "references" / "quality_targets.json")
    if expected_sha256 is None:
        if path.exists():
            raise IntegrityError("Quality target receipt exists without run authority")
        return None
    if not path.is_file() or path.is_symlink() or sha256_file(path) != expected_sha256:
        raise IntegrityError("Quality target receipt is missing, unsafe or modified")
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_targets(payload, references)
    return payload


def validate_assessment(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    candidate: dict[str, Any],
    targets: dict[str, Any],
    targets_sha256: str,
    evidence_views: set[str],
    best_sha256: str | None,
) -> dict[str, Any]:
    validate_contract("quality_assessment", payload)
    if payload["run_id"] != run["run_id"] or payload["candidate_id"] != candidate["candidate_id"]:
        raise ContractError("Quality assessment is bound to another run or candidate")
    if payload["candidate_sha256"] != candidate["candidate_sha256"]:
        raise IntegrityError("Quality assessment uses a stale candidate SHA")
    if payload["targets_sha256"] != targets_sha256:
        raise IntegrityError("Quality assessment uses a stale reference-target SHA")
    if payload["compared_to_sha256"] != best_sha256:
        raise IntegrityError("Quality comparison does not cite the current best candidate SHA")

    opened = set(payload["opened_evidence"])
    if not opened.issubset(evidence_views):
        raise ContractError(f"Quality assessment cites unknown rendered views: {sorted(opened - evidence_views)}")
    by_target = {item["target_id"]: item for item in targets["targets"]}
    submitted = payload["target_results"]
    if len(submitted) != len(by_target) or {item["target_id"] for item in submitted} != set(by_target):
        raise ContractError("Quality assessment must inspect every registered feature target exactly once")
    if len({item["target_id"] for item in submitted}) != len(submitted):
        raise ContractError("Duplicate target in quality assessment")
    for item in submitted:
        target = by_target[item["target_id"]]
        if not set(target["view_keys"]).issubset(set(item["view_keys"])):
            raise ContractError(f"Missing required views for feature target: {item['target_id']}")
        if not set(item["view_keys"]).issubset(opened):
            raise ContractError(f"Feature target cites an unopened rendered view: {item['target_id']}")
        if best_sha256 is None and item["delta"] != "BASELINE":
            raise ContractError("First candidate must be marked BASELINE against no best candidate")
        if best_sha256 is not None and item["delta"] == "BASELINE":
            raise ContractError("Later candidates must compare every feature against the best candidate")

    if payload["decision"] == "PROMOTE":
        if payload["creator_context_id"] == payload["reviewer_context_id"]:
            raise ContractError("Promoting a quality candidate requires a separate evaluator context")
        if best_sha256 is not None:
            deltas = {item["delta"] for item in submitted}
            if deltas & {"REGRESSED", "INCOMPARABLE"}:
                raise ContractError("A worse or incomparable feature cannot be promoted over the best candidate")
            if "IMPROVED" not in deltas and candidate["candidate_sha256"] != best_sha256:
                raise ContractError("A new best candidate must improve at least one recorded feature")
    return payload
