from __future__ import annotations

from pathlib import Path

from blendsmith.gc import plan_gc
from blendsmith.paths import atomic_write_json
from blendsmith.project import initialize_project
from blendsmith.retention import RetentionRegistry


def test_expired_verified_record_is_planned(tmp_path: Path) -> None:
    layout = initialize_project(tmp_path / "project")
    registry = RetentionRegistry(layout)
    target = layout.control / "runs" / "old" / "payload.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"expired")
    record = registry.register(target, "EPHEMERAL", ttl_hours=1)
    state = registry.records()
    state[record["record_id"]]["expires_at"] = "2000-01-01T00:00:00Z"
    atomic_write_json(registry.state_path, state)
    plan = plan_gc(registry)
    assert plan[0]["record_id"] == record["record_id"]
    assert plan[0]["status"] == "eligible"


def test_changed_record_is_not_planned_as_eligible(tmp_path: Path) -> None:
    layout = initialize_project(tmp_path / "project")
    registry = RetentionRegistry(layout)
    target = layout.control / "runs" / "old" / "payload.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"original")
    record = registry.register(target, "EPHEMERAL", ttl_hours=1)
    state = registry.records()
    state[record["record_id"]]["expires_at"] = "2000-01-01T00:00:00Z"
    atomic_write_json(registry.state_path, state)
    target.write_bytes(b"changed")
    plan = plan_gc(registry)
    assert plan[0]["status"] == "blocked_digest_mismatch"
