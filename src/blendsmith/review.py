from __future__ import annotations

from typing import Any

from .closure import verify_candidate_manifest
from .contracts import validate_contract
from .errors import ContractError, IntegrityError


def _assert_identity(payload: dict[str, Any], run: dict[str, Any], manifest: dict[str, Any]) -> None:
    if payload["run_id"] != run["run_id"]:
        raise ContractError("Contract run_id does not match active run")
    if payload["candidate_id"] != manifest["candidate_id"]:
        raise ContractError("Contract candidate_id does not match active candidate")
    if payload["candidate_sha256"] != manifest["candidate_sha256"]:
        raise IntegrityError("Contract SHA does not match active candidate")


def validate_visual_review(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    manifest_path,
    project_config: dict[str, Any],
) -> dict[str, Any]:
    validate_contract("visual_review", payload)
    manifest = verify_candidate_manifest(manifest_path)
    _assert_identity(payload, run, manifest)

    if payload["verdict"] == "ACCEPT":
        opened = set(payload["opened_evidence"])
        required_evidence = set(project_config["qa"].get("required_evidence", []))
        missing_evidence = sorted(required_evidence - opened)
        if missing_evidence:
            raise ContractError(f"Required evidence was not opened: {missing_evidence}")
        completed = set(payload.get("perspectives_completed", []))
        required_perspectives = set(project_config["qa"].get("required_perspectives", []))
        missing_perspectives = sorted(required_perspectives - completed)
        if missing_perspectives:
            raise ContractError(f"Required review perspectives missing: {missing_perspectives}")
    return payload


def validate_fix_plan(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    manifest_path,
    visual_review: dict[str, Any],
) -> dict[str, Any]:
    validate_contract("fix_plan", payload)
    manifest = verify_candidate_manifest(manifest_path)
    _assert_identity(payload, run, manifest)
    known_issue_ids = {item["issue_id"] for item in visual_review.get("issues", [])}
    unknown = set(payload["primary_issue_ids"]) - known_issue_ids
    if unknown:
        raise ContractError(f"Fix plan references unknown issues: {sorted(unknown)}")
    return payload


def validate_live_gui_review(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    manifest_path,
    current_capability_status: str,
) -> dict[str, Any]:
    validate_contract("live_gui_review", payload)
    manifest = verify_candidate_manifest(manifest_path)
    _assert_identity(payload, run, manifest)
    if payload["capability_status"] != current_capability_status:
        raise ContractError("GUI review capability status is stale")
    if current_capability_status in {"BROKEN", "UNKNOWN"} and payload["status"] == "SKIPPED_UNAVAILABLE":
        raise ContractError("BROKEN/UNKNOWN GUI capability cannot be skipped as unavailable")
    return payload
