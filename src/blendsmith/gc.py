from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .errors import SafetyError
from .hashing import hash_path
from .paths import append_jsonl, atomic_write_json, ensure_within
from .retention import EPHEMERAL_CLASSES, PINNED_CLASSES, RetentionRegistry
from .timeutil import iso_now, parse_iso, utc_now


def plan_gc(registry: RetentionRegistry) -> list[dict[str, Any]]:
    state = registry.records()
    now = utc_now()
    pinned = [
        ensure_within(registry.layout.control, registry.layout.control / item["relative_path"])
        for item in state.values()
        if item["class"] in PINNED_CLASSES
    ]
    result: list[dict[str, Any]] = []
    for record_id, record in state.items():
        if record["class"] not in EPHEMERAL_CLASSES or not record["gc_allowed"]:
            continue
        if not record.get("expires_at") or parse_iso(record["expires_at"]) > now:
            continue
        target = ensure_within(registry.layout.control, registry.layout.control / record["relative_path"])
        if any(_overlaps(target, protected) for protected in pinned):
            result.append({"record_id": record_id, "path": str(target), "status": "blocked_by_pin"})
            continue
        if not target.exists():
            result.append({"record_id": record_id, "path": str(target), "status": "already_absent"})
            continue
        actual = hash_path(target)
        status = "eligible" if actual == record["sha256"] else "blocked_digest_mismatch"
        result.append({"record_id": record_id, "path": str(target), "status": status})
    return result


def execute_gc(registry: RetentionRegistry) -> list[dict[str, Any]]:
    state = registry.records()
    actions: list[dict[str, Any]] = []
    for item in plan_gc(registry):
        if item["status"] != "eligible":
            actions.append(item)
            continue
        record_id = item["record_id"]
        record = state[record_id]
        target = ensure_within(registry.layout.control, Path(item["path"]))
        if hash_path(target) != record["sha256"]:
            actions.append({**item, "status": "blocked_digest_mismatch"})
            continue
        if target.is_symlink():
            raise SafetyError(f"Refusing linked GC target: {target}")
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            raise SafetyError(f"Unsupported GC target: {target}")
        append_jsonl(
            registry.layout.history / "gc.jsonl",
            {
                "schema_version": 1,
                "record_id": record_id,
                "relative_path": record["relative_path"],
                "sha256": record["sha256"],
                "collected_at": iso_now(),
            },
        )
        state.pop(record_id, None)
        actions.append({**item, "status": "removed"})
    atomic_write_json(registry.state_path, state)
    return actions


def _overlaps(a: Path, b: Path) -> bool:
    a_parts = tuple(a.parts)
    b_parts = tuple(b.parts)
    if len(a_parts) <= len(b_parts):
        return b_parts[: len(a_parts)] == a_parts
    return a_parts[: len(b_parts)] == b_parts
