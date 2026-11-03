"""Quality assessment, best-so-far preservation, and non-regression acceptance gates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .capabilities import latest_snapshot
from .closure import verify_candidate_manifest
from .errors import CapabilityError, ContractError, IntegrityError
from .evidence import verify_evidence_bundle
from .geometry_audit import inspect_contact_proximity
from .hashing import sha256_file
from .paths import atomic_write_json, ensure_within
from .quality import validate_assessment
from .run_store import load_current_run, save_run
from .state_machine import RunState


def assess(app: Any, payload: dict[str, Any]) -> dict[str, Any]:
    run_dir, run = load_current_run(app.layout)
    if RunState(run["state"]) != RunState.AWAITING_VISUAL_REVIEW:
        raise ContractError("Quality assessment requires submitted render evidence")
    targets = app._verified_quality_targets(run_dir, run)
    if not targets:
        raise ContractError("No reference quality targets are registered")
    manifest_path = app._manifest_path(run_dir, run)
    manifest = verify_candidate_manifest(manifest_path)
    bundle = verify_evidence_bundle(run_dir, app._evidence_path(run_dir, run))
    best = app._verified_quality_best(run_dir, run)
    validate_assessment(
        payload, run=run, candidate=manifest, targets=targets,
        targets_sha256=run["metadata"]["quality_targets_sha256"],
        evidence_views={item["key"] for item in bundle["views"]},
        best_sha256=best["candidate_sha256"] if best else None,
    )
    receipt_path = ensure_within(
        run_dir, run_dir / "reviews" / f"quality-i{run['iteration']}-{manifest['candidate_id']}.json"
    )
    if receipt_path.exists():
        raise ContractError("This candidate already has an immutable quality assessment")
    geometry_results: list[dict[str, Any]] = []
    if targets["geometry_checks"]:
        snapshot = latest_snapshot(app.layout)
        executable = (snapshot or {}).get("capabilities", {}).get("blender_backend", {}).get(
            "details", {}
        ).get("executable")
        if not executable:
            raise CapabilityError("Geometry checks require an explicitly available Blender executable")
        candidate_record = next(item for item in manifest["files"] if item["role"] == "candidate")
        scene_path = manifest_path.parent / "closure" / candidate_record["pinned_path"]
        geometry_results = inspect_contact_proximity(executable, scene_path, targets["geometry_checks"])
    if payload["decision"] == "PROMOTE" and any(item["status"] != "PASS" for item in geometry_results):
        raise ContractError("A candidate with failed contact proximity checks cannot become the best")
    receipt = {"assessment": payload, "geometry_results": geometry_results}
    atomic_write_json(receipt_path, receipt)
    run["metadata"]["quality_assessment_path"] = receipt_path.relative_to(run_dir).as_posix()
    run["metadata"]["quality_assessment_sha256"] = sha256_file(receipt_path)
    if payload["decision"] == "PROMOTE":
        record = app.retention.register(manifest_path.parent, "PINNED_QUALITY_BEST")
        if best:
            app.retention.transition(
                best["retention_id"], "EPHEMERAL",
                ttl_hours=app.config["storage"]["ephemeral_ttl_hours"],
                replaced_by=manifest["candidate_id"],
            )
        run["metadata"]["quality_best"] = {
            "candidate_id": manifest["candidate_id"],
            "candidate_sha256": manifest["candidate_sha256"],
            "manifest_path": manifest_path.relative_to(run_dir).as_posix(),
            "assessment_path": receipt_path.relative_to(run_dir).as_posix(),
            "assessment_sha256": sha256_file(receipt_path),
            "retention_id": record["record_id"],
        }
    save_run(run_dir, run)
    return {
        "run_id": run["run_id"],
        "candidate_sha256": manifest["candidate_sha256"],
        "decision": payload["decision"],
        "geometry_results": geometry_results,
        "best_candidate_sha256": run["metadata"].get("quality_best", {}).get("candidate_sha256"),
    }


def require_ready(app: Any, run_dir: Path, run: dict[str, Any]) -> None:
    if run["metadata"].get("quality_loop_version") != 1 or not app._verified_references(run_dir, run):
        return
    targets = app._verified_quality_targets(run_dir, run)
    if not targets:
        raise ContractError("Reference-guided acceptance requires registered feature targets")
    path_text = run["metadata"].get("quality_assessment_path")
    expected_sha = run["metadata"].get("quality_assessment_sha256")
    if not path_text or not expected_sha:
        raise ContractError("Reference-guided acceptance requires a quality assessment")
    path = ensure_within(run_dir, run_dir / path_text)
    if not path.is_file() or sha256_file(path) != expected_sha:
        raise IntegrityError("Active quality assessment was modified or removed")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    assessment = receipt["assessment"]
    manifest = verify_candidate_manifest(app._manifest_path(run_dir, run))
    best = app._verified_quality_best(run_dir, run)
    if not best or best["candidate_id"] != manifest["candidate_id"]:
        raise ContractError("The active candidate is not the best assessed candidate")
    if assessment["candidate_sha256"] != manifest["candidate_sha256"]:
        raise IntegrityError("Quality assessment is bound to another candidate")
    if assessment["targets_sha256"] != run["metadata"]["quality_targets_sha256"]:
        raise IntegrityError("Quality assessment is bound to stale reference features")
    if assessment["decision"] != "PROMOTE":
        raise ContractError("Unpromoted quality assessment cannot be accepted")
    if any(item["fidelity"] == "MISMATCH" for item in assessment["target_results"]):
        raise ContractError("Unresolved part-level reference mismatches block acceptance")
    by_target = {item["target_id"]: item for item in targets["targets"]}
    for item in assessment["target_results"]:
        if by_target[item["target_id"]]["priority"] == "CRITICAL" and item["fidelity"] != "MATCH":
            raise ContractError("Critical reference features must match before acceptance")
    checks = receipt["geometry_results"]
    if len(checks) != len(targets["geometry_checks"]) or any(item["status"] != "PASS" for item in checks):
        raise ContractError("Required independent geometry checks are incomplete or failed")


def restore_best(app: Any) -> dict[str, Any]:
    run_dir, run = load_current_run(app.layout)
    if RunState(run["state"]) != RunState.WORKING:
        raise ContractError("Best candidate can be restored only while WORKING")
    best = app._verified_quality_best(run_dir, run)
    if not best:
        raise ContractError("No assessed best candidate is available for restoration")
    app._validate_current_method_selection(run_dir, run)
    source_manifest_path = ensure_within(run_dir, run_dir / best["manifest_path"])
    manifest = verify_candidate_manifest(source_manifest_path)
    current_method_sha = app._current_method_selection_identity(run_dir, run)[2]
    if manifest["method_selection_sha256"] != current_method_sha:
        raise ContractError("Best candidate used a different method selection; revalidate before restoration")
    existing = [
        path for path in (run_dir / "candidates").glob("*/candidate.manifest.json")
        if json.loads(path.read_text(encoding="utf-8")).get("iteration") == run["iteration"]
    ]
    variant_index = len(existing) + 1
    if variant_index > app.config["qa"]["max_variants_per_iteration"]:
        raise ContractError("Best restore would exceed the active iteration candidate budget")
    closure_root = source_manifest_path.parent / "closure"
    candidate_record = next(item for item in manifest["files"] if item["role"] == "candidate")
    dependencies = [
        closure_root / item["pinned_path"] for item in manifest["files"] if item["role"] == "dependency"
    ]
    app._materialize_active_candidate(
        run_dir, run, candidate=closure_root / candidate_record["pinned_path"],
        dependencies=dependencies, iteration=run["iteration"], variant_index=variant_index,
    )
    save_run(run_dir, run)
    return run
