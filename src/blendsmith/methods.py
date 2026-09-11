from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .contracts import validate_contract
from .errors import ContractError
from .method_cache import CACHEABLE_DISCOVERY_SOURCES

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


def validate_method_plan(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    domain_practice: dict[str, Any] | None = None,
    expected_domain_practice_sha256: str | None = None,
) -> dict[str, Any]:
    validate_contract("method_plan", payload)
    if payload["run_id"] != run["run_id"]:
        raise ContractError("Method plan run_id does not match active run")

    domain_contract_required = "domain_research_revision" in run["metadata"]
    if domain_contract_required and "domain_practice_sha256" not in payload:
        raise ContractError("New production runs require an explicit domain_practice_sha256 field")
    if domain_practice is None:
        if payload.get("domain_practice_sha256") is not None:
            raise ContractError("Method plan cites domain practice when no active domain practice exists")
        practice_rules: dict[str, dict[str, Any]] = {}
    else:
        if expected_domain_practice_sha256 is None:
            raise ContractError("Active domain practice has no authoritative SHA")
        if payload.get("domain_practice_sha256") != expected_domain_practice_sha256:
            raise ContractError("Method plan is not bound to the active domain practice receipt")
        practice_rules = {rule["rule_id"]: rule for rule in domain_practice["rules"]}

    expected_revision = int(run["metadata"].get("method_plan_revision", 0))
    if payload["revision"] != expected_revision:
        raise ContractError(
            f"Method plan revision is stale: expected {expected_revision}, got {payload['revision']}"
        )
    if expected_revision > 0:
        expected_supersedes = run["metadata"].get("previous_method_plan_sha256")
        if not expected_supersedes:
            raise ContractError("Revised method plan has no authoritative predecessor SHA")
        if payload.get("supersedes_sha256") != expected_supersedes:
            raise ContractError("Revised method plan must supersede the exact previous plan SHA")

    units = payload["work_units"]
    unit_ids = [item["work_unit_id"] for item in units]
    if len(unit_ids) != len(set(unit_ids)):
        raise ContractError("Method plan work_unit_id values must be unique")
    unit_set = set(unit_ids)

    catalog_intents = {
        family["intent"] for family in load_method_hints()["families"]
    }
    operation_ids: list[str] = []
    constraint_ids: list[str] = []
    referenced_practice_rules: set[str] = set()
    for unit in units:
        if domain_contract_required:
            if not unit.get("purpose"):
                raise ContractError(f"Work unit {unit['work_unit_id']} requires an explicit purpose")
            if "domain_constraints" not in unit:
                raise ContractError(
                    f"Work unit {unit['work_unit_id']} must explicitly include domain_constraints, even when empty"
                )
        deps = unit["depends_on"]
        if unit["work_unit_id"] in deps:
            raise ContractError(f"Work unit {unit['work_unit_id']} cannot depend on itself")
        missing = sorted(set(deps) - unit_set)
        if missing:
            raise ContractError(
                f"Work unit {unit['work_unit_id']} depends on unknown work units: {missing}"
            )
        constraints = unit.get("domain_constraints", [])
        local_constraint_ids = [item["constraint_id"] for item in constraints]
        if len(local_constraint_ids) != len(set(local_constraint_ids)):
            raise ContractError(f"Domain constraint IDs must be unique inside {unit['work_unit_id']}")
        constraint_ids.extend(local_constraint_ids)
        for constraint in constraints:
            rule_id = constraint["practice_rule_id"]
            rule = practice_rules.get(rule_id)
            if rule is None:
                raise ContractError(
                    f"Work unit {unit['work_unit_id']} cites unknown domain practice rule {rule_id}"
                )
            if constraint["requirement"] != rule["requirement"]:
                raise ContractError(
                    "Domain constraint "
                    f"{constraint['constraint_id']} changed the requirement from practice rule {rule_id}"
                )
            if constraint["confidence"] != rule["confidence"]:
                raise ContractError(
                    "Domain constraint "
                    f"{constraint['constraint_id']} changed the confidence from practice rule {rule_id}"
                )
            if constraint["verification"] != rule["verification"]:
                raise ContractError(
                    "Domain constraint "
                    f"{constraint['constraint_id']} changed the verification from practice rule {rule_id}"
                )
            referenced_practice_rules.add(rule_id)

        checks = unit["method_family_checks"]
        check_intents = [check["intent"] for check in checks]
        if len(check_intents) != len(set(check_intents)):
            raise ContractError(
                f"Method-family checks must be unique inside {unit['work_unit_id']}"
            )
        missing_checks = sorted(catalog_intents - set(check_intents))
        extra_checks = sorted(set(check_intents) - catalog_intents)
        if missing_checks or extra_checks:
            raise ContractError(
                f"Work unit {unit['work_unit_id']} must account for every known method family; "
                f"missing={missing_checks}, extra={extra_checks}"
            )

        operation_intents = {operation["intent"] for operation in unit["method_operations"]}
        for check in checks:
            intent = check["intent"]
            if check["status"] == "APPLICABLE" and intent not in operation_intents:
                raise ContractError(
                    f"Work unit {unit['work_unit_id']} marks {intent} APPLICABLE but has no matching method operation"
                )
            if check["status"] == "NOT_APPLICABLE" and intent in operation_intents:
                raise ContractError(
                    f"Work unit {unit['work_unit_id']} has a {intent} operation but marks that family NOT_APPLICABLE"
                )

        ids = [operation["operation_id"] for operation in unit["method_operations"]]
        if len(ids) != len(set(ids)):
            raise ContractError(f"Method operation IDs must be unique inside {unit['work_unit_id']}")
        operation_ids.extend(ids)

    if len(operation_ids) != len(set(operation_ids)):
        raise ContractError("Method operation IDs must be globally unique")
    if len(constraint_ids) != len(set(constraint_ids)):
        raise ContractError("Domain constraint IDs must be globally unique")
    missing_rules = sorted(set(practice_rules) - referenced_practice_rules)
    if missing_rules:
        raise ContractError(
            "Every domain practice rule must be mapped into at least one work-unit constraint: "
            + ", ".join(missing_rules)
        )
    _validate_acyclic_graph(units)
    return payload


