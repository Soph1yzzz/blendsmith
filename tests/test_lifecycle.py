from __future__ import annotations

import json
from pathlib import Path

import pytest

from blendsmith.checkpoint import verify_checkpoint
from blendsmith.closure import verify_candidate_manifest
from blendsmith.errors import AuthorityError, ContractError, IntegrityError, SafetyError
from blendsmith.hashing import sha256_file
from blendsmith.orchestrator import BlendSmith
from blendsmith.paths import atomic_write_json
from blendsmith.publication import publish_verified
from blendsmith.run_store import load_current_run, save_run, transition
from blendsmith.state_machine import RunState


def _capabilities(app: BlendSmith, gui: str) -> None:
    payload = {
        "schema_version": 1,
        "captured_at": "2026-09-06T00:00:00Z",
        "capabilities": {
            "filesystem": {"status": "AVAILABLE", "details": {}, "observed_at": "2026-09-06T00:00:00Z"},
            "blender_backend": {"status": "AVAILABLE", "details": {}, "observed_at": "2026-09-06T00:00:00Z"},
            "render_image_review": {"status": "AVAILABLE", "details": {}, "observed_at": "2026-09-06T00:00:00Z"},
            "live_blender_gui_review": {"status": gui, "details": {}, "observed_at": "2026-09-06T00:00:00Z"},
        },
    }
    atomic_write_json(app.layout.capabilities / "0001.json", payload)


def _fake_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def materialize(run_dir, *, candidate_id, views, **kwargs):
        path = Path(run_dir) / "evidence" / candidate_id / "evidence.bundle.json"
        payload = {
            "schema_version": 1,
            "candidate_id": candidate_id,
            "created_at": "2026-09-06T00:00:00Z",
            "views": [{"key": key} for key in views],
        }
        atomic_write_json(path, payload)
        return path, payload

    def verify(run_dir, bundle_path):
        return json.loads(Path(bundle_path).read_text(encoding="utf-8"))

    monkeypatch.setattr("blendsmith.orchestrator.materialize_evidence", materialize)
    monkeypatch.setattr("blendsmith.orchestrator.verify_evidence_bundle", verify)


def _discovery_sources(*, extensions: str = "CHECKED") -> list[dict]:
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


def _method_plan(app: BlendSmith, *, plan_id: str = "plan-main") -> dict:
    run = app.status()
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "plan_id": plan_id,
        "work_units": [
            {
                "work_unit_id": "primary-shape",
                "intent": "symmetry",
                "requirements": ["editable", "repeatable"],
            }
        ],
    }


def _specialized_selection(app: BlendSmith, *, round_id: int = 0) -> dict:
    run_dir, run = load_current_run(app.layout)
    plan_path = run_dir / run["metadata"]["method_plan_path"]
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "plan_id": run["metadata"]["method_plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "selection_round": round_id,
        "discovery_sources": _discovery_sources(),
        "selections": [
            {
                "work_unit_id": "primary-shape",
                "specialized_search_complete": True,
                "candidate_methods": [
                    {
                        "method_id": "modifier.mirror",
                        "label": "Mirror modifier",
                        "kind": "SPECIALIZED",
                        "source": "BLENDER_NATIVE",
                        "availability": "AVAILABLE",
                        "requirement_fit": "FULL",
                        "probe_evidence": ["Blender modifier probe found Mirror"],
                        "limitations": [],
                    }
                ],
                "selected_method_id": "modifier.mirror",
                "selection_reason": "Dedicated symmetry method satisfies the work unit.",
                "remaining_manual_work": [],
            }
        ],
    }


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, gui: str = "UNAVAILABLE") -> BlendSmith:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app, gui)
    run = app.start()
    assert run["state"] == "AWAITING_METHOD_PLAN"
    app.submit_method_plan(_method_plan(app))
    app.submit_method_selection(_specialized_selection(app))
    candidate = tmp_path / "scene.blend"
    dependency = tmp_path / "texture.bin"
    candidate.write_bytes(b"candidate-v1")
    dependency.write_bytes(b"texture-v1")
    run = app.add_variant(candidate, dependencies=[dependency])
    assert run["state"] == "WORKING"
    return app


