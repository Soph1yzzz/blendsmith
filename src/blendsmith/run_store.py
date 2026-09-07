from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from .contracts import validate_contract
from .errors import IntegrityError
from .paths import append_jsonl, atomic_write_json, ensure_within
from .project import ProjectLayout
from .state_machine import RunState, validate_transition
from .timeutil import iso_now

_RUN_ID = re.compile(r"^run-[0-9a-f]{12}$")


def _validated_run_id(run_id: object) -> str:
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise IntegrityError("Invalid BlendSmith run id")
    return run_id


def create_run(layout: ProjectLayout, project_id: str) -> tuple[Path, dict[str, Any]]:
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    run_dir = layout.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    now = iso_now()
    run = {
        "schema_version": 1,
        "run_id": run_id,
        "project_id": project_id,
        "state": RunState.CREATED.value,
        "created_at": now,
        "updated_at": now,
        "iteration": 0,
        "active_candidate_id": None,
        "resume_state": None,
        "assurance_level": None,
        "accepted_candidate_sha256": None,
        "active_checkpoint_id": None,
        "metadata": {},
    }
    validate_contract("run", run)
    atomic_write_json(run_dir / "run.json", run)
    atomic_write_json(layout.current_run_pointer, {"run_id": run_id})
    return run_dir, run


def load_run(layout: ProjectLayout, run_id: str) -> tuple[Path, dict[str, Any]]:
    run_id = _validated_run_id(run_id)
    run_dir = ensure_within(layout.runs, layout.runs / run_id)
    run_path = ensure_within(run_dir, run_dir / "run.json")
    if not run_path.is_file():
        raise FileNotFoundError(run_path)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    validate_contract("run", run)
    if run["run_id"] != run_id:
        raise IntegrityError("Run file identity does not match requested run id")
    project = json.loads(layout.config.read_text(encoding="utf-8"))
    if run["project_id"] != project.get("project_id"):
        raise IntegrityError("Run file project identity does not match BlendSmith project")
    return run_dir, run


def load_current_run(layout: ProjectLayout) -> tuple[Path, dict[str, Any]]:
    pointer_path = ensure_within(layout.control, layout.current_run_pointer)
    if not pointer_path.is_file():
        raise FileNotFoundError("No current BlendSmith run")
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if not isinstance(pointer, dict) or set(pointer) != {"run_id"}:
        raise IntegrityError("Invalid current-run pointer")
    return load_run(layout, _validated_run_id(pointer["run_id"]))


def save_run(run_dir: Path, run: dict[str, Any]) -> None:
    run["updated_at"] = iso_now()
    validate_contract("run", run)
    atomic_write_json(run_dir / "run.json", run)


def transition(
    run_dir: Path,
    run: dict[str, Any],
    target: RunState,
    *,
    reason: str,
    metadata: dict[str, Any] | None = None,
    resume_target: RunState | None = None,
) -> dict[str, Any]:
    source = RunState(run["state"])
    validate_transition(source, target, resume_target=resume_target)
    event = {
        "schema_version": 1,
        "run_id": run["run_id"],
        "from_state": source.value,
        "to_state": target.value,
        "occurred_at": iso_now(),
        "reason": reason,
        "metadata": metadata or {},
    }
    validate_contract("state_event", event)
    append_jsonl(run_dir / "state_events.jsonl", event)
    run["state"] = target.value
    save_run(run_dir, run)
    return run
