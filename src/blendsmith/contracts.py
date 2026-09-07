from __future__ import annotations

from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .errors import ContractError
from .timeutil import parse_iso

SCHEMA_FILES = {
    "project": "project.schema.json",
    "run": "run.schema.json",
    "state_event": "state_event.schema.json",
    "capability_report": "capability_report.schema.json",
    "method_plan": "method_plan.schema.json",
    "method_selection": "method_selection.schema.json",
    "visual_review": "visual_review.schema.json",
    "fix_plan": "fix_plan.schema.json",
    "live_gui_review": "live_gui_review.schema.json",
    "owner_decision": "owner_decision.schema.json",
    "owner_action_required": "owner_action_required.schema.json",
    "retention_record": "retention_record.schema.json",
    "candidate_manifest": "candidate_manifest.schema.json",
    "checkpoint": "checkpoint.schema.json",
    "provenance": "provenance.schema.json",
    "publication_manifest": "publication_manifest.schema.json",
}


def load_schema(name: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILES[name]
    except KeyError as exc:
        raise ContractError(f"Unknown contract: {name}") from exc
    package = resources.files("blendsmith.schemas")
    return __import__("json").loads((package / filename).read_text(encoding="utf-8"))


def validate_contract(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    schema = load_schema(name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"/{'/'.join(str(p) for p in error.path)}: {error.message}" for error in errors[:8]
        )
        raise ContractError(f"{name} contract invalid: {details}")
    _runtime_invariants(name, payload)
    return payload


def _runtime_invariants(name: str, payload: dict[str, Any]) -> None:
    _validate_timestamps(name, payload)

    if name == "visual_review" and payload["verdict"] == "ACCEPT":
        if not payload.get("opened_evidence"):
            raise ContractError("Visual ACCEPT requires opened evidence")
        blockers = [
            issue
            for issue in payload.get("issues", [])
            if issue.get("severity") in {"critical", "high"}
        ]
        if blockers:
            raise ContractError("Visual ACCEPT cannot contain critical/high issues")
        major_regressions = [
            item for item in payload.get("regressions", []) if item.get("severity") == "major"
        ]
        if major_regressions:
            raise ContractError("Visual ACCEPT cannot contain a major regression")

    if name == "fix_plan":
        primary = payload.get("primary_issue_ids", [])
        if len(primary) > 2:
            raise ContractError("A fix plan may address at most two primary issues")

    if name == "live_gui_review" and payload["status"] == "PASS":
        required_true = (
            "blend_path_verified",
            "dirty_state_checked",
            "viewport_interaction_performed",
        )
        if not all(payload.get(field) is True for field in required_true):
            raise ContractError("GUI PASS requires path, dirty-state, and viewport checks")
        if not payload.get("views_observed"):
            raise ContractError("GUI PASS requires at least one observed view")
        if any(issue.get("blocking", False) for issue in payload.get("issues", [])):
            raise ContractError("GUI PASS cannot contain a blocking issue")

    if (
        name == "live_gui_review"
        and payload["status"] == "SKIPPED_UNAVAILABLE"
        and payload.get("capability_status") != "UNAVAILABLE"
    ):
        raise ContractError("GUI skip is valid only when capability is UNAVAILABLE")

    if name == "checkpoint":
        candidate_fields = (
            payload.get("candidate_id"),
            payload.get("candidate_sha256"),
            payload.get("closure_sha256"),
            payload.get("candidate_manifest_path"),
        )
        if any(value is None for value in candidate_fields) and any(
            value is not None for value in candidate_fields
        ):
            raise ContractError("Checkpoint candidate identity must be fully present or fully absent")
        method_plan_fields = (
            payload.get("method_plan_snapshot_path"),
            payload.get("method_plan_sha256"),
        )
        if any(value is None for value in method_plan_fields) and any(
            value is not None for value in method_plan_fields
        ):
            raise ContractError("Checkpoint method-plan identity must be fully present or fully absent")
        method_selection_fields = (
            payload.get("method_selection_snapshot_path"),
            payload.get("method_selection_sha256"),
        )
        if any(value is None for value in method_selection_fields) and any(
            value is not None for value in method_selection_fields
        ):
            raise ContractError(
                "Checkpoint method-selection identity must be fully present or fully absent"
            )
        if payload.get("method_selection_snapshot_path") is not None and payload.get(
            "method_plan_snapshot_path"
        ) is None:
            raise ContractError("Checkpoint method selection requires a method-plan snapshot")
        if payload.get("candidate_manifest_path") is not None and payload.get(
            "method_selection_snapshot_path"
        ) is None:
            raise ContractError("Checkpoint candidate requires a method-selection snapshot")

    if name == "retention_record":
        cls = payload["class"]
        pinned = cls.startswith("PINNED_") or cls == "LIGHTWEIGHT_HISTORY"
        ephemeral = cls in {"EPHEMERAL", "EPHEMERAL_SUPERSEDED_FINAL"}
        if pinned and payload["gc_allowed"]:
            raise ContractError("Pinned/history records cannot be GC-allowed")
        if ephemeral and not payload.get("expires_at"):
            raise ContractError("Ephemeral records require expires_at")
        if ephemeral and not payload.get("sha256"):
            raise ContractError("Ephemeral records require a recorded digest")


def _validate_timestamps(name: str, payload: dict[str, Any]) -> None:
    fields_by_contract = {
        "run": ("created_at", "updated_at"),
        "state_event": ("occurred_at",),
        "capability_report": ("captured_at",),
        "candidate_manifest": ("created_at",),
        "checkpoint": ("created_at",),
        "owner_decision": ("decided_at",),
        "retention_record": ("created_at", "expires_at"),
        "publication_manifest": ("published_at",),
    }
    for field in fields_by_contract.get(name, ()):
        value = payload.get(field)
        if value is None:
            continue
        try:
            parse_iso(value)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"{name} field {field} must be an ISO timestamp with timezone") from exc

    if name == "capability_report":
        for capability_name, capability in payload.get("capabilities", {}).items():
            value = capability.get("observed_at")
            if value is None:
                continue
            try:
                parse_iso(value)
            except (TypeError, ValueError) as exc:
                raise ContractError(
                    f"capability_report observed_at is invalid for {capability_name}"
                ) from exc
