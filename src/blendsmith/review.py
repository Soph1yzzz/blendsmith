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


def validate_change_impact(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    manifest_path,
    method_plan: dict[str, Any],
    method_selection: dict[str, Any],
    source_review: dict[str, Any] | None,
) -> dict[str, Any]:
    validate_contract("change_impact", payload)
    manifest = verify_candidate_manifest(manifest_path)
    _assert_identity(payload, run, manifest)

    work_units = {item["work_unit_id"] for item in method_plan["work_units"]}
    unknown_units = sorted(set(payload["affected_work_units"]) - work_units)
    if unknown_units:
        raise ContractError(f"Change impact references unknown work units: {unknown_units}")

    if source_review is not None:
        known_issue_ids = {item["issue_id"] for item in source_review.get("issues", [])}
        unknown_issues = sorted(set(payload["issue_ids"]) - known_issue_ids)
        if unknown_issues:
            raise ContractError(f"Change impact references unknown review issues: {unknown_issues}")
    elif payload["source"] == "OWNER_REVISION":
        expected_owner_issue = run["metadata"].get("pending_owner_revision_issue_id")
        if not expected_owner_issue or payload["issue_ids"] != [expected_owner_issue]:
            raise ContractError("Owner revision change impact must reference the pending owner revision issue")

    selected_by_unit: dict[str, set[str]] = {}
    for selection in method_selection["selections"]:
        selected_by_unit.setdefault(selection["work_unit_id"], set()).add(selection["selected_method_id"])
    expected_methods: set[str] = set()
    for work_unit_id in payload["affected_work_units"]:
        expected_methods.update(selected_by_unit.get(work_unit_id, set()))

    continuity = payload["method_continuity"]
    continuity_methods = set(continuity["selected_method_ids"])
    if payload["scope"] == "LOCAL":
        if continuity["status"] != "PRESERVE":
            raise ContractError("LOCAL change impact must preserve the validated method selection")
        if not expected_methods:
            raise ContractError("LOCAL change impact could not resolve selected methods for affected work units")
        if continuity_methods != expected_methods:
            raise ContractError(
                "LOCAL change impact must preserve all selected methods for the affected work units; "
                f"expected={sorted(expected_methods)}, got={sorted(continuity_methods)}"
            )
    elif payload["scope"] == "METHOD" and continuity["status"] != "RESELECT":
        raise ContractError("METHOD change impact must explicitly require method reselection")
    return payload


def validate_global_reassessment(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    manifest_path,
    method_plan: dict[str, Any],
) -> dict[str, Any]:
    validate_contract("global_reassessment", payload)
    manifest = verify_candidate_manifest(manifest_path)
    _assert_identity(payload, run, manifest)
    unit_ids = {item["work_unit_id"] for item in method_plan["work_units"]}
    unknown = sorted(set(payload.get("affected_work_units", [])) - unit_ids)
    if unknown:
        raise ContractError(f"Global reassessment references unknown work units: {unknown}")
    return payload


def validate_fix_plan(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    manifest_path,
    source_review: dict[str, Any] | None,
    change_impact: dict[str, Any],
) -> dict[str, Any]:
    validate_contract("fix_plan", payload)
    manifest = verify_candidate_manifest(manifest_path)
    _assert_identity(payload, run, manifest)

    known_issue_ids = set(change_impact.get("issue_ids", []))
    if source_review is not None:
        known_issue_ids.update(item["issue_id"] for item in source_review.get("issues", []))
    unknown = set(payload["primary_issue_ids"]) - known_issue_ids
    if unknown:
        raise ContractError(f"Fix plan references unknown issues: {sorted(unknown)}")

    expected_methods = set(change_impact["method_continuity"]["selected_method_ids"])
    if set(payload["method_ids_to_preserve"]) != expected_methods:
        raise ContractError(
            "Fix plan must preserve the methods authorized by the LOCAL change-impact decision"
        )
    return payload


def validate_live_gui_review(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    manifest_path,
    current_capability_status: str,
    project_config: dict[str, Any],
) -> dict[str, Any]:
    validate_contract("live_gui_review", payload)
    manifest = verify_candidate_manifest(manifest_path)
    _assert_identity(payload, run, manifest)
    if payload["capability_status"] != current_capability_status:
        raise ContractError("GUI review capability status is stale")
    if current_capability_status in {"BROKEN", "UNKNOWN"} and payload["status"] == "SKIPPED_UNAVAILABLE":
        raise ContractError("BROKEN/UNKNOWN GUI capability cannot be skipped as unavailable")
    meaningful_quality_gains = [
        issue
        for issue in payload.get("issues", [])
        if issue.get("quality_gain") in {"MEDIUM", "HIGH"}
    ]
    max_quality_gains = int(
        project_config.get("production_structure", {}).get("max_gui_quality_gain_issues", 2)
    )
    if len(meaningful_quality_gains) > max_quality_gains:
        raise ContractError(
            "GUI review exceeded the bounded quality-gain issue budget: "
            f"max {max_quality_gains}"
        )
    return payload
