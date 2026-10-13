from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from test_lifecycle import (
    _accepted_visual_payload,
    _capabilities,
    _domain_not_required,
    _fake_evidence,
    _method_plan,
    _specialized_selection,
)

from blendsmith.errors import ContractError, IntegrityError
from blendsmith.hashing import sha256_file
from blendsmith.orchestrator import BlendSmith
from blendsmith.references import pin_reference, verify_references
from blendsmith.run_store import load_current_run
from blendsmith.scene_audit import inspect_saved_blend


def _image(path: Path) -> Path:
    Image.new("RGB", (8, 8), (20, 70, 120)).save(path)
    return path


def _guided_working_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BlendSmith:
    _fake_evidence(monkeypatch)
    app = BlendSmith.init(tmp_path / "project")
    _capabilities(app, "UNAVAILABLE")
    app.start()
    app.add_reference("main-photo", _image(tmp_path / "photo.png"))
    _domain_not_required(app)
    app.submit_method_plan(_method_plan(app))
    app.submit_method_selection(_specialized_selection(app))
    candidate = tmp_path / "scene.blend"
    candidate.write_bytes(b"fake-test-scene")
    app.add_variant(candidate)
    return app


def test_reference_image_receipt_fails_closed_on_tamper(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source = _image(tmp_path / "ref.png")
    manifest = pin_reference(run_dir, "reference-1", source)
    indexed_sha = sha256_file(run_dir / "references" / "index.json")
    assert verify_references(run_dir, indexed_sha) == manifest
    with pytest.raises(ContractError, match="already exists"):
        pin_reference(run_dir, "reference-1", source)
    (run_dir / "references" / "reference-1.png").write_bytes(b"tampered")
    with pytest.raises(IntegrityError, match="digest mismatch"):
        verify_references(run_dir, indexed_sha)


def test_reference_registration_locks_after_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _guided_working_app(tmp_path, monkeypatch)
    run_dir, run = load_current_run(app.layout)
    assert app.reference_status()["references"][0]["reference_id"] == "main-photo"
    candidate_manifest = json.loads((run_dir / run["metadata"]["candidate_manifest_path"]).read_text())
    assert len(candidate_manifest["files"]) == 2
    assert {x["role"] for x in candidate_manifest["files"]} == {"candidate", "dependency"}
    with pytest.raises(ContractError, match="before the first candidate"):
        app.add_reference("late", _image(tmp_path / "late.png"))
    with pytest.raises(IntegrityError, match="index changed"):
        (run_dir / "references" / "index.json").write_text('{"schema_version":1,"images":[]}')
        app.reference_status()


def test_accept_requires_real_reference_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _guided_working_app(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": tmp_path / "dummy.png"})
    template = app.contract_template("visual_review")
    assert template["verdict"] == "BLOCKED"
    assert template["opened_evidence"] == []
    assert template["reference_comparisons"][0]["fidelity"] == "MISMATCH"
    payload = _accepted_visual_payload(app)
    with pytest.raises(ContractError, match="every pinned reference"):
        app.submit_visual_review(payload)
    reference = app.reference_status()["references"][0]
    payload["reference_comparisons"] = [{
        "reference_id": "main-photo",
        "reference_sha256": reference["sha256"],
        "view_keys": ["front"],
        "observations": ["Front framing resembles the photographic reference."],
        "fidelity": "MATCH",
    }]
    payload["reference_comparisons"][0]["reference_sha256"] = "0" * 64
    with pytest.raises(IntegrityError, match="stale SHA"):
        app.submit_visual_review(payload)
    payload["reference_comparisons"][0]["reference_sha256"] = reference["sha256"]
    payload["reference_comparisons"][0]["view_keys"] = ["rear"]
    with pytest.raises(ContractError, match="opened render"):
        app.submit_visual_review(payload)
    payload["reference_comparisons"][0]["view_keys"] = ["front"]
    payload["reference_comparisons"][0]["fidelity"] = "MISMATCH"
    with pytest.raises(ContractError, match="mismatch"):
        app.submit_visual_review(payload)
    payload["reference_comparisons"][0]["fidelity"] = "MATCH"
    assert app.submit_visual_review(payload)["state"] == "FINAL_AI_VALIDATION"

    captured: list[tuple[Path, list[dict]]] = []

    def probe(executable: str, blend_file: Path, references: list[dict]) -> dict:
        assert executable == "test-blender"
        captured.append((blend_file, references))
        return {"scene_loaded": True, "missing_assets": [], "missing_references": []}

    monkeypatch.setattr("blendsmith.orchestrator.inspect_saved_blend", probe)
    monkeypatch.setattr("blendsmith.orchestrator.latest_snapshot", lambda layout: {
        "capabilities": {"blender_backend": {"details": {"executable": "test-blender"}},
                         "live_blender_gui_review": {"status": "UNAVAILABLE"}}
    })
    run = app.ai_accept()
    assert run["state"] == "OWNER_REVIEW"
    assert captured[0][0].is_file()
    assert captured[0][1][0]["reference_id"] == "main-photo"
    assert app.owner_accept(payload["candidate_sha256"])["state"] == "CURRENT_FINAL_PINNED"


def test_acceptance_receipt_tamper_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _guided_working_app(tmp_path, monkeypatch)
    app.begin_evidence()
    app.submit_evidence({"front": tmp_path / "unused.png"})
    review = _accepted_visual_payload(app)
    ref = app.reference_status()["references"][0]
    review["reference_comparisons"] = [{
        "reference_id": ref["reference_id"],
        "reference_sha256": ref["sha256"],
        "view_keys": ["front"],
        "observations": ["Reference camera framing was compared with the final render."],
        "fidelity": "MATCH",
    }]
    app.submit_visual_review(review)
    monkeypatch.setattr("blendsmith.orchestrator.inspect_saved_blend", lambda *args: {
        "scene_loaded": True, "missing_assets": [], "missing_references": []
    })
    monkeypatch.setattr("blendsmith.orchestrator.latest_snapshot", lambda layout: {
        "capabilities": {"blender_backend": {"details": {"executable": "test-blender"}},
                         "live_blender_gui_review": {"status": "UNAVAILABLE"}}
    })
    app.ai_accept()
    run_dir, run = load_current_run(app.layout)
    (run_dir / run["metadata"]["scene_audit_path"]).write_text("{}")
    with pytest.raises(IntegrityError, match="scene-audit receipt changed"):
        app.owner_accept(review["candidate_sha256"])


def test_scene_audit_fails_if_blender_reports_missing_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from subprocess import CompletedProcess

    def run(*args, **kwargs):
        result = {"scene_loaded": True, "images_inspected": 0,
                  "missing_assets": [], "missing_references": ["main-photo"]}
        return CompletedProcess(args[0], 0, "BLENDSMITH_SCENE_AUDIT:" + json.dumps(result), "")

    monkeypatch.setattr("blendsmith.scene_audit.subprocess.run", run)
    with pytest.raises(IntegrityError, match="missing image data"):
        inspect_saved_blend(
            "blender", tmp_path / "scene.blend",
            [{"reference_id": "main-photo", "sha256": "a" * 64, "require_in_blend": True}],
        )
