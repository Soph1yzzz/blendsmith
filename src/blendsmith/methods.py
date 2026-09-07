from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .contracts import validate_contract
from .errors import ContractError

VIABLE_FITS = {"FULL", "PARTIAL_LOCAL_REFINEMENT"}
SETTLED_DISCOVERY = {"CHECKED", "UNAVAILABLE"}


def load_method_hints(intent: str | None = None) -> dict[str, Any]:
    package = resources.files("blendsmith.profiles")
    payload = json.loads((package / "method_catalog.default.json").read_text(encoding="utf-8"))
    if intent is None:
        return payload
    needle = intent.casefold().strip()
    families = [item for item in payload["families"] if item["intent"].casefold() == needle]
    return {"schema_version": payload["schema_version"], "families": families}


def validate_method_plan(payload: dict[str, Any], *, run: dict[str, Any]) -> dict[str, Any]:
    validate_contract("method_plan", payload)
    if payload["run_id"] != run["run_id"]:
        raise ContractError("Method plan run_id does not match active run")
    unit_ids = [item["work_unit_id"] for item in payload["work_units"]]
    if len(unit_ids) != len(set(unit_ids)):
        raise ContractError("Method plan work_unit_id values must be unique")
    return payload


def validate_method_selection(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    plan: dict[str, Any],
    project_config: dict[str, Any],
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    validate_contract("method_selection", payload)
    if payload["run_id"] != run["run_id"]:
        raise ContractError("Method selection run_id does not match active run")
    if payload["plan_id"] != plan["plan_id"]:
        raise ContractError("Method selection plan_id does not match active method plan")
    if expected_plan_sha256 is not None and payload["plan_sha256"] != expected_plan_sha256:
        raise ContractError("Method selection plan_sha256 does not match the active method plan")
    expected_round = int(run["metadata"].get("method_selection_round", 0))
    if payload["selection_round"] != expected_round:
        raise ContractError(
            f"Method selection round is stale: expected {expected_round}, got {payload['selection_round']}"
        )

    discovery = payload["discovery_sources"]
    discovery_names = [item["source"] for item in discovery]
    if len(discovery_names) != len(set(discovery_names)):
        raise ContractError("Method discovery sources must be unique")
    discovery_by_name = {item["source"]: item for item in discovery}
    required_sources = set(project_config["method_selection"]["required_discovery_sources"])
    missing_sources = sorted(required_sources - set(discovery_by_name))
    if missing_sources:
        raise ContractError(f"Required method discovery sources were not accounted for: {missing_sources}")
    unsettled_sources = [
        name
        for name in sorted(required_sources)
        if discovery_by_name[name]["status"] not in SETTLED_DISCOVERY
    ]
    if unsettled_sources:
        raise ContractError(
            "Method selection requires settled discovery sources; unresolved: "
            + ", ".join(unsettled_sources)
        )

    plan_units = {item["work_unit_id"]: item for item in plan["work_units"]}
    selection_units = [item["work_unit_id"] for item in payload["selections"]]
    if len(selection_units) != len(set(selection_units)):
        raise ContractError("Each work unit must have exactly one method selection")
    if set(selection_units) != set(plan_units):
        missing = sorted(set(plan_units) - set(selection_units))
        extra = sorted(set(selection_units) - set(plan_units))
        raise ContractError(f"Method selections do not match work plan; missing={missing}, extra={extra}")

    for selection in payload["selections"]:
        plan_unit = plan_units[selection["work_unit_id"]]
        catalog_hints: dict[str, dict[str, Any]] = {}
        if project_config["method_selection"].get("require_catalog_hint_accounting", True):
            hint_payload = load_method_hints(plan_unit["intent"])
            for family in hint_payload["families"]:
                for hint in family["hints"]:
                    catalog_hints[hint["method_id"]] = hint
        _validate_work_unit_selection(
            selection,
            enforce_specialized_first=project_config["method_selection"][
                "scratch_requires_specialized_exhaustion"
            ],
            catalog_hints=catalog_hints,
        )
    return payload


def _validate_work_unit_selection(
    selection: dict[str, Any],
    *,
    enforce_specialized_first: bool,
    catalog_hints: dict[str, dict[str, Any]],
) -> None:
    methods = selection["candidate_methods"]
    method_ids = [item["method_id"] for item in methods]
    if len(method_ids) != len(set(method_ids)):
        raise ContractError(f"Duplicate method_id in work unit {selection['work_unit_id']}")
    by_id = {item["method_id"]: item for item in methods}
    missing_catalog_hints = sorted(set(catalog_hints) - set(by_id))
    if missing_catalog_hints:
        raise ContractError(
            "Known specialized method hints were omitted from evaluation: "
            + ", ".join(missing_catalog_hints)
        )
    for method_id, hint in catalog_hints.items():
        accounted = by_id[method_id]
        if accounted["kind"] != "SPECIALIZED" or accounted["source"] != hint["source"]:
            raise ContractError(
                f"Known method hint {method_id} must be accounted for as SPECIALIZED from {hint['source']}"
            )

    selected = by_id.get(selection["selected_method_id"])
    if selected is None:
        raise ContractError(
            f"Selected method {selection['selected_method_id']} was not present in candidate_methods"
        )
    if selected["availability"] != "AVAILABLE":
        raise ContractError("Selected production method must be AVAILABLE")
    if selected["requirement_fit"] not in VIABLE_FITS:
        raise ContractError("Selected production method must satisfy the work-unit requirements")
    if selected["requirement_fit"] == "PARTIAL_LOCAL_REFINEMENT" and not selection[
        "remaining_manual_work"
    ]:
        raise ContractError("PARTIAL_LOCAL_REFINEMENT requires bounded remaining_manual_work")

    specialized = [item for item in methods if item["kind"] == "SPECIALIZED"]
    unresolved_methods = [
        item["method_id"]
        for item in specialized
        if item["availability"] == "UNKNOWN" or item["requirement_fit"] == "UNKNOWN"
    ]
    if unresolved_methods:
        raise ContractError(
            "Method selection is blocked by unresolved specialized methods: "
            + ", ".join(sorted(unresolved_methods))
        )

    viable_specialized = [
        item
        for item in specialized
        if item["availability"] == "AVAILABLE" and item["requirement_fit"] in VIABLE_FITS
    ]

    if selected["kind"] == "SPECIALIZED":
        return
    if not enforce_specialized_first:
        return

    if viable_specialized:
        names = sorted(item["method_id"] for item in viable_specialized)
        raise ContractError(
            "General-purpose/scratch selection is forbidden while a viable specialized method exists: "
            + ", ".join(names)
        )
