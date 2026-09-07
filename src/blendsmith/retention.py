from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from .contracts import validate_contract
from .errors import IntegrityError
from .hashing import hash_path
from .paths import append_jsonl, atomic_write_json, ensure_within, relative_managed_path
from .project import ProjectLayout
from .timeutil import iso_now, utc_now

PINNED_CLASSES = {
    "PINNED_INSTALLATION",
    "PINNED_ENVIRONMENT",
    "PINNED_ACTIVE_CHECKPOINT",
    "PINNED_CURRENT_FINAL",
    "LIGHTWEIGHT_HISTORY",
}
EPHEMERAL_CLASSES = {"EPHEMERAL", "EPHEMERAL_SUPERSEDED_FINAL"}


class RetentionRegistry:
    def __init__(self, layout: ProjectLayout):
        self.layout = layout
        self.state_path = layout.history / "retention_state.json"
        self.log_path = layout.history / "retention.jsonl"

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.state_path.exists():
            return {}
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise IntegrityError("Retention state is not an object")
        for record in payload.values():
            validate_contract("retention_record", record)
        return payload

    def _save(self, state: dict[str, dict[str, Any]], record: dict[str, Any]) -> None:
        atomic_write_json(self.state_path, state)
        append_jsonl(self.log_path, record)

    def register(
        self,
        path: Path,
        retention_class: str,
        *,
        ttl_hours: int | None = None,
        record_id: str | None = None,
        replaced_by: str | None = None,
    ) -> dict[str, Any]:
        path = ensure_within(self.layout.control, path)
        if retention_class not in PINNED_CLASSES | EPHEMERAL_CLASSES:
            raise ValueError(f"Unknown retention class: {retention_class}")
        now = utc_now()
        if retention_class in EPHEMERAL_CLASSES:
            if ttl_hours is None or ttl_hours <= 0:
                raise ValueError("Ephemeral retention requires a positive TTL")
            expires_at = (now + timedelta(hours=ttl_hours)).isoformat().replace("+00:00", "Z")
            gc_allowed = True
        else:
            expires_at = None
            gc_allowed = False
        record = {
            "schema_version": 1,
            "record_id": record_id or uuid.uuid4().hex,
            "relative_path": relative_managed_path(self.layout.control, path),
            "class": retention_class,
            "sha256": hash_path(path),
            "gc_allowed": gc_allowed,
            "created_at": iso_now(),
            "expires_at": expires_at,
            "replaced_by": replaced_by,
        }
        validate_contract("retention_record", record)
        state = self._load()
        state[record["record_id"]] = record
        self._save(state, record)
        return record

    def transition(
        self,
        record_id: str,
        retention_class: str,
        *,
        ttl_hours: int | None = None,
        replaced_by: str | None = None,
    ) -> dict[str, Any]:
        state = self._load()
        current = state[record_id]
        path = ensure_within(self.layout.control, self.layout.control / current["relative_path"])
        actual = hash_path(path)
        if actual != current["sha256"]:
            raise IntegrityError("Retention transition refused because stored bytes changed")
        now = utc_now()
        if retention_class in EPHEMERAL_CLASSES:
            if ttl_hours is None or ttl_hours <= 0:
                raise ValueError("Ephemeral retention requires a positive TTL")
            expires_at = (now + timedelta(hours=ttl_hours)).isoformat().replace("+00:00", "Z")
            gc_allowed = True
        elif retention_class in PINNED_CLASSES:
            expires_at = None
            gc_allowed = False
        else:
            raise ValueError(f"Unknown retention class: {retention_class}")
        updated = {
            **current,
            "class": retention_class,
            "gc_allowed": gc_allowed,
            "expires_at": expires_at,
            "replaced_by": replaced_by,
            "sha256": actual,
        }
        validate_contract("retention_record", updated)
        state[record_id] = updated
        self._save(state, updated)
        return updated

    def records(self) -> dict[str, dict[str, Any]]:
        return self._load()
