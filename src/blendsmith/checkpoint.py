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
    snapshot_dir: str = "method_snapshot",
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
        checkpoint_root / snapshot_dir / destination_name,
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
    domain_research_path: Path | None = None,
    domain_knowledge_path: Path | None = None,
    domain_practice_path: Path | None = None,
    method_plan_path: Path | None = None,
    method_selection_path: Path | None = None,
    resume_state: str,
    next_action: str,
    review_path: str | None = None,
    fix_plan_path: str | None = None,
    unresolved_issue_ids: list[str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if domain_knowledge_path is not None and domain_research_path is None:
        raise IntegrityError("Checkpoint domain knowledge requires its research receipt")
    if domain_practice_path is not None and domain_knowledge_path is None:
        raise IntegrityError("Checkpoint domain practice requires its knowledge receipt")
    if method_selection_path is not None and method_plan_path is None:
        raise IntegrityError("Checkpoint method selection requires its method plan")

    checkpoint_id = f"cp-{uuid.uuid4().hex[:12]}"
    checkpoint_root = ensure_within(run_dir, Path(run_dir) / "checkpoints" / checkpoint_id)
    checkpoint_root.mkdir(parents=True, exist_ok=False)

    domain_research_snapshot_path, domain_research_sha256 = _copy_contract_snapshot(
        run_dir,
        checkpoint_root,
        source=domain_research_path,
        destination_name="domain-research.json",
        contract_name="domain_research",
        snapshot_dir="domain_snapshot",
    )
    domain_knowledge_snapshot_path, domain_knowledge_sha256 = _copy_contract_snapshot(
        run_dir,
        checkpoint_root,
        source=domain_knowledge_path,
        destination_name="domain-knowledge.json",
        contract_name="domain_knowledge",
        snapshot_dir="domain_snapshot",
    )
    domain_practice_snapshot_path, domain_practice_sha256 = _copy_contract_snapshot(
        run_dir,
        checkpoint_root,
        source=domain_practice_path,
        destination_name="domain-practice.json",
        contract_name="domain_practice",
        snapshot_dir="domain_snapshot",
    )

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

    domain_research = None
    domain_knowledge = None
    domain_practice = None
    if domain_research_snapshot_path is not None:
        research_snapshot = ensure_within(checkpoint_root, checkpoint_root / domain_research_snapshot_path)
        domain_research = json.loads(research_snapshot.read_text(encoding="utf-8"))
        if domain_research["run_id"] != run["run_id"]:
            raise IntegrityError("Checkpoint domain research belongs to a different run")
    if domain_knowledge_snapshot_path is not None:
        if domain_research is None or domain_research_sha256 is None:
            raise IntegrityError("Checkpoint domain knowledge has no domain research")
        knowledge_snapshot = ensure_within(checkpoint_root, checkpoint_root / domain_knowledge_snapshot_path)
        domain_knowledge = json.loads(knowledge_snapshot.read_text(encoding="utf-8"))
        if domain_knowledge["run_id"] != run["run_id"]:
            raise IntegrityError("Checkpoint domain knowledge belongs to a different run")
        if domain_knowledge["research_sha256"] != domain_research_sha256:
            raise IntegrityError("Checkpoint domain knowledge does not bind the copied research receipt")
    if domain_practice_snapshot_path is not None:
        if domain_knowledge is None or domain_knowledge_sha256 is None:
            raise IntegrityError("Checkpoint domain practice has no domain knowledge")
        practice_snapshot = ensure_within(checkpoint_root, checkpoint_root / domain_practice_snapshot_path)
        domain_practice = json.loads(practice_snapshot.read_text(encoding="utf-8"))
        if domain_practice["run_id"] != run["run_id"]:
            raise IntegrityError("Checkpoint domain practice belongs to a different run")
        if domain_practice["knowledge_sha256"] != domain_knowledge_sha256:
            raise IntegrityError("Checkpoint domain practice does not bind the copied knowledge receipt")

    if method_plan_snapshot_path is not None and domain_research is not None:
        plan_snapshot = ensure_within(checkpoint_root, checkpoint_root / method_plan_snapshot_path)
        plan_for_domain = json.loads(plan_snapshot.read_text(encoding="utf-8"))
        expected_practice_sha = domain_practice_sha256
        if plan_for_domain.get("domain_practice_sha256") != expected_practice_sha:
            raise IntegrityError("Checkpoint method plan does not bind the copied domain practice receipt")
        if domain_research["decision"] == "RESEARCH_REQUIRED" and domain_practice is None:
            raise IntegrityError("Checkpoint researched method plan is missing domain practice authority")
        if domain_research["decision"] == "NOT_REQUIRED" and domain_practice is not None:
            raise IntegrityError("Checkpoint NOT_REQUIRED research unexpectedly has domain practice authority")

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
        "domain_research_revision": run["metadata"].get("domain_research_revision"),
        "domain_research_snapshot_path": domain_research_snapshot_path,
        "domain_research_sha256": domain_research_sha256,
        "domain_knowledge_snapshot_path": domain_knowledge_snapshot_path,
        "domain_knowledge_sha256": domain_knowledge_sha256,
        "domain_practice_snapshot_path": domain_practice_snapshot_path,
        "domain_practice_sha256": domain_practice_sha256,
        "method_plan_revision": int(run["metadata"].get("method_plan_revision", 0)),
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

    research = _verify_method_snapshot(
        root,
        relative_path=payload.get("domain_research_snapshot_path"),
        expected_sha=payload.get("domain_research_sha256"),
        contract_name="domain_research",
    )
    knowledge = _verify_method_snapshot(
        root,
        relative_path=payload.get("domain_knowledge_snapshot_path"),
        expected_sha=payload.get("domain_knowledge_sha256"),
        contract_name="domain_knowledge",
    )
    practice = _verify_method_snapshot(
        root,
        relative_path=payload.get("domain_practice_snapshot_path"),
        expected_sha=payload.get("domain_practice_sha256"),
        contract_name="domain_practice",
    )
    if research is not None:
        if research["run_id"] != payload["run_id"]:
            raise IntegrityError("Checkpoint domain research belongs to a different run")
        if research["revision"] != payload.get("domain_research_revision"):
            raise IntegrityError("Checkpoint domain-research revision mismatch")
    if knowledge is not None:
        if research is None:
            raise IntegrityError("Checkpoint domain knowledge has no research receipt")
        if knowledge["run_id"] != payload["run_id"]:
            raise IntegrityError("Checkpoint domain knowledge belongs to a different run")
        if knowledge["research_sha256"] != payload.get("domain_research_sha256"):
            raise IntegrityError("Checkpoint domain knowledge research SHA mismatch")
    if practice is not None:
        if knowledge is None:
            raise IntegrityError("Checkpoint domain practice has no knowledge receipt")
        if practice["run_id"] != payload["run_id"]:
            raise IntegrityError("Checkpoint domain practice belongs to a different run")
        if practice["knowledge_sha256"] != payload.get("domain_knowledge_sha256"):
            raise IntegrityError("Checkpoint domain practice knowledge SHA mismatch")

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
    if plan is not None and plan["revision"] != payload["method_plan_revision"]:
        raise IntegrityError("Checkpoint method-plan revision mismatch")
    if plan is not None and research is not None:
        if plan.get("domain_practice_sha256") != payload.get("domain_practice_sha256"):
            raise IntegrityError("Checkpoint method plan domain-practice SHA mismatch")
        if research["decision"] == "RESEARCH_REQUIRED" and practice is None:
            raise IntegrityError("Checkpoint researched method plan has no domain practice")
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
    domain_root = ensure_within(run_dir, Path(run_dir) / "domain")
    methods_root = ensure_within(run_dir, Path(run_dir) / "methods")
    result: dict[str, Any] = {
        "domain_research_path": None,
        "domain_research_revision": payload.get("domain_research_revision"),
        "domain_research_sha256": None,
        "domain_knowledge_path": None,
        "domain_knowledge_sha256": None,
        "domain_practice_path": None,
        "domain_practice_sha256": None,
        "method_plan_path": None,
        "method_plan_id": None,
        "method_plan_revision": None,
        "method_plan_sha256": None,
        "method_selection_path": None,
        "method_selection_round": None,
        "method_selection_sha256": None,
    }

    if payload.get("domain_research_snapshot_path") is not None:
        revision_value = payload.get("domain_research_revision")
        if revision_value is None:
            raise IntegrityError("Checkpoint domain research has no revision")
        revision = int(revision_value)
        source = ensure_within(root, root / payload["domain_research_snapshot_path"])
        destination = ensure_within(run_dir, domain_root / f"research-r{revision}.json")
        _restore_snapshot_file(source, destination, payload["domain_research_sha256"])
        research = json.loads(destination.read_text(encoding="utf-8"))
        validate_contract("domain_research", research)
        result["domain_research_path"] = destination.relative_to(run_dir).as_posix()
        result["domain_research_revision"] = revision
        result["domain_research_sha256"] = payload["domain_research_sha256"]

    if payload.get("domain_knowledge_snapshot_path") is not None:
        revision_value = payload.get("domain_research_revision")
        if revision_value is None:
            raise IntegrityError("Checkpoint domain knowledge has no research revision")
        revision = int(revision_value)
        source = ensure_within(root, root / payload["domain_knowledge_snapshot_path"])
        destination = ensure_within(run_dir, domain_root / f"knowledge-r{revision}.json")
        _restore_snapshot_file(source, destination, payload["domain_knowledge_sha256"])
        knowledge = json.loads(destination.read_text(encoding="utf-8"))
        validate_contract("domain_knowledge", knowledge)
        result["domain_knowledge_path"] = destination.relative_to(run_dir).as_posix()
        result["domain_knowledge_sha256"] = payload["domain_knowledge_sha256"]

    if payload.get("domain_practice_snapshot_path") is not None:
        revision_value = payload.get("domain_research_revision")
        if revision_value is None:
            raise IntegrityError("Checkpoint domain practice has no research revision")
        revision = int(revision_value)
        source = ensure_within(root, root / payload["domain_practice_snapshot_path"])
        destination = ensure_within(run_dir, domain_root / f"practice-r{revision}.json")
        _restore_snapshot_file(source, destination, payload["domain_practice_sha256"])
        practice = json.loads(destination.read_text(encoding="utf-8"))
        validate_contract("domain_practice", practice)
        result["domain_practice_path"] = destination.relative_to(run_dir).as_posix()
        result["domain_practice_sha256"] = payload["domain_practice_sha256"]

    if payload["method_plan_snapshot_path"] is not None:
        source = ensure_within(root, root / payload["method_plan_snapshot_path"])
        revision = int(payload["method_plan_revision"])
        destination = ensure_within(run_dir, methods_root / f"method-plan-r{revision}.json")
        _restore_snapshot_file(source, destination, payload["method_plan_sha256"])
        plan = json.loads(destination.read_text(encoding="utf-8"))
        validate_contract("method_plan", plan)
        result["method_plan_path"] = destination.relative_to(run_dir).as_posix()
        result["method_plan_id"] = plan["plan_id"]
        result["method_plan_revision"] = revision
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