def _accepted_visual_payload(app: BlendSmith) -> dict:
    run_dir, run = __import__("blendsmith.run_store", fromlist=["load_current_run"]).load_current_run(app.layout)
    manifest_path = run_dir / run["metadata"]["candidate_manifest_path"]
    manifest = verify_candidate_manifest(manifest_path)
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "candidate_id": manifest["candidate_id"],
        "candidate_sha256": manifest["candidate_sha256"],
        "verdict": "ACCEPT",
        "opened_evidence": ["front"],
        "perspectives_completed": [],
        "issues": [],
        "regressions": [],
        "uncertainties": [],
        "next_action": "owner gate",
    }


def _reach_owner_review(app: BlendSmith) -> str:
    app.begin_evidence()
    app.submit_evidence({"front": Path("unused.png")})
    review = _accepted_visual_payload(app)
    app.submit_visual_review(review)
    assert app.status()["state"] == "FINAL_AI_VALIDATION"
    app.ai_accept()
    run = app.status()
    assert run["state"] == "OWNER_REVIEW"
    return review["candidate_sha256"]


def _revision_visual_payload(app: BlendSmith, strategy: str) -> dict:
    payload = _accepted_visual_payload(app)
    payload["verdict"] = "REVISE"
    payload["revision_strategy"] = strategy
    payload["issues"] = [
        {
            "issue_id": "shape-1",
            "severity": "medium",
            "category": "method" if strategy == "METHOD_RECONSIDERATION" else "geometry",
            "view_keys": ["front"],
            "observation": "The current approach produces an artificial result.",
            "likely_cause": "The selected production approach is not appropriate.",
            "recommended_strategy": (
                "Reconsider the method."
                if strategy == "METHOD_RECONSIDERATION"
                else "Refine locally."
            ),
            "regression_risk": "low",
            "acceptance_test": "Result reads naturally after revision.",
        }
    ]
    payload["next_action"] = "reselect method" if strategy == "METHOD_RECONSIDERATION" else "local repair"
    return payload


def test_method_gate_waiting_state_can_checkpoint_without_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app, "UNAVAILABLE")
    app.start()
    checkpointed = app.checkpoint("resume method planning")
    assert checkpointed["state"] == "RESUMABLE"
    resumed = app.resume()
    assert resumed["state"] == "AWAITING_METHOD_PLAN"
    assert resumed["active_candidate_id"] is None


def test_initial_candidate_is_blocked_until_method_selection_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app, "UNAVAILABLE")
    run = app.start()
    assert run["state"] == "AWAITING_METHOD_PLAN"
    candidate = tmp_path / "premature.blend"
    candidate.write_bytes(b"premature")
    with pytest.raises(ContractError):
        app.add_variant(candidate)
    app.submit_method_plan(_method_plan(app))
    assert app.status()["state"] == "AWAITING_METHOD_SELECTION"
    with pytest.raises(ContractError):
        app.add_variant(candidate)


def test_visual_method_mismatch_reenters_method_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": Path("unused.png")})
    app.submit_visual_review(_revision_visual_payload(app, "METHOD_RECONSIDERATION"))
    run = app.status()
    assert run["state"] == "AWAITING_METHOD_SELECTION"
    assert run["iteration"] == 1
    assert run["active_candidate_id"] is None
    assert run["metadata"]["method_selection_round"] == 1
    assert "method_selection_path" not in run["metadata"]

    app.submit_method_selection(_specialized_selection(app, round_id=1))
    candidate = tmp_path / "method-reselected.blend"
    candidate.write_bytes(b"new-method-candidate")
    app.add_variant(candidate)
    run_dir, run = load_current_run(app.layout)
    manifest = verify_candidate_manifest(run_dir / run["metadata"]["candidate_manifest_path"])
    assert manifest["iteration"] == 1
    assert manifest["method_selection_round"] == 1