def _validate_acyclic_graph(units: list[dict[str, Any]]) -> None:
    graph = {item["work_unit_id"]: tuple(item["depends_on"]) for item in units}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise ContractError(f"Production graph contains a dependency cycle at {node}")
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def validate_method_selection(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    plan: dict[str, Any],
    project_config: dict[str, Any],
    expected_plan_sha256: str | None = None,
    expected_cache_fingerprint: str | None = None,
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
    cached_sources = {
        item["source"]
        for item in discovery
        if item.get("cache_fingerprint") is not None
    }
    unsupported_cached_sources = sorted(cached_sources - CACHEABLE_DISCOVERY_SOURCES)
    if unsupported_cached_sources:
        raise ContractError(
            "Method discovery cache cannot authorize sources without a Core-owned freshness fingerprint: "
            + ", ".join(unsupported_cached_sources)
        )
    cache_fingerprints = {
        item["cache_fingerprint"]
        for item in discovery
        if item.get("cache_fingerprint") is not None
    }
    if len(cache_fingerprints) > 1:
        raise ContractError("Method discovery sources cite multiple cache fingerprints")
    if cache_fingerprints:
        if expected_cache_fingerprint is None:
            raise ContractError("Cached method discovery cannot be used without a current environment fingerprint")
        if cache_fingerprints != {expected_cache_fingerprint}:
            raise ContractError("Method discovery cache fingerprint is stale for the current environment")
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

    operations: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for unit in plan["work_units"]:
        for operation in unit["method_operations"]:
            operations[operation["operation_id"]] = (unit, operation)

    selection_operation_ids = [item["operation_id"] for item in payload["selections"]]
    if len(selection_operation_ids) != len(set(selection_operation_ids)):
        raise ContractError("Each method operation must have exactly one method selection")
    if set(selection_operation_ids) != set(operations):
        missing = sorted(set(operations) - set(selection_operation_ids))
        extra = sorted(set(selection_operation_ids) - set(operations))
        raise ContractError(
            f"Method selections do not match planned operations; missing={missing}, extra={extra}"
        )

    for selection in payload["selections"]:
        unit, operation = operations[selection["operation_id"]]
        if selection["work_unit_id"] != unit["work_unit_id"]:
            raise ContractError(
                f"Operation {selection['operation_id']} belongs to work unit {unit['work_unit_id']}"
            )
        catalog_hints: dict[str, dict[str, Any]] = {}
        if project_config["method_selection"].get("require_catalog_hint_accounting", True):
            hint_payload = load_method_hints(operation["intent"])
            for family in hint_payload["families"]:
                for hint in family["hints"]:
                    catalog_hints[hint["method_id"]] = hint
        _validate_operation_selection(
            selection,
            enforce_specialized_first=project_config["method_selection"][
                "scratch_requires_specialized_exhaustion"
            ],
            catalog_hints=catalog_hints,
        )
    return payload


def _validate_operation_selection(
    selection: dict[str, Any],
    *,
    enforce_specialized_first: bool,
    catalog_hints: dict[str, dict[str, Any]],
) -> None:
    methods = selection["candidate_methods"]
    method_ids = [item["method_id"] for item in methods]
    if len(method_ids) != len(set(method_ids)):
        raise ContractError(f"Duplicate method_id in operation {selection['operation_id']}")
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
        raise ContractError("Selected production method must satisfy the operation requirements")
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

    specialized_full = [
        item
        for item in specialized
        if item["availability"] == "AVAILABLE" and item["requirement_fit"] == "FULL"
    ]
    specialized_partial = [
        item
        for item in specialized
        if item["availability"] == "AVAILABLE"
        and item["requirement_fit"] == "PARTIAL_LOCAL_REFINEMENT"
    ]
    viable_general = [
        item
        for item in methods
        if item["kind"] == "GENERAL_PURPOSE"
        and item["availability"] == "AVAILABLE"
        and item["requirement_fit"] in VIABLE_FITS
    ]

    if selected["kind"] == "SPECIALIZED" or not enforce_specialized_first:
        return

    if specialized_full:
        names = sorted(item["method_id"] for item in specialized_full)
        raise ContractError(
            "General-purpose/scratch selection is forbidden while a FULL specialized method exists: "
            + ", ".join(names)
        )

    if selected["kind"] == "SCRATCH":
        alternatives = specialized_partial + viable_general
        if alternatives:
            names = sorted(item["method_id"] for item in alternatives)
            raise ContractError(
                "Scratch selection is forbidden while a viable non-scratch method exists: "
                + ", ".join(names)
            )
        return

    if specialized_partial:
        if selected["requirement_fit"] != "FULL":
            names = sorted(item["method_id"] for item in specialized_partial)
            raise ContractError(
                "A PARTIAL general-purpose method cannot displace a viable specialized method: "
                + ", ".join(names)
            )
        waiver = selection.get("specialized_waiver")
        if not waiver:
            names = sorted(item["method_id"] for item in specialized_partial)
            raise ContractError(
                "Selecting GENERAL_PURPOSE + FULL over SPECIALIZED + PARTIAL requires an evidence-backed waiver: "
                + ", ".join(names)
            )
