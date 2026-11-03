from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from test_lifecycle import (
    _accepted_visual_payload,
    _capabilities,
    _domain_not_required,
    _fake_evidence,
    _method_plan,
    _specialized_selection,
)
from test_reference_images import _guided_working_app, _image, _promote_quality

from blendsmith.errors import ContractError, IntegrityError
from blendsmith.geometry_audit import inspect_contact_proximity
from blendsmith.orchestrator import BlendSmith
from blendsmith.quality import validate_assessment
from blendsmith.run_store import load_current_run


def _assessment(app: BlendSmith) -> dict:
    payload = app.contract_template("quality_assessment")
    payload["creator_context_id"] = "modeler-1"
    payload["reviewer_context_id"] = "fresh-blind-reviewer-2"
    payload["opened_evidence"] = ["front"]
    payload["target_results"][0]["observations"] = ["Compared thickness, profile and mounting."]
    payload["target_results"][0]["fidelity"] = "MATCH"
    payload["target_results"][0]["confidence"] = "HIGH"
    payload["decision"] = "PROMOTE"
    return payload


def test_new_reference_run_requires_targets_before_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app, "UNAVAILABLE")
    app.start()
    app.add_reference("photo", _image(tmp_path / "photo.png"))
    _domain_not_required(app)
    app.submit_method_plan(_method_plan(app))
    app.submit_method_selection(_specialized_selection(app))
    candidate = tmp_path / "scene.blend"
    candidate.write_bytes(b"scene")
    with pytest.raises(ContractError, match="requires feature targets"):
        app.add_variant(candidate)


def test_quality_assessment_checks_every_feature_and_separate_reviewer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _guided_working_app(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": tmp_path / "unused.png"})
    payload = _assessment(app)
    payload["target_results"] = []
    with pytest.raises(ContractError, match="quality_assessment contract invalid"):
        app.submit_quality_assessment(payload)
    payload = _assessment(app)
    payload["reviewer_context_id"] = payload["creator_context_id"]
    with pytest.raises(ContractError, match="separate evaluator context"):
        app.submit_quality_assessment(payload)
    payload = _assessment(app)
    payload["opened_evidence"] = ["rear"]
    with pytest.raises(ContractError, match="unknown rendered views"):
        app.submit_quality_assessment(payload)
    assert app.submit_quality_assessment(_assessment(app))["decision"] == "PROMOTE"


def test_regression_and_uncertainty_cannot_displace_best(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _guided_working_app(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": tmp_path / "unused.png"})
    _promote_quality(app)
    best = app.quality_status()["best"]
    targets = app.quality_status()["targets"]
    run_dir, run = load_current_run(app.layout)
    assert best["candidate_sha256"]
    payload = _assessment(app)
    payload["candidate_id"] = "new-candidate"
    payload["candidate_sha256"] = "b" * 64
    payload["compared_to_sha256"] = best["candidate_sha256"]
    payload["target_results"][0]["delta"] = "REGRESSED"
    candidate = {"candidate_id": "new-candidate", "candidate_sha256": "b" * 64}
    with pytest.raises(ContractError, match="worse or incomparable"):
        validate_assessment(
            payload, run=run, candidate=candidate, targets=targets,
            targets_sha256=run["metadata"]["quality_targets_sha256"],
            evidence_views={"front"}, best_sha256=best["candidate_sha256"],
        )
    assert app.quality_status()["best"] == best
    assert run_dir.is_dir()


def test_visual_accept_requires_promoted_quality_and_tamper_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _guided_working_app(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": tmp_path / "unused.png"})
    visual = _accepted_visual_payload(app)
    ref = app.reference_status()["references"][0]
    visual["reference_comparisons"] = [{
        "reference_id": "main-photo", "reference_sha256": ref["sha256"],
        "view_keys": ["front"], "observations": ["Compared with source."], "fidelity": "MATCH",
    }]
    with pytest.raises(ContractError, match="requires a quality assessment"):
        app.submit_visual_review(visual)
    _promote_quality(app)
    run_dir, run = load_current_run(app.layout)
    assessment_path = run_dir / run["metadata"]["quality_assessment_path"]
    assessment_path.write_text("{}")
    with pytest.raises(IntegrityError, match="modified or removed"):
        app.submit_visual_review(visual)


def test_objective_geometry_failure_blocks_promotion_but_allows_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = {
        "check_id": "seam-contact",
        "source_objects": ["thread"], "target_objects": ["leather"],
        "max_distance_mm": 0.5, "min_source_vertices": 3,
    }
    app = _guided_working_app(tmp_path, monkeypatch, geometry_checks=[check])
    app.begin_evidence()
    app.submit_evidence({"front": tmp_path / "unused.png"})
    observed = [{
        "check_id": "seam-contact", "status": "FAIL",
        "max_distance_mm": 1.8, "vertices_inspected": 20, "reason": "Gap too large",
    }]
    monkeypatch.setattr("blendsmith.quality_runtime.latest_snapshot", lambda layout: {
        "capabilities": {"blender_backend": {"details": {"executable": "test-blender"}}},
    })
    monkeypatch.setattr("blendsmith.quality_runtime.inspect_contact_proximity", lambda *a, **kw: observed)
    with pytest.raises(ContractError, match="failed contact"):
        app.submit_quality_assessment(_assessment(app))
    payload = _assessment(app)
    payload["decision"] = "HOLD"
    assert app.submit_quality_assessment(payload)["geometry_results"] == observed
    assert app.quality_status()["best"] is None


def test_geometry_audit_rejects_forged_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = {
        "check_id": "seam-contact",
        "source_objects": ["thread"], "target_objects": ["leather"],
        "max_distance_mm": 0.5, "min_source_vertices": 3,
    }

    def fake_run(*args, **kwargs):
        data = [{
            "check_id": "seam-contact", "status": "PASS",
            "max_distance_mm": 1.8, "vertices_inspected": 20, "reason": "fake",
        }]
        return CompletedProcess(args[0], 0, "BLENDSMITH_GEOMETRY_AUDIT:" + json.dumps(data), "")

    monkeypatch.setattr("blendsmith.geometry_audit.subprocess.run", fake_run)
    with pytest.raises(IntegrityError, match="PASS without meeting"):
        inspect_contact_proximity("blender", tmp_path / "scene.blend", [check])
