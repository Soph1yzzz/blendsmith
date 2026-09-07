from __future__ import annotations

import json

import pytest

from blendsmith.errors import ContractError
from blendsmith.methods import load_method_hints, validate_method_plan, validate_method_selection
from blendsmith.project import DEFAULT_CONFIG


def _run() -> dict:
    return {
        "run_id": "run-1",
        "metadata": {"method_selection_round": 0, "method_plan_revision": 0},
    }


def _family_checks(*applicable: str) -> list[dict]:
    applicable_set = set(applicable)
    return [
        {
            "intent": family["intent"],
            "status": "APPLICABLE" if family["intent"] in applicable_set else "NOT_APPLICABLE",
            "evidence": [f"decomposition:{family['intent']}"],
        }
        for family in load_method_hints()["families"]
    ]


def _plan() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "plan_id": "plan-1",
        "revision": 0,
        "supersedes_sha256": None,
        "revision_reason": None,
        "work_units": [
            {
                "work_unit_id": "tree",
                "intent": "tree generation",
                "requirements": ["realistic"],
                "rationale": "The tree is a distinct production responsibility.",
                "stage": "geometry",
                "depends_on": [],
                "method_family_checks": _family_checks("tree_generation"),
                "method_operations": [
                    {
                        "operation_id": "tree.generate",
                        "intent": "tree_generation",
                        "requirements": ["realistic"],
                    }
                ],
            }
        ],
    }


def _sources(*, extensions: str = "CHECKED") -> list[dict]:
    statuses = {
        "BLENDER_NATIVE": "CHECKED",
        "GEOMETRY_NODE_TOOLS": "CHECKED",
        "ASSET_LIBRARIES": "CHECKED",
        "EXTENSIONS": extensions,
        "PROJECT_CATALOG": "CHECKED",
        "ADAPTERS": "CHECKED",
    }
    return [
        {"source": source, "status": status, "evidence": [f"probe:{source}:{status}"]}
        for source, status in statuses.items()
    ]


def _method(
    method_id: str,
    *,
    kind: str,
    availability: str,
    fit: str,
    source: str = "EXTENSION",
) -> dict:
    return {
        "method_id": method_id,
        "label": method_id,
        "kind": kind,
        "source": source,
        "availability": availability,
        "requirement_fit": fit,
        "probe_evidence": [f"probe:{method_id}"],
        "limitations": [],
    }


def _payload(
    methods: list[dict],
    selected: str,
    *,
    sources: list[dict] | None = None,
    account_catalog_hints: bool = True,
) -> dict:
    methods = [dict(item) for item in methods]
    if account_catalog_hints:
        existing = {item["method_id"] for item in methods}
        for family in load_method_hints("tree_generation")["families"]:
            for hint in family["hints"]:
                if hint["method_id"] not in existing:
                    methods.append(
                        _method(
                            hint["method_id"],
                            kind="SPECIALIZED",
                            availability="UNAVAILABLE",
                            fit="INSUFFICIENT",
                            source=hint["source"],
                        )
                    )
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "plan_id": "plan-1",
        "plan_sha256": "a" * 64,
        "selection_round": 0,
        "discovery_sources": sources or _sources(),
        "selections": [
            {
                "work_unit_id": "tree",
                "operation_id": "tree.generate",
                "specialized_search_complete": True,
                "candidate_methods": methods,
                "selected_method_id": selected,
                "selection_reason": "validated choice",
                "remaining_manual_work": [],
            }
        ],
    }


def _config() -> dict:
    return json.loads(json.dumps(DEFAULT_CONFIG))


def test_scratch_is_rejected_when_viable_specialized_method_exists() -> None:
    payload = _payload(
        [
            _method("tree.generator", kind="SPECIALIZED", availability="AVAILABLE", fit="FULL"),
            _method(
                "scratch.mesh",
                kind="SCRATCH",
                availability="AVAILABLE",
                fit="FULL",
                source="CUSTOM",
            ),
        ],
        "scratch.mesh",
    )
    with pytest.raises(ContractError, match="FULL specialized"):
        validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())


def test_scratch_is_rejected_when_specialized_method_is_unknown() -> None:
    payload = _payload(
        [
            _method("tree.generator", kind="SPECIALIZED", availability="UNKNOWN", fit="UNKNOWN"),
            _method(
                "scratch.mesh",
                kind="SCRATCH",
                availability="AVAILABLE",
                fit="FULL",
                source="CUSTOM",
            ),
        ],
        "scratch.mesh",
    )
    with pytest.raises(ContractError, match="unresolved specialized"):
        validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())


def test_scratch_is_rejected_when_required_discovery_source_is_broken() -> None:
    payload = _payload(
        [
            _method("tree.generator", kind="SPECIALIZED", availability="UNAVAILABLE", fit="INSUFFICIENT"),
            _method(
                "scratch.mesh",
                kind="SCRATCH",
                availability="AVAILABLE",
                fit="FULL",
                source="CUSTOM",
            ),
        ],
        "scratch.mesh",
        sources=_sources(extensions="BROKEN"),
    )
    with pytest.raises(ContractError, match="unresolved"):
        validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())


