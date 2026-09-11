from __future__ import annotations

import json
from pathlib import Path

import pytest

from blendsmith.errors import ContractError
from blendsmith.method_cache import load_method_cache, method_cache_fingerprint, save_method_cache
from blendsmith.methods import load_method_hints
from blendsmith.orchestrator import BlendSmith
from blendsmith.paths import atomic_write_json
from blendsmith.project import initialize_project, load_project


def _capability_snapshot(root: Path, fingerprint: str) -> None:
    layout, _ = load_project(root)
    atomic_write_json(
        layout.capabilities / "0001.json",
        {
            "schema_version": 1,
            "captured_at": "2026-09-07T00:00:00Z",
            "capabilities": {
                "filesystem": {"status": "AVAILABLE", "details": {}, "observed_at": "2026-09-07T00:00:00Z"},
                "blender_backend": {
                    "status": "AVAILABLE",
                    "details": {"version": "5.2.1"},
                    "observed_at": "2026-09-07T00:00:00Z",
                },
                "method_environment": {
                    "status": "AVAILABLE",
                    "details": {"fingerprint": fingerprint},
                    "observed_at": "2026-09-07T00:00:00Z",
                },
                "render_image_review": {"status": "AVAILABLE", "details": {}, "observed_at": "2026-09-07T00:00:00Z"},
                "live_blender_gui_review": {
                    "status": "UNAVAILABLE",
                    "details": {},
                    "observed_at": "2026-09-07T00:00:00Z",
                },
            },
        },
    )


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


def _domain_not_required(app: BlendSmith) -> None:
    run = app.status()
    app.submit_domain_research(
        {
            "schema_version": 1,
            "run_id": run["run_id"],
            "revision": int(run["metadata"].get("domain_research_revision", 0)),
            "supersedes_sha256": None,
            "revision_reason": None,
            "domain": "purely artistic cache test",
            "decision": "NOT_REQUIRED",
            "risk_signals": [],
            "risk_checks": [
                {"signal": signal, "status": "NOT_APPLICABLE", "evidence": [f"test:{signal}:not-applicable"]}
                for signal in [
                    "REAL_WORLD_FUNCTION",
                    "DIMENSIONAL_CONSTRAINT",
                    "STRUCTURAL_RELATIONSHIP",
                    "CONSTRUCTION_OR_MANUFACTURING_PROCESS",
                    "SAFETY_OR_CLEARANCE",
                    "REGULATION_OR_STANDARD",
                    "SPECIALIST_PRACTICE",
                ]
            ],
            "topics": [],
            "rationale": "Method-cache tests do not need external domain research.",
        }
    )


def _plan() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "plan_id": "plan-1",
        "revision": 0,
        "supersedes_sha256": None,
        "revision_reason": None,
        "domain_practice_sha256": None,
        "work_units": [
            {
                "work_unit_id": "shape",
                "intent": "symmetry",
                "purpose": "Provide an editable symmetric test shape.",
                "requirements": ["editable"],
                "rationale": "Keep both sides mechanically linked.",
                "stage": "geometry",
                "depends_on": [],
                "domain_constraints": [],
                "method_family_checks": _family_checks("symmetry"),
                "method_operations": [
                    {
                        "operation_id": "shape.symmetry",
                        "intent": "symmetry",
                        "requirements": ["editable"],
                    }
                ],
            }
        ],
    }


def _selection() -> dict:
    sources = [
        "BLENDER_NATIVE",
        "GEOMETRY_NODE_TOOLS",
        "ASSET_LIBRARIES",
        "EXTENSIONS",
        "PROJECT_CATALOG",
        "ADAPTERS",
    ]
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "plan_id": "plan-1",
        "plan_sha256": "a" * 64,
        "selection_round": 0,
        "discovery_sources": [
            {"source": source, "status": "CHECKED", "evidence": [f"probe:{source}"]}
            for source in sources
        ],
        "selections": [
            {
                "work_unit_id": "shape",
                "operation_id": "shape.symmetry",
                "specialized_search_complete": True,
                "candidate_methods": [
                    {
                        "method_id": "modifier.mirror",
                        "label": "Mirror modifier",
                        "kind": "SPECIALIZED",
                        "source": "BLENDER_NATIVE",
                        "availability": "AVAILABLE",
                        "requirement_fit": "FULL",
                        "probe_evidence": ["Mirror exists in this Blender environment"],
                        "limitations": [],
                    }
                ],
                "selected_method_id": "modifier.mirror",
                "selection_reason": "Dedicated full-fit method.",
                "remaining_manual_work": [],
                "specialized_waiver": None,
            }
        ],
    }