def test_local_repair_keeps_validated_method_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": Path("unused.png")})
    review = _revision_visual_payload(app, "LOCAL_REPAIR")
    app.submit_visual_review(review)
    run = app.status()
    assert run["state"] == "AWAITING_FIX_PLAN"
    assert run["metadata"]["method_selection_round"] == 0
    selection_path = run["metadata"]["method_selection_path"]

    app.submit_fix_plan(
        {
            "schema_version": 1,
            "run_id": review["run_id"],
            "candidate_id": review["candidate_id"],
            "candidate_sha256": review["candidate_sha256"],
            "primary_issue_ids": ["shape-1"],
            "steps": ["Apply a bounded local geometry refinement."],
            "expected_acceptance_tests": ["The reported shape defect is resolved."],
        }
    )
    run = app.status()
    assert run["state"] == "WORKING"
    assert run["iteration"] == 1
    assert run["metadata"]["method_selection_round"] == 0
    assert run["metadata"]["method_selection_path"] == selection_path

    candidate = tmp_path / "local-repair.blend"
    candidate.write_bytes(b"local-repair")
    app.add_variant(candidate)
    run_dir, run = load_current_run(app.layout)
    manifest = verify_candidate_manifest(run_dir / run["metadata"]["candidate_manifest_path"])
    assert manifest["method_selection_round"] == 0


def test_candidate_is_sha_bound_to_method_selection_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    run_dir, run = load_current_run(app.layout)
    selection_path = run_dir / run["metadata"]["method_selection_path"]
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    payload["selections"][0]["selection_reason"] = "tampered after candidate ingest"
    atomic_write_json(selection_path, payload)
    with pytest.raises(IntegrityError, match="method selection bytes changed|not bound"):
        app.begin_evidence()


def test_sha_bound_accept_publish_then_revision_transaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _start(tmp_path, monkeypatch, gui="UNAVAILABLE")
    accepted_sha = _reach_owner_review(app)

    with pytest.raises(AuthorityError):
        app.owner_accept("0" * 64)
    run = app.owner_accept(accepted_sha)
    assert run["state"] == "CURRENT_FINAL_PINNED"
    assert run["accepted_candidate_sha256"] == accepted_sha

    run = app.publish()
    assert run["state"] == "PUBLISHED"
    assert app.layout.publication_current.is_dir()

    run = app.owner_revise("adjust silhouette")
    assert run["state"] == "WORKING"
    assert not app.layout.publication_current.exists()
    assert run["accepted_candidate_sha256"] is None

    records = app.retention.records().values()
    classes = {item["class"] for item in records}
    assert "PINNED_ACTIVE_CHECKPOINT" in classes
    assert "EPHEMERAL_SUPERSEDED_FINAL" in classes