def test_scratch_is_allowed_after_specialized_options_are_exhausted() -> None:
    payload = _payload(
        [
            _method("tree.generator", kind="SPECIALIZED", availability="UNAVAILABLE", fit="INSUFFICIENT"),
            _method(
                "scratch.mesh",
                kind="SCRATCH",
                availability="AVAILABLE",
                fit="FULL",
                source="CUSTOM",
            ),
        ],
        "scratch.mesh",
    )
    assert validate_method_selection(
        payload,
        run=_run(),
        plan=_plan(),
        project_config=_config(),
    ) == payload


def test_selection_must_cover_every_work_unit_exactly_once() -> None:
    plan = _plan()
    plan["work_units"].append(
        {
            "work_unit_id": "grass",
            "intent": "grass scatter",
            "requirements": ["dense"],
            "rationale": "Grass scattering is independent of tree generation.",
            "stage": "detail",
            "depends_on": [],
            "method_family_checks": _family_checks("surface_scatter"),
            "method_operations": [
                {
                    "operation_id": "grass.scatter",
                    "intent": "surface_scatter",
                    "requirements": ["dense"],
                }
            ],
        }
    )
    payload = _payload(
        [_method("tree.generator", kind="SPECIALIZED", availability="AVAILABLE", fit="FULL")],
        "tree.generator",
    )
    with pytest.raises(ContractError, match="do not match planned operations"):
        validate_method_selection(payload, run=_run(), plan=plan, project_config=_config())


def test_method_plan_requires_every_known_method_family_to_be_accounted_for() -> None:
    plan = _plan()
    plan["work_units"][0]["method_family_checks"] = [
        check
        for check in plan["work_units"][0]["method_family_checks"]
        if check["intent"] != "symmetry"
    ]
    with pytest.raises(ContractError, match="account for every known method family"):
        validate_method_plan(plan, run=_run())


def test_applicable_method_family_requires_matching_operation() -> None:
    plan = _plan()
    symmetry = next(
        check for check in plan["work_units"][0]["method_family_checks"] if check["intent"] == "symmetry"
    )
    symmetry["status"] = "APPLICABLE"
    with pytest.raises(ContractError, match="has no matching method operation"):
        validate_method_plan(plan, run=_run())


def test_method_plan_rejects_duplicate_work_units() -> None:
    plan = _plan()
    plan["work_units"].append(dict(plan["work_units"][0]))
    with pytest.raises(ContractError, match="must be unique"):
        validate_method_plan(plan, run=_run())


def test_general_full_can_displace_specialized_partial_only_with_evidence_backed_waiver() -> None:
    payload = _payload(
        [
            _method(
                "tree_generator.extension",
                kind="SPECIALIZED",
                availability="AVAILABLE",
                fit="PARTIAL_LOCAL_REFINEMENT",
                source="EXTENSION",
            ),
            _method(
                "general.native",
                kind="GENERAL_PURPOSE",
                availability="AVAILABLE",
                fit="FULL",
                source="CUSTOM",
            ),
        ],
        "general.native",
    )
    with pytest.raises(ContractError, match="evidence-backed waiver"):
        validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())

    payload["selections"][0]["specialized_waiver"] = {
        "reason": "The specialized method leaves unbounded refinement while the general method is a full fit.",
        "evidence": ["Probe comparison recorded both requirement fits."],
    }
    validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())



def test_partial_specialized_method_requires_bounded_manual_work() -> None:
    payload = _payload(
        [
            _method(
                "tree.generator",
                kind="SPECIALIZED",
                availability="AVAILABLE",
                fit="PARTIAL_LOCAL_REFINEMENT",
            )
        ],
        "tree.generator",
    )
    with pytest.raises(ContractError, match="remaining_manual_work"):
        validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())


def test_tree_generation_hints_include_non_scratch_discovery_targets() -> None:
    payload = load_method_hints("tree_generation")
    sources = {item["source"] for family in payload["families"] for item in family["hints"]}
    assert {"EXTENSION", "GEOMETRY_NODE_TOOL", "ASSET_LIBRARY"} <= sources


def test_known_catalog_hint_cannot_be_omitted() -> None:
    payload = _payload(
        [
            _method(
                "scratch.mesh",
                kind="SCRATCH",
                availability="AVAILABLE",
                fit="FULL",
                source="CUSTOM",
            )
        ],
        "scratch.mesh",
        account_catalog_hints=False,
    )
    with pytest.raises(ContractError, match="Known specialized method hints were omitted"):
        validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())


def test_known_catalog_hint_cannot_be_disguised_as_general_purpose() -> None:
    payload = _payload(
        [
            _method(
                "tree_generator.extension",
                kind="GENERAL_PURPOSE",
                availability="UNAVAILABLE",
                fit="INSUFFICIENT",
                source="EXTENSION",
            ),
            _method(
                "scratch.mesh",
                kind="SCRATCH",
                availability="AVAILABLE",
                fit="FULL",
                source="CUSTOM",
            ),
        ],
        "scratch.mesh",
    )
    with pytest.raises(ContractError, match="must be accounted for as SPECIALIZED"):
        validate_method_selection(payload, run=_run(), plan=_plan(), project_config=_config())
