from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .contracts import validate_contract
from .errors import IntegrityError, SafetyError
from .hashing import sha256_file
from .paths import atomic_write_json, ensure_within
from .timeutil import iso_now

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", name).strip("._")
    return cleaned[:120] or "file"


def _source_file(path: Path) -> Path:
    path = Path(path).expanduser()
    if path.is_symlink():
        raise SafetyError(f"Source symlink is not accepted for pinning: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.resolve()


def _closure_digest(files: Iterable[dict[str, Any]]) -> str:
    normalized = [
        {"role": item["role"], "pinned_path": item["pinned_path"], "sha256": item["sha256"], "size": item["size"]}
        for item in files
    ]
    normalized.sort(key=lambda item: item["pinned_path"])
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def materialize_candidate_closure(
    run_dir: Path,
    *,
    run_id: str,
    iteration: int,
    variant_index: int,
    method_plan_id: str,
    method_selection_round: int,
    method_selection_sha256: str,
    candidate: Path,
    dependencies: Iterable[Path] = (),
    candidate_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    if variant_index < 1 or variant_index > 3:
        raise ValueError("variant_index must be between 1 and 3")
    candidate_source = _source_file(candidate)
    if candidate_source.suffix.lower() != ".blend":
        raise ValueError("BlendSmith candidates must be .blend files")

    candidate_id = candidate_id or f"i{iteration}-v{variant_index}-{uuid.uuid4().hex[:8]}"
    candidate_root = ensure_within(run_dir, Path(run_dir) / "candidates" / candidate_id)
    if candidate_root.exists():
        raise FileExistsError(candidate_root)
    closure_root = candidate_root / "closure"
    (closure_root / "candidate").mkdir(parents=True, exist_ok=False)
    (closure_root / "dependencies").mkdir(parents=True, exist_ok=False)

    records: list[dict[str, Any]] = []

    def copy_verified(source: Path, destination: Path, role: str) -> None:
        source = _source_file(source)
        before = source.stat()
        source_hash = sha256_file(source)
        shutil.copy2(source, destination)
        destination_hash = sha256_file(destination)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise IntegrityError(f"Source changed while pinning: {source}")
        if source_hash != destination_hash:
            raise IntegrityError(f"Copy verification failed: {source}")
        records.append(
            {
                "role": role,
                "source_path": os.fspath(source),
                "pinned_path": destination.relative_to(closure_root).as_posix(),
                "sha256": destination_hash,
                "size": destination.stat().st_size,
            }
        )

    candidate_destination = closure_root / "candidate" / _safe_name(candidate_source.name)
    copy_verified(candidate_source, candidate_destination, "candidate")

    seen_hashes: set[tuple[str, int]] = set()
    for index, dependency in enumerate(dependencies, start=1):
        source = _source_file(Path(dependency))
        key = (os.path.normcase(os.fspath(source)), source.stat().st_size)
        if key in seen_hashes:
            continue
        seen_hashes.add(key)
        destination = closure_root / "dependencies" / f"{index:04d}_{_safe_name(source.name)}"
        copy_verified(source, destination, "dependency")

    candidate_record = next(record for record in records if record["role"] == "candidate")
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "iteration": iteration,
        "variant_index": variant_index,
        "method_plan_id": method_plan_id,
        "method_selection_round": method_selection_round,
        "method_selection_sha256": method_selection_sha256,
        "candidate_sha256": candidate_record["sha256"],
        "closure_sha256": _closure_digest(records),
        "files": records,
        "created_at": iso_now(),
    }
    validate_contract("candidate_manifest", manifest)
    manifest_path = candidate_root / "candidate.manifest.json"
    atomic_write_json(manifest_path, manifest)
    return manifest_path, manifest


def verify_candidate_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_contract("candidate_manifest", manifest)
    closure_root = manifest_path.parent / "closure"
    verified: list[dict[str, Any]] = []
    candidate_sha: str | None = None
    for record in manifest["files"]:
        pinned = ensure_within(closure_root, closure_root / Path(record["pinned_path"]))
        if not pinned.is_file() or pinned.is_symlink():
            raise IntegrityError(f"Pinned closure file missing or unsafe: {pinned}")
        actual_sha = sha256_file(pinned)
        if actual_sha != record["sha256"]:
            raise IntegrityError(f"Pinned closure digest mismatch: {pinned}")
        if pinned.stat().st_size != record["size"]:
            raise IntegrityError(f"Pinned closure size mismatch: {pinned}")
        verified.append(record)
        if record["role"] == "candidate":
            if candidate_sha is not None:
                raise IntegrityError("Candidate closure contains multiple root candidates")
            candidate_sha = actual_sha

    if candidate_sha != manifest["candidate_sha256"]:
        raise IntegrityError("Candidate SHA does not match manifest")
    if _closure_digest(verified) != manifest["closure_sha256"]:
        raise IntegrityError("Dependency closure digest does not match manifest")
    return manifest
