from __future__ import annotations

from typing import Any

from .contracts import validate_contract
from .errors import ContractError
from .paths import atomic_write_json


def save_provenance(path, payload: dict[str, Any]) -> None:
    validate_contract("provenance", payload)
    atomic_write_json(path, payload)


def validate_for_candidate(
    candidate_manifest: dict[str, Any],
    provenance: dict[str, Any] | None,
    *,
    required: bool,
) -> None:
    dependencies = [item for item in candidate_manifest["files"] if item["role"] == "dependency"]
    if not dependencies:
        return
    if provenance is None:
        if required:
            raise ContractError("Publication policy requires provenance for dependency files")
        return
    validate_contract("provenance", provenance)
    by_path = {item["path"]: item for item in provenance["items"]}
    for dependency in dependencies:
        entry = by_path.get(dependency["pinned_path"])
        if entry is None:
            if required:
                raise ContractError(f"Missing provenance for {dependency['pinned_path']}")
            continue
        if entry["sha256"] != dependency["sha256"]:
            raise ContractError(f"Provenance SHA mismatch for {dependency['pinned_path']}")
        if required and (not entry.get("source") or not entry.get("license")):
            raise ContractError(f"Incomplete required provenance for {dependency['pinned_path']}")
