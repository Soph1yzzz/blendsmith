from __future__ import annotations

import json
from pathlib import Path

import pytest

from blendsmith.closure import verify_candidate_manifest
from blendsmith.domain_knowledge import research_scope_fingerprint
from blendsmith.errors import ContractError, IntegrityError
from blendsmith.hashing import sha256_file
from blendsmith.methods import load_method_hints, validate_method_plan
from blendsmith.orchestrator import BlendSmith
from blendsmith.paths import atomic_write_json
from blendsmith.run_store import load_current_run


def _capabilities(app: BlendSmith) -> None:
    captured_at = "2026-09-10T00:00:00Z"
    atomic_write_json(
        app.layout.capabilities / "0001.json",
        {
            "schema_version": 1,
            "captured_at": captured_at,
            "capabilities": {
                "filesystem": {"status": "AVAILABLE", "details": {}, "observed_at": captured_at},
                "blender_backend": {"status": "AVAILABLE", "details": {}, "observed_at": captured_at},
                "render_image_review": {"status": "AVAILABLE", "details": {}, "observed_at": captured_at},
                "live_blender_gui_review": {
                    "status": "UNAVAILABLE",
                    "details": {"source": "explicit"},
                    "observed_at": captured_at,
                },
            },
        },
    )


def _fake_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def materialize(run_dir, *, candidate_id, views, **kwargs):
        path = Path(run_dir) / "evidence" / candidate_id / "evidence.bundle.json"
        payload = {
            "schema_version": 1,
            "candidate_id": candidate_id,
            "created_at": "2026-09-10T00:00:00Z",
            "views": [{"key": key} for key in views],
        }
        atomic_write_json(path, payload)
        return path, payload

    def verify(run_dir, bundle_path):
        return json.loads(Path(bundle_path).read_text(encoding="utf-8"))

    monkeypatch.setattr("blendsmith.orchestrator.materialize_evidence", materialize)
    monkeypatch.setattr("blendsmith.orchestrator.verify_evidence_bundle", verify)


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


def _risk_checks(*applicable: str) -> list[dict]:
    applicable_set = set(applicable)
    signals = [
        "REAL_WORLD_FUNCTION",
        "DIMENSIONAL_CONSTRAINT",
        "STRUCTURAL_RELATIONSHIP",
        "CONSTRUCTION_OR_MANUFACTURING_PROCESS",
        "SAFETY_OR_CLEARANCE",
        "REGULATION_OR_STANDARD",
        "SPECIALIST_PRACTICE",
    ]
    return [
        {
            "signal": signal,
            "status": "APPLICABLE" if signal in applicable_set else "NOT_APPLICABLE",
            "evidence": [f"test-risk-check:{signal}"],
        }
        for signal in signals
    ]


def _research(app: BlendSmith) -> dict:
    run = app.status()
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "revision": int(run["metadata"].get("domain_research_revision", 0)),
        "supersedes_sha256": run["metadata"].get("previous_domain_research_sha256"),
        "revision_reason": run["metadata"].get("pending_domain_research_revision_reason"),
        "domain": "railway platform infrastructure",
        "decision": "RESEARCH_REQUIRED",
        "risk_signals": ["REAL_WORLD_FUNCTION", "DIMENSIONAL_CONSTRAINT", "SPECIALIST_PRACTICE"],
        "risk_checks": _risk_checks(
            "REAL_WORLD_FUNCTION",
            "DIMENSIONAL_CONSTRAINT",
            "SPECIALIST_PRACTICE",
        ),
        "topics": [
            {
                "topic_key": "platform-mirror-placement",
                "question": "How should a platform observation mirror be placed to serve its operational purpose?",
                "purpose": "Prevent a visually plausible but functionally useless mirror placement.",
                "volatility": "STABLE",
            }
        ],
        "rationale": "The modeled part has a real operational purpose and placement constraints.",
    }


