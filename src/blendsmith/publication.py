from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from .closure import verify_candidate_manifest
from .contracts import validate_contract
from .errors import AuthorityError, IntegrityError, SafetyError
from .hashing import sha256_file
from .paths import atomic_write_json, ensure_within
from .project import ProjectLayout
from .timeutil import iso_now

PUBLICATION_MARKER = "publication.manifest.json"


def publish_verified(
    layout: ProjectLayout,
    *,
    run: dict[str, Any],
    candidate_manifest_path: Path,
) -> tuple[Path, dict[str, Any]]:
    manifest = verify_candidate_manifest(candidate_manifest_path)
    accepted_sha = run.get("accepted_candidate_sha256")
    if not accepted_sha or accepted_sha != manifest["candidate_sha256"]:
        raise AuthorityError("Publication requires the exact human-accepted candidate SHA")
    if layout.publication_current.exists():
        raise SafetyError("Current publication already exists; retract/revise before replacement")

    layout.publication_root.mkdir(parents=True, exist_ok=True)
    ensure_within(layout.publication_root, layout.publication_root)
    staging = ensure_within(
        layout.publication_root,
        layout.publication_root / f".staging-{uuid.uuid4().hex[:12]}",
    )
    staging.mkdir(parents=True, exist_ok=False)

    source_root = Path(candidate_manifest_path).parent / "closure"
    published_files: list[dict[str, Any]] = []
    try:
        for record in manifest["files"]:
            source = ensure_within(source_root, source_root / record["pinned_path"])
            if not source.is_file() or source.is_symlink():
                raise IntegrityError(f"Pinned publication source missing or unsafe: {source}")
            if sha256_file(source) != record["sha256"]:
                raise IntegrityError(f"Pinned publication source changed: {source}")
            destination = ensure_within(staging, staging / record["pinned_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied_sha = sha256_file(destination)
            if copied_sha != record["sha256"]:
                raise IntegrityError(f"Publication staging verification failed: {destination}")
            published_files.append(
                {"path": record["pinned_path"], "sha256": copied_sha, "size": destination.stat().st_size}
            )

        publication = {
            "schema_version": 1,
            "run_id": run["run_id"],
            "candidate_id": manifest["candidate_id"],
            "accepted_candidate_sha256": accepted_sha,
            "closure_sha256": manifest["closure_sha256"],
            "published_at": iso_now(),
            "files": published_files,
        }
        validate_contract("publication_manifest", publication)
        atomic_write_json(staging / PUBLICATION_MARKER, publication)
        _verify_staged_publication(staging, publication)
        os.replace(staging, layout.publication_current)
        return layout.publication_current, publication
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _verify_staged_publication(root: Path, publication: dict[str, Any]) -> None:
    for record in publication["files"]:
        path = ensure_within(root, root / record["path"])
        if not path.is_file() or path.is_symlink():
            raise IntegrityError(f"Staged publication file missing or unsafe: {path}")
        if sha256_file(path) != record["sha256"] or path.stat().st_size != record["size"]:
            raise IntegrityError(f"Staged publication file mismatch: {path}")
    candidate = [item for item in publication["files"] if item["path"].startswith("candidate/")]
    if len(candidate) != 1 or candidate[0]["sha256"] != publication["accepted_candidate_sha256"]:
        raise IntegrityError("Published candidate does not match accepted SHA")


def verify_current_publication(layout: ProjectLayout) -> dict[str, Any]:
    root = ensure_within(layout.publication_root, layout.publication_current)
    marker = root / PUBLICATION_MARKER
    if not marker.is_file():
        raise IntegrityError("Current publication has no BlendSmith manifest")
    publication = json.loads(marker.read_text(encoding="utf-8"))
    validate_contract("publication_manifest", publication)
    _verify_staged_publication(root, publication)
    return publication


def retract_current_publication(
    layout: ProjectLayout,
    *,
    run_dir: Path,
) -> dict[str, Any] | None:
    if not layout.publication_current.exists():
        return None
    publication = verify_current_publication(layout)
    destination = ensure_within(
        layout.control,
        Path(run_dir) / "superseded_publication" / f"pub-{uuid.uuid4().hex[:12]}",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(layout.publication_current, destination)
    return {"publication": publication, "path": str(destination)}