def test_post_review_candidate_mutation_blocks_ai_accept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _start(tmp_path, monkeypatch, gui="UNAVAILABLE")
    app.begin_evidence()
    app.submit_evidence({"front": Path("unused.png")})
    app.submit_visual_review(_accepted_visual_payload(app))

    run_dir, run = __import__("blendsmith.run_store", fromlist=["load_current_run"]).load_current_run(app.layout)
    manifest_path = run_dir / run["metadata"]["candidate_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_record = next(item for item in manifest["files"] if item["role"] == "candidate")
    candidate_path = manifest_path.parent / "closure" / candidate_record["pinned_path"]
    candidate_path.write_bytes(b"mutated-after-review")

    with pytest.raises(IntegrityError):
        app.ai_accept()


def test_live_gui_available_requires_strict_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _start(tmp_path, monkeypatch, gui="AVAILABLE")
    app.begin_evidence()
    app.submit_evidence({"front": Path("unused.png")})
    review = _accepted_visual_payload(app)
    app.submit_visual_review(review)
    assert app.status()["state"] == "AWAITING_LIVE_GUI_REVIEW"

    bad = {
        "schema_version": 1,
        "run_id": review["run_id"],
        "candidate_id": review["candidate_id"],
        "candidate_sha256": review["candidate_sha256"],
        "status": "PASS",
        "capability_status": "AVAILABLE",
        "blend_path_verified": False,
        "dirty_state_checked": True,
        "viewport_interaction_performed": True,
        "views_observed": ["orbit"],
        "issues": [],
    }
    with pytest.raises(ContractError):
        app.submit_gui_review(bad)
    assert app.status()["state"] == "AWAITING_LIVE_GUI_REVIEW"

    good = {**bad, "blend_path_verified": True}
    app.submit_gui_review(good)
    assert app.status()["state"] == "FINAL_AI_VALIDATION"
    assert app.status()["assurance_level"] == "live_gui_verified"


def test_candidate_variant_budget_is_per_iteration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _start(tmp_path, monkeypatch)
    for index in (2, 3):
        path = tmp_path / f"variant-{index}.blend"
        path.write_bytes(f"variant-{index}".encode())
        app.add_variant(path)
    fourth = tmp_path / "variant-4.blend"
    fourth.write_bytes(b"variant-4")
    with pytest.raises(ContractError):
        app.add_variant(fourth)


def test_candidate_selection_rejects_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _start(tmp_path, monkeypatch)
    with pytest.raises(SafetyError):
        app.select_candidate("../../outside")


def test_candidate_selection_is_locked_after_working(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _start(tmp_path, monkeypatch)
    active = app.status()["active_candidate_id"]
    app.begin_evidence()
    with pytest.raises(ContractError):
        app.select_candidate(active)


def test_acceptance_can_recover_after_sha_locked_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    accepted_sha = _reach_owner_review(app)
    run_dir, run = load_current_run(app.layout)
    run["accepted_candidate_sha256"] = accepted_sha
    save_run(run_dir, run)
    transition(
        run_dir,
        run,
        RunState.HUMAN_ACCEPTED_SHA_LOCKED,
        reason="simulate interruption after owner decision",
    )
    recovered = app.owner_accept(accepted_sha)
    assert recovered["state"] == "CURRENT_FINAL_PINNED"


def test_publication_can_recover_after_current_swap_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    accepted_sha = _reach_owner_review(app)
    app.owner_accept(accepted_sha)
    run_dir, run = load_current_run(app.layout)
    transition(run_dir, run, RunState.PUBLICATION_STAGING, reason="simulate staging interruption")
    manifest_path = run_dir / run["metadata"]["candidate_manifest_path"]
    publish_verified(app.layout, run=run, candidate_manifest_path=manifest_path)

    recovered = app.publish()
    assert recovered["state"] == "PUBLISHED"
    assert app.layout.publication_current.is_dir()


def test_resume_recovers_interrupted_checkpoint_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    run_dir, run = load_current_run(app.layout)
    run["resume_state"] = RunState.WORKING.value
    save_run(run_dir, run)
    transition(run_dir, run, RunState.CHECKPOINTING, reason="simulate checkpoint interruption")

    recovered = app.resume()
    assert recovered["state"] == "WORKING"
    assert recovered["active_checkpoint_id"] is not None


def test_checkpoint_copies_only_manifested_candidate_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    run_dir, run = __import__("blendsmith.run_store", fromlist=["load_current_run"]).load_current_run(app.layout)
    manifest_path = run_dir / run["metadata"]["candidate_manifest_path"]
    untracked = manifest_path.parent / "untracked-secret.txt"
    untracked.write_text("must not enter checkpoint", encoding="utf-8")

    run = app.checkpoint("resume")
    checkpoint_path = run_dir / run["metadata"]["active_checkpoint_path"]
    snapshot_root = checkpoint_path.parent / "candidate_snapshot"
    assert not (snapshot_root / "untracked-secret.txt").exists()


def test_validated_method_plan_mutation_before_selection_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app, "UNAVAILABLE")
    app.start()
    app.submit_method_plan(_method_plan(app))
    run_dir, run = load_current_run(app.layout)
    plan_path = run_dir / run["metadata"]["method_plan_path"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["work_units"][0]["requirements"].append("tampered")
    atomic_write_json(plan_path, plan)

    with pytest.raises(IntegrityError, match="method plan bytes changed"):
        app.submit_method_selection(_specialized_selection(app))


def test_validated_method_selection_mutation_before_candidate_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app, "UNAVAILABLE")
    app.start()
    app.submit_method_plan(_method_plan(app))
    app.submit_method_selection(_specialized_selection(app))
    run_dir, run = load_current_run(app.layout)
    selection_path = run_dir / run["metadata"]["method_selection_path"]
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["selections"][0]["selection_reason"] = "tampered after validation"
    atomic_write_json(selection_path, selection)

    candidate = tmp_path / "tampered-selection.blend"
    candidate.write_bytes(b"candidate")
    with pytest.raises(IntegrityError, match="method selection bytes changed"):
        app.add_variant(candidate)


def test_method_metadata_path_swap_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    run_dir, run = load_current_run(app.layout)
    selection_path = run_dir / run["metadata"]["method_selection_path"]
    alternate = run_dir / "methods" / "alternate-selection.json"
    atomic_write_json(alternate, json.loads(selection_path.read_text(encoding="utf-8")))
    run["metadata"]["method_selection_path"] = alternate.relative_to(run_dir).as_posix()
    save_run(run_dir, run)

    candidate = tmp_path / "path-swap.blend"
    candidate.write_bytes(b"path-swap")
    with pytest.raises(IntegrityError, match="authoritative|active selection round"):
        app.add_variant(candidate)


def test_method_plan_tamper_after_candidate_blocks_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    run_dir, run = load_current_run(app.layout)
    plan_path = run_dir / run["metadata"]["method_plan_path"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["work_units"][0]["notes"] = ["tampered after candidate ingest"]
    atomic_write_json(plan_path, plan)

    with pytest.raises((ContractError, IntegrityError), match="plan_sha256|method plan bytes changed"):
        app.begin_evidence()


def test_checkpoint_restores_method_authority_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    run_dir, _ = load_current_run(app.layout)
    checkpointed = app.checkpoint("restore method receipts")
    checkpoint_path = run_dir / checkpointed["metadata"]["active_checkpoint_path"]
    checkpoint = verify_checkpoint(checkpoint_path)

    plan_path = run_dir / "methods" / "method-plan.json"
    selection_path = run_dir / "methods" / "method-selection-r0.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["work_units"][0]["notes"] = ["post-checkpoint mutation"]
    atomic_write_json(plan_path, plan)
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["selections"][0]["selection_reason"] = "post-checkpoint mutation"
    atomic_write_json(selection_path, selection)

    resumed = app.resume()
    assert resumed["state"] == "WORKING"
    assert sha256_file(plan_path) == checkpoint["method_plan_sha256"]
    assert sha256_file(selection_path) == checkpoint["method_selection_sha256"]
    app.begin_evidence()
    assert app.status()["state"] == "RENDERING_EVIDENCE"


def test_checkpoint_method_snapshot_tamper_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    run_dir, _ = load_current_run(app.layout)
    checkpointed = app.checkpoint("verify method snapshot")
    checkpoint_path = run_dir / checkpointed["metadata"]["active_checkpoint_path"]
    checkpoint = verify_checkpoint(checkpoint_path)
    snapshot = checkpoint_path.parent / checkpoint["method_selection_snapshot_path"]
    snapshot.write_text(snapshot.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(IntegrityError, match="snapshot SHA mismatch"):
        app.resume()


def test_method_reconsideration_checkpoint_preserves_selection_round_without_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _start(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": Path("unused.png")})
    app.submit_visual_review(_revision_visual_payload(app, "METHOD_RECONSIDERATION"))
    assert app.status()["metadata"]["method_selection_round"] == 1
    checkpointed = app.checkpoint("resume method reselection")
    assert checkpointed["state"] == "RESUMABLE"

    resumed = app.resume()
    assert resumed["state"] == "AWAITING_METHOD_SELECTION"
    assert resumed["metadata"]["method_selection_round"] == 1
    assert "method_selection_path" not in resumed["metadata"]
    assert resumed["metadata"]["method_plan_id"] == "plan-main"