def _knowledge(app: BlendSmith, research: dict) -> dict:
    run = app.status()
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "research_sha256": run["metadata"]["domain_research_sha256"],
        "knowledge_id": "railway-platform-basics",
        "domain": research["domain"],
        "collected_at": "2026-09-10T00:00:00Z",
        "acquisition": "FRESH",
        "scope_fingerprint": research_scope_fingerprint(research),
        "topics": [
            {
                "topic_key": "platform-mirror-placement",
                "volatility": "STABLE",
                "sources": [
                    {
                        "source_id": "source-railway-practice",
                        "kind": "MANUAL",
                        "title": "Railway platform operational reference",
                        "locator": "local:test-fixture/railway-platform-reference",
                        "accessed_at": "2026-09-10T00:00:00Z",
                    }
                ],
                "findings": [
                    {
                        "finding_id": "finding-mirror-sightline",
                        "category": "PLACEMENT",
                        "statement": (
                            "The observation mirror must be oriented around the operator sightline rather than "
                            "attached flat to a convenient wall surface."
                        ),
                        "source_ids": ["source-railway-practice"],
                        "confidence": "HIGH",
                        "actionable": True,
                    }
                ],
            }
        ],
        "limitations": ["This fixture validates the contract flow rather than a specific railway standard."],
        "cache_origin": None,
    }


def _practice(app: BlendSmith) -> dict:
    run = app.status()
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "knowledge_sha256": run["metadata"]["domain_knowledge_sha256"],
        "practice_id": "railway-platform-practice",
        "domain": "railway platform infrastructure",
        "rules": [
            {
                "rule_id": "rule-mirror-sightline",
                "category": "PLACEMENT",
                "requirement": "Orient the observation mirror to the intended operator sightline.",
                "rationale": "The mirror exists to expose a useful view, not merely to decorate the platform wall.",
                "finding_ids": ["finding-mirror-sightline"],
                "confidence": "HIGH",
                "verification": (
                    "Inspect the modeled mirror from the intended operator position and confirm the sightline."
                ),
            }
        ],
        "ignored_findings": [],
    }


def _plan(app: BlendSmith) -> dict:
    run = app.status()
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "plan_id": "railway-plan",
        "revision": int(run["metadata"].get("method_plan_revision", 0)),
        "supersedes_sha256": run["metadata"].get("previous_method_plan_sha256"),
        "revision_reason": run["metadata"].get("pending_plan_revision_reason"),
        "domain_practice_sha256": run["metadata"]["domain_practice_sha256"],
        "work_units": [
            {
                "work_unit_id": "platform-mirror",
                "intent": "model an operational platform observation mirror",
                "purpose": "Give the operator a usable view of the platform.",
                "requirements": ["editable", "operationally placed"],
                "rationale": "Placement and geometry should follow the mirror's real function.",
                "stage": "infrastructure-detail",
                "depends_on": [],
                "domain_constraints": [
                    {
                        "constraint_id": "constraint-mirror-sightline",
                        "practice_rule_id": "rule-mirror-sightline",
                        "requirement": "Orient the observation mirror to the intended operator sightline.",
                        "confidence": "HIGH",
                        "verification": (
                            "Inspect the modeled mirror from the intended operator position and confirm the sightline."
                        ),
                    }
                ],
                "method_family_checks": _family_checks("symmetry"),
                "method_operations": [
                    {
                        "operation_id": "platform-mirror.symmetry",
                        "intent": "symmetry",
                        "requirements": ["editable"],
                    }
                ],
            }
        ],
    }


