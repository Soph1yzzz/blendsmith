from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .closure import verify_candidate_manifest
from .contracts import validate_contract
from .errors import IntegrityError
from .hashing import sha256_file
from .paths import atomic_write_json, ensure_within
from .timeutil import iso_now


def _copy_contract_snapshot(
    run_dir: Path,
    checkpoint_root: Path,
    *,
    source: Path | None,
    destination_name: str,
    contract_name: str,
) -> tuple[str | None, str | None]:
    if source is None:
        return None, None
    source = ensure_within(run_dir, source)
    if not source.is_file() or source.is_symlink():
        raise IntegrityError(f"Checkpoint contract source is missing or unsafe: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    validate_contract(contract_name, payload)
    source_sha = sha256_file(source)
    destination = ensure_within(
        checkpoint_root,
        checkpoint_root / "method_snapshot" / destination_name,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256_file(destination) != source_sha:
        raise IntegrityError(f"Checkpoint contract copy changed bytes: {source}")
    copied = json.loads(destination.read_text(encoding="utf-8"))
    validate_contract(contract_name, copied)
    return destination.relative_to(checkpoint_root).as_posix(), source_sha


def materialize_checkpoint(
    run_dir: Path,
    *,
    run: dict[str, Any],
    candidate_manifest_path: Path | None,
    method_plan_path: Path | None = None,
    method_selection_path: Path | None = None,
    resume_state: str,
    next_action: str,
    review_path: str | None = None,
    fix_plan_path: str | None = None,
    unresolved_issue_ids: list[str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if method_selection_path is not None and method_plan_path is None:
        raise IntegrityError("Checkpoint method selection requires its method plan")

    checkpoint_id = f"cp-{uuid.uuid4().hex[:12]}"
    checkpoint_root = ensure_within(run_dir, Path(run_dir) / "checkpoints" / checkpoint_id)
    checkpoint_root.mkdir(parents=True, exist_ok=False)

    method_plan_snapshot_path, method_plan_sha256 = _copy_contract_snapshot(
        run_dir,
        checkpoint_root,
        source=method_plan_path,
        destination_name="method-plan.json",
        contract_name="method_plan",
    )
    method_selection_snapshot_path, method_selection_sha256 = _copy_contract_snapshot(
        run_dir,
        checkpoint_root,
        source=method_selection_path,
        destination_name="method-selection.json",
        contract_name="method_selection",
    )

    if method_selection_snapshot_path is not None:
        plan_snapshot = ensure_within(
            checkpoint_root,
            checkpoint_root / str(method_plan_snapshot_path),
        )
        selection_snapshot = ensure_within(
            checkpoint_root,
            checkpoint_root / method_selection_snapshot_path,
        )
        plan = json.loads(plan_snapshot.read_text(encoding="utf-8"))
        selection = json.loads(selection_snapshot.read_text(encoding="utf-8"))
        if selection["plan_id"] != plan["plan_id"]:
            raise IntegrityError("Checkpoint method selection references a different method plan")
        if selection["plan_sha256"] != method_plan_sha256:
            raise IntegrityError("Checkpoint method selection does not bind the copied method plan")

    candidate_id: str | None = None
    candidate_sha256: str | None = None
    closure_sha256: str | None = None
    copied_manifest_relative: str | None = None

    if candidate_manifest_path is not None:
        source_manifest = verify_candidate_manifest(candidate_manifest_path)
        source_candidate_root = Path(candidate_manifest_path).parent
        copied_candidate_root = checkpoint_root / "candidate_snapshot"
        copied_closure_root = copied_candidate_root / "closure"
        copied_closure_root.mkdir(parents=True, exist_ok=False)
        for record in source_manifest["files"]:
            source = ensure_within(
                source_candidate_root / "closure",
                source_candidate_root / "closure" / record["pinned_path"],
            )
            destination = ensure_within(
                copied_closure_root,
                copied_closure_root / record["pinned_path"],
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        copied_manifest_path = copied_candidate_root / "candidate.manifest.json"
        atomic_write_json(copied_manifest_path, source_manifest)
        copied_manifest = verify_candidate_manifest(copied_manifest_path)

        if copied_manifest["candidate_sha256"] != source_manifest["candidate_sha256"]:
            raise IntegrityError("Checkpoint candidate SHA changed during snapshot")
        if copied_manifest["closure_sha256"] != source_manifest["closure_sha256"]:
            raise IntegrityError("Checkpoint closure digest changed during snapshot")
        if method_selection_sha256 is None:
            raise IntegrityError("Checkpoint candidate requires a method-selection snapshot")
        if copied_manifest["method_selection_sha256"] != method_selection_sha256:
            raise IntegrityError("Checkpoint candidate is not bound to the copied method selection")
        candidate_id = copied_manifest["candidate_id"]
        candidate_sha256 = copied_manifest["candidate_sha256"]
        closure_sha256 = copied_manifest["closure_sha256"]
        copied_manifest_relative = copied_manifest_path.relative_to(checkpoint_root).as_posix()

    payload = {
        "schema_version": 1,
        "checkpoint_id": checkpoint_id,
        "run_id": run["run_id"],
        "created_at": iso_now(),
        "resume_state": resume_state,
        "iteration": run["iteration"],
        "method_selection_round": int(run["metadata"].get("method_selection_round", 0)),
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "closure_sha256": closure_sha256,
        "candidate_manifest_path": copied_manifest_relative,
        "method_plan_snapshot_path": method_plan_snapshot_path,
        "method_plan_sha256": method_plan_sha256,
        "method_selection_snapshot_path": method_selection_snapshot_path,
        "method_selection_sha256": method_selection_sha256,
        "review_path": review_path,
        "fix_plan_path": fix_plan_path,
        "unresolved_issue_ids": unresolved_issue_ids or [],
        "next_action": next_action,
    }
    validate_contract("checkpoint", payload)
    checkpoint_path = checkpoint_root / "checkpoint.json"
    atomic_write_json(checkpoint_path, payload)
    return checkpoint_path, payload


def _verify_method_snapshot(
    root: Path,
    *,
    relative_path: str | None,
    expected_sha: str | None,
    contract_name: str,
) -> dict[str, Any] | None:
    if relative_path is None:
        return None
    path = ensure_within(root, root / relative_path)
    if not path.is_file() or path.is_symlink():
        raise IntegrityError(f"Checkpoint {contract_name} snapshot is missing or unsafe")
    if sha256_file(path) != expected_sha:
        raise IntegrityError(f"Checkpoint {contract_name} snapshot SHA mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_contract(contract_name, payload)
    return payload


def verify_checkpoint(checkpoint_path: Path) -> dict[str, Any]:
    checkpoint_path = Path(checkpoint_path)
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    validate_contract("checkpoint", payload)
    root = checkpoint_path.parent

    plan = _verify_method_snapshot(
        root,
        relative_path=payload["method_plan_snapshot_path"],
        expected_sha=payload["method_plan_sha256"],
        contract_name="method_plan",
    )
    selection = _verify_method_snapshot(
        root,
        relative_path=payload["method_selection_snapshot_path"],
        expected_sha=payload["method_selection_sha256"],
        contract_name="method_selection",
    )
    if plan is not None and plan["run_id"] != payload["run_id"]:
        raise IntegrityError("Checkpoint method plan belongs to a different run")
    if selection is not None:
        if plan is None:
            raise IntegrityError("Checkpoint method selection has no method plan")
        if selection["run_id"] != payload["run_id"]:
            raise IntegrityError("Checkpoint method selection belongs to a different run")
        if selection["plan_id"] != plan["plan_id"]:
            raise IntegrityError("Checkpoint method plan/selection identity mismatch")
        if selection["plan_sha256"] != payload["method_plan_sha256"]:
            raise IntegrityError("Checkpoint method selection plan SHA mismatch")
        if selection["selection_round"] != payload["method_selection_round"]:
            raise IntegrityError("Checkpoint method-selection round mismatch")

    if payload["candidate_manifest_path"] is not None:
        manifest_path = ensure_within(root, root / payload["candidate_manifest_path"])
        manifest = verify_candidate_manifest(manifest_path)
        if manifest["run_id"] != payload["run_id"]:
            raise IntegrityError("Checkpoint candidate belongs to a different run")
        if manifest["candidate_sha256"] != payload["candidate_sha256"]:
            raise IntegrityError("Checkpoint candidate SHA mismatch")
        if manifest["closure_sha256"] != payload["closure_sha256"]:
            raise IntegrityError("Checkpoint closure digest mismatch")
        if selection is None or manifest["method_selection_sha256"] != payload["method_selection_sha256"]:
            raise IntegrityError("Checkpoint candidate method-selection binding mismatch")
        if manifest["method_plan_id"] != selection["plan_id"]:
            raise IntegrityError("Checkpoint candidate method-plan identity mismatch")
        if manifest["method_selection_round"] != payload["method_selection_round"]:
            raise IntegrityError("Checkpoint candidate method-selection round mismatch")
    return payload


def _restore_snapshot_file(source: Path, destination: Path, expected_sha: str) -> None:
    if not source.is_file() or source.is_symlink():
        raise IntegrityError(f"Checkpoint restore source is missing or unsafe: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copy2(source, tmp)
        if sha256_file(tmp) != expected_sha:
            raise IntegrityError(f"Checkpoint restore copy failed verification: {source}")
        os.replace(tmp, destination)
        if sha256_file(destination) != expected_sha:
            raise IntegrityError(f"Checkpoint restored bytes failed verification: {destination}")
    finally:
        if tmp.exists():
            tmp.unlink()


def restore_checkpoint_methods(checkpoint_path: Path, run_dir: Path) -> dict[str, Any]:
    checkpoint_path = Path(checkpoint_path)
    payload = verify_checkpoint(checkpoint_path)
    root = checkpoint_path.parent
    methods_root = ensure_within(run_dir, Path(run_dir) / "methods")
    result: dict[str, Any] = {
        "method_plan_path": None,
        "method_plan_id": None,
        "method_plan_sha256": None,
        "method_selection_path": None,
        "method_selection_round": None,
        "method_selection_sha256": None,
    }

    if payload["method_plan_snapshot_path"] is not None:
        source = ensure_within(root, root / payload["method_plan_snapshot_path"])
        destination = ensure_within(run_dir, methods_root / "method-plan.json")
        _restore_snapshot_file(source, destination, payload["method_plan_sha256"])
        plan = json.loads(destination.read_text(encoding="utf-8"))
        validate_contract("method_plan", plan)
        result["method_plan_path"] = destination.relative_to(run_dir).as_posix()
        result["method_plan_id"] = plan["plan_id"]
        result["method_plan_sha256"] = payload["method_plan_sha256"]

    if payload["method_selection_snapshot_path"] is not None:
        source = ensure_within(root, root / payload["method_selection_snapshot_path"])
        selection_snapshot = json.loads(source.read_text(encoding="utf-8"))
        validate_contract("method_selection", selection_snapshot)
        round_id = int(selection_snapshot["selection_round"])
        destination = ensure_within(
            run_dir,
            methods_root / f"method-selection-r{round_id}.json",
        )
        _restore_snapshot_file(source, destination, payload["method_selection_sha256"])
        result["method_selection_path"] = destination.relative_to(run_dir).as_posix()
        result["method_selection_round"] = round_id
        result["method_selection_sha256"] = payload["method_selection_sha256"]
    return result