def test_method_cache_reuses_discovery_facts_only_for_same_environment(tmp_path: Path) -> None:
    root = tmp_path / "project"
    initialize_project(root)
    _capability_snapshot(root, "e" * 64)
    layout, config = load_project(root)
    config = json.loads(json.dumps(config))

    identity = method_cache_fingerprint(layout, config)
    assert identity["status"] == "AVAILABLE"
    cached = save_method_cache(layout, config, plan=_plan(), selection=_selection())
    assert cached is not None

    loaded = load_method_cache(layout, config, intent="symmetry")
    assert loaded["status"] == "VALID"
    assert loaded["fingerprint"] == identity["fingerprint"]
    assert loaded["entries"][0]["previous_selected_method_id"] == "modifier.mirror"
    assert loaded["cache_scope"] == ["BLENDER_NATIVE"]
    assert set(loaded["uncached_sources"]) == {
        "GEOMETRY_NODE_TOOLS",
        "ASSET_LIBRARIES",
        "EXTENSIONS",
        "PROJECT_CATALOG",
        "ADAPTERS",
    }
    assert [item["source"] for item in loaded["discovery_sources"]] == ["BLENDER_NATIVE"]
    assert "not method-selection authority" in loaded["note"]

    _capability_snapshot(root, "f" * 64)
    stale = load_method_cache(layout, config, intent="symmetry")
    assert stale["status"] == "STALE"
    assert stale["entries"] == []


def test_cached_discovery_selection_remains_valid_when_candidate_is_ingested(tmp_path: Path) -> None:
    root = tmp_path / "project"
    app = BlendSmith.init(root)
    _capability_snapshot(root, "e" * 64)
    app.start()
    _domain_not_required(app)

    plan = _plan()
    plan["run_id"] = app.status()["run_id"]
    app.submit_method_plan(plan)

    cache_identity = method_cache_fingerprint(app.layout, app.config)
    assert cache_identity["status"] == "AVAILABLE"
    selection = _selection()
    selection["run_id"] = app.status()["run_id"]
    selection["plan_id"] = app.status()["metadata"]["method_plan_id"]
    selection["plan_sha256"] = app.status()["metadata"]["method_plan_sha256"]
    selection["selections"][0].pop("specialized_waiver", None)
    native_source = next(
        source for source in selection["discovery_sources"] if source["source"] == "BLENDER_NATIVE"
    )
    native_source["cache_fingerprint"] = cache_identity["fingerprint"]
    app.submit_method_selection(selection)

    candidate = tmp_path / "cached-selection.blend"
    candidate.write_bytes(b"virtual-candidate")
    result = app.add_variant(candidate)
    assert result["state"] == "WORKING"
    assert result["active_candidate_id"] is not None


def test_uncacheable_discovery_source_cannot_claim_cache_authority(tmp_path: Path) -> None:
    root = tmp_path / "project"
    app = BlendSmith.init(root)
    _capability_snapshot(root, "e" * 64)
    app.start()
    _domain_not_required(app)

    plan = _plan()
    plan["run_id"] = app.status()["run_id"]
    app.submit_method_plan(plan)

    cache_identity = method_cache_fingerprint(app.layout, app.config)
    selection = _selection()
    selection["run_id"] = app.status()["run_id"]
    selection["plan_id"] = app.status()["metadata"]["method_plan_id"]
    selection["plan_sha256"] = app.status()["metadata"]["method_plan_sha256"]
    selection["selections"][0].pop("specialized_waiver", None)
    adapter_source = next(
        source for source in selection["discovery_sources"] if source["source"] == "ADAPTERS"
    )
    adapter_source["cache_fingerprint"] = cache_identity["fingerprint"]

    with pytest.raises(ContractError, match="cannot authorize sources"):
        app.submit_method_selection(selection)