def _selection(app: BlendSmith) -> dict:
    run_dir, run = load_current_run(app.layout)
    plan_path = run_dir / run["metadata"]["method_plan_path"]
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
        "run_id": run["run_id"],
        "plan_id": run["metadata"]["method_plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "selection_round": int(run["metadata"]["method_selection_round"]),
        "discovery_sources": [
            {"source": source, "status": "CHECKED", "evidence": [f"probe:{source}"]}
            for source in sources
        ],
        "selections": [
            {
                "work_unit_id": "platform-mirror",
                "operation_id": "platform-mirror.symmetry",
                "specialized_search_complete": True,
                "candidate_methods": [
                    {
                        "method_id": "modifier.mirror",
                        "label": "Mirror modifier",
                        "kind": "SPECIALIZED",
                        "source": "BLENDER_NATIVE",
                        "availability": "AVAILABLE",
                        "requirement_fit": "FULL",
                        "probe_evidence": ["Mirror is available in the active Blender environment."],
                        "limitations": [],
                    }
                ],
                "selected_method_id": "modifier.mirror",
                "selection_reason": "Dedicated symmetry tool fully satisfies the operation.",
                "remaining_manual_work": [],
            }
        ],
    }


def _enter_domain_practice(app: BlendSmith) -> tuple[dict, dict]:
    research = _research(app)
    app.submit_domain_research(research)
    assert app.status()["state"] == "AWAITING_DOMAIN_KNOWLEDGE"
    knowledge = _knowledge(app, research)
    app.submit_domain_knowledge(knowledge)
    assert app.status()["state"] == "AWAITING_DOMAIN_PRACTICE"
    return research, knowledge


def _complete_domain_gates(app: BlendSmith) -> None:
    _enter_domain_practice(app)
    app.submit_domain_practice(_practice(app))
    assert app.status()["state"] == "AWAITING_METHOD_PLAN"


def test_next_action_exposes_domain_gate_commands_and_authority(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()
    first = app.next_action()
    assert first["state"] == "AWAITING_DOMAIN_RESEARCH"
    assert "domain-research" in first["next_command"]

    research = _research(app)
    app.submit_domain_research(research)
    second = app.next_action()
    assert second["state"] == "AWAITING_DOMAIN_KNOWLEDGE"
    assert "knowledge-cache" in second["next_command"]
    assert second["domain_research_sha256"] == app.status()["metadata"]["domain_research_sha256"]

    app.submit_domain_knowledge(_knowledge(app, research))
    third = app.next_action()
    assert third["state"] == "AWAITING_DOMAIN_PRACTICE"
    assert "domain-practice" in third["next_command"]
    assert third["domain_knowledge_sha256"] == app.status()["metadata"]["domain_knowledge_sha256"]


def test_domain_research_practice_must_reach_work_unit_constraints(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    run = app.start()
    assert run["state"] == "AWAITING_DOMAIN_RESEARCH"

    _complete_domain_gates(app)
    assert app.status()["metadata"]["domain_knowledge_cache_status"] == "SAVED"

    invalid = _plan(app)
    invalid["work_units"][0]["domain_constraints"][0]["requirement"] = "Attach the mirror wherever convenient."
    with pytest.raises(ContractError, match="changed the requirement"):
        app.submit_method_plan(invalid)

    valid = _plan(app)
    result = app.submit_method_plan(valid)
    assert result["state"] == "AWAITING_METHOD_SELECTION"
    assert result["metadata"]["domain_practice_sha256"] == valid["domain_practice_sha256"]


def test_domain_knowledge_cache_reuses_facts_but_not_practice_authority(tmp_path: Path) -> None:
    root = tmp_path / "project"
    app = BlendSmith.init(root)
    _capabilities(app)
    app.start()
    research, _ = _enter_domain_practice(app)
    first_knowledge_sha = app.status()["metadata"]["domain_knowledge_sha256"]
    assert app.domain_knowledge_cache()["status"] == "VALID"

    second = BlendSmith(root)
    _capabilities(second)
    second.start()
    second_research = _research(second)
    assert research_scope_fingerprint(second_research) == research_scope_fingerprint(research)
    second.submit_domain_research(second_research)
    assert second.domain_knowledge_cache()["status"] == "VALID"
    second.use_domain_knowledge_cache()
    run = second.status()
    assert run["state"] == "AWAITING_DOMAIN_PRACTICE"
    assert run["metadata"]["domain_knowledge_cache_status"] == "CACHE"
    assert run["metadata"]["domain_knowledge_sha256"] != first_knowledge_sha

    with pytest.raises(ContractError, match="Method plan is not currently awaited"):
        second.submit_method_plan({})

    second.submit_domain_practice(_practice(second))
    assert second.status()["state"] == "AWAITING_METHOD_PLAN"

    config = json.loads(second.layout.config.read_text(encoding="utf-8"))
    config["domain_knowledge"]["cache_epoch"] += 1
    atomic_write_json(second.layout.config, config)
    refreshed = BlendSmith(root)
    assert refreshed.domain_knowledge_cache()["status"] == "STALE"
    assert refreshed.domain_knowledge_cache()["reason"] == "cache_epoch_changed"


def test_domain_knowledge_cache_rejects_tampered_validity_window(tmp_path: Path) -> None:
    root = tmp_path / "project"
    app = BlendSmith.init(root)
    _capabilities(app)
    app.start()
    research, _ = _enter_domain_practice(app)
    cache = app.domain_knowledge_cache()
    assert cache["status"] == "VALID"

    cache_path = app.layout.knowledge_cache / f"{research_scope_fingerprint(research)}.json"
    record = json.loads(cache_path.read_text(encoding="utf-8"))
    record["valid_until"] = "2099-01-01T00:00:00Z"
    atomic_write_json(cache_path, record)

    tampered = app.domain_knowledge_cache()
    assert tampered["status"] == "INVALID"
    assert "validity window changed" in tampered["error"]


def test_structural_change_can_reenter_domain_research_before_replanning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()
    _complete_domain_gates(app)
    app.submit_method_plan(_plan(app))
    app.submit_method_selection(_selection(app))

    candidate = tmp_path / "station.blend"
    candidate.write_bytes(b"station-v1")
    app.add_variant(candidate)
    app.begin_evidence()
    app.submit_evidence({"front": Path("unused.png")})
    run_dir, run = load_current_run(app.layout)
    manifest = verify_candidate_manifest(run_dir / run["metadata"]["candidate_manifest_path"])
    app.submit_visual_review(
        {
            "schema_version": 1,
            "run_id": run["run_id"],
            "candidate_id": manifest["candidate_id"],
            "candidate_sha256": manifest["candidate_sha256"],
            "verdict": "REVISE",
            "opened_evidence": ["front"],
            "perspectives_completed": [],
            "issues": [
                {
                    "issue_id": "mirror-function-1",
                    "severity": "medium",
                    "category": "structure",
                    "view_keys": ["front"],
                    "observation": (
                        "The current mirror geometry suggests the original domain assumption may be incomplete."
                    ),
                    "likely_cause": "The operational placement rule needs to be researched again.",
                    "recommended_strategy": "Revisit domain knowledge before revising the production graph.",
                    "regression_risk": "medium",
                    "acceptance_test": "The revised structure is backed by an updated operational rule.",
                }
            ],
            "regressions": [],
            "uncertainties": [],
            "next_action": "classify upstream impact",
        }
    )
    assert app.status()["state"] == "AWAITING_CHANGE_IMPACT"

    app.submit_change_impact(
        {
            "schema_version": 1,
            "run_id": run["run_id"],
            "candidate_id": manifest["candidate_id"],
            "candidate_sha256": manifest["candidate_sha256"],
            "source": "VISUAL_REVIEW",
            "scope": "STRUCTURAL",
            "issue_ids": ["mirror-function-1"],
            "affected_work_units": ["platform-mirror"],
            "rationale": "The observed defect may originate in the upstream operational assumption.",
            "method_continuity": {
                "status": "RESELECT",
                "selected_method_ids": ["modifier.mirror"],
                "evidence": ["The active selection was inspected but is downstream of the domain issue."],
            },
            "global_reassessment_recommended": False,
            "revisit_domain_knowledge": True,
            "upstream_change_summary": "Revalidate how the mirror should work before changing its structure.",
        }
    )
    revised = app.status()
    assert revised["state"] == "AWAITING_DOMAIN_RESEARCH"
    assert revised["iteration"] == 1
    assert revised["metadata"]["domain_research_revision"] == 1
    assert revised["metadata"]["method_plan_revision"] == 1
    assert revised["metadata"]["method_selection_round"] == 1
    assert revised["metadata"]["previous_domain_research_sha256"]
    assert revised["metadata"]["previous_method_plan_sha256"]
    assert "domain_knowledge_path" not in revised["metadata"]
    assert "domain_practice_path" not in revised["metadata"]
    assert revised["metadata"]["domain_knowledge_fresh_required"] is True

    revised_research = _research(app)
    app.submit_domain_research(revised_research)
    cache = app.domain_knowledge_cache()
    assert cache["status"] == "BYPASS_REQUIRED"
    next_command = app.next_action()["next_command"]
    assert "fresh knowledge" in next_command or "domain-knowledge" in next_command
    with pytest.raises(ContractError, match="Fresh domain knowledge is required"):
        app.use_domain_knowledge_cache()

    app.submit_domain_knowledge(_knowledge(app, revised_research))
    assert "domain_knowledge_fresh_required" not in app.status()["metadata"]


def test_checkpoint_pins_domain_authority_chain(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()
    _complete_domain_gates(app)
    app.submit_method_plan(_plan(app))
    app.submit_method_selection(_selection(app))

    checkpointed = app.checkpoint("resume after domain-aware method selection")
    assert checkpointed["state"] == "RESUMABLE"
    run_dir, run = load_current_run(app.layout)
    checkpoint_path = run_dir / run["metadata"]["active_checkpoint_path"]
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["domain_research_snapshot_path"]
    assert checkpoint["domain_knowledge_snapshot_path"]
    assert checkpoint["domain_practice_snapshot_path"]
    assert checkpoint["domain_research_sha256"] == run["metadata"]["domain_research_sha256"]
    assert checkpoint["domain_knowledge_sha256"] == run["metadata"]["domain_knowledge_sha256"]
    assert checkpoint["domain_practice_sha256"] == run["metadata"]["domain_practice_sha256"]

    resumed = app.resume()
    assert resumed["state"] == "WORKING"
    assert resumed["metadata"]["domain_research_sha256"] == checkpoint["domain_research_sha256"]
    assert resumed["metadata"]["domain_knowledge_sha256"] == checkpoint["domain_knowledge_sha256"]
    assert resumed["metadata"]["domain_practice_sha256"] == checkpoint["domain_practice_sha256"]


def test_research_gate_requires_complete_risk_accounting_and_exact_signal_match(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()

    incomplete = _research(app)
    incomplete["risk_checks"] = incomplete["risk_checks"][:-1]
    with pytest.raises(ContractError, match="too short|account for every risk family"):
        app.submit_domain_research(incomplete)

    mismatched = _research(app)
    mismatched["risk_signals"] = ["REAL_WORLD_FUNCTION"]
    with pytest.raises(ContractError, match="exactly match APPLICABLE"):
        app.submit_domain_research(mismatched)

    invalid_skip = _research(app)
    invalid_skip["decision"] = "NOT_REQUIRED"
    invalid_skip["topics"] = []
    invalid_skip["risk_signals"] = []
    with pytest.raises(ContractError, match="risk_signals must exactly match APPLICABLE"):
        app.submit_domain_research(invalid_skip)


def test_confidence_cannot_be_laundered_from_knowledge_to_plan(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()
    research = _research(app)
    app.submit_domain_research(research)
    knowledge = _knowledge(app, research)
    knowledge["topics"][0]["findings"][0]["confidence"] = "LOW"
    app.submit_domain_knowledge(knowledge)

    inflated_practice = _practice(app)
    with pytest.raises(ContractError, match="cannot claim higher confidence"):
        app.submit_domain_practice(inflated_practice)

    practice = _practice(app)
    practice["rules"][0]["confidence"] = "LOW"
    app.submit_domain_practice(practice)

    inflated_plan = _plan(app)
    inflated_plan["work_units"][0]["domain_constraints"][0]["confidence"] = "HIGH"
    with pytest.raises(ContractError, match="changed the confidence"):
        app.submit_method_plan(inflated_plan)

    valid = _plan(app)
    valid["work_units"][0]["domain_constraints"][0]["confidence"] = "LOW"
    assert app.submit_method_plan(valid)["state"] == "AWAITING_METHOD_SELECTION"


def test_domain_knowledge_rejects_future_timestamp_authority(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()
    research = _research(app)
    app.submit_domain_research(research)

    future = _knowledge(app, research)
    future["collected_at"] = "2099-01-01T00:00:00Z"
    future["topics"][0]["sources"][0]["accessed_at"] = "2099-01-01T00:00:00Z"
    with pytest.raises(ContractError, match="collected_at cannot be materially in the future"):
        app.submit_domain_knowledge(future)

    source_after_collection = _knowledge(app, research)
    source_after_collection["topics"][0]["sources"][0]["accessed_at"] = "2026-09-10T01:00:00Z"
    with pytest.raises(ContractError, match="cannot be accessed after collected_at"):
        app.submit_domain_knowledge(source_after_collection)


@pytest.mark.parametrize(
    ("authority_key", "mutator", "expected"),
    [
        (
            "domain_research_path",
            lambda payload: payload.__setitem__("rationale", "tampered research rationale"),
            "domain research bytes changed",
        ),
        (
            "domain_knowledge_path",
            lambda payload: payload.__setitem__("limitations", ["tampered knowledge"]),
            "domain knowledge bytes changed",
        ),
        (
            "domain_practice_path",
            lambda payload: payload["rules"][0].__setitem__("rationale", "tampered practice rationale"),
            "domain practice bytes changed",
        ),
    ],
)
def test_domain_authority_tamper_blocks_method_planning(
    tmp_path: Path,
    authority_key: str,
    mutator,
    expected: str,
) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()
    _complete_domain_gates(app)
    run_dir, run = load_current_run(app.layout)
    path = run_dir / run["metadata"][authority_key]
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    atomic_write_json(path, payload)

    with pytest.raises(IntegrityError, match=expected):
        app.submit_method_plan(_plan(app))


def test_checkpoint_domain_snapshot_tamper_blocks_resume(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app)
    app.start()
    _complete_domain_gates(app)
    app.submit_method_plan(_plan(app))
    app.submit_method_selection(_selection(app))
    app.checkpoint("resume after domain-aware method selection")

    run_dir, run = load_current_run(app.layout)
    checkpoint_path = run_dir / run["metadata"]["active_checkpoint_path"]
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    practice_snapshot = checkpoint_path.parent / checkpoint["domain_practice_snapshot_path"]
    practice = json.loads(practice_snapshot.read_text(encoding="utf-8"))
    practice["rules"][0]["rationale"] = "tampered checkpoint practice"
    atomic_write_json(practice_snapshot, practice)

    with pytest.raises(IntegrityError, match="snapshot SHA mismatch"):
        app.resume()


def test_legacy_v002_method_plan_remains_valid_without_domain_fields() -> None:
    run = {
        "run_id": "legacy-run",
        "metadata": {"method_plan_revision": 0},
    }
    legacy = {
        "schema_version": 1,
        "run_id": "legacy-run",
        "plan_id": "legacy-plan",
        "revision": 0,
        "supersedes_sha256": None,
        "revision_reason": None,
        "work_units": [
            {
                "work_unit_id": "shape",
                "intent": "symmetry",
                "requirements": ["editable"],
                "rationale": "Legacy v0.0.2 work unit.",
                "stage": "geometry",
                "depends_on": [],
                "method_family_checks": _family_checks("symmetry"),
                "method_operations": [
                    {"operation_id": "shape.symmetry", "intent": "symmetry", "requirements": ["editable"]}
                ],
            }
        ],
    }
    assert validate_method_plan(legacy, run=run) == legacy
