from __future__ import annotations

import json
from pathlib import Path

import pytest

from blendsmith.errors import IntegrityError, SafetyError
from blendsmith.hashing import hash_path
from blendsmith.orchestrator import BlendSmith
from blendsmith.paths import ensure_within
from blendsmith.run_store import load_current_run


def test_managed_path_rejects_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    with pytest.raises(SafetyError):
        ensure_within(root, root / ".." / "escape.txt")


def test_hash_changes_when_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "x.bin"
    path.write_bytes(b"one")
    first = hash_path(path)
    path.write_bytes(b"two")
    assert hash_path(path) != first


def test_current_run_pointer_rejects_path_traversal(tmp_path: Path) -> None:
    app = BlendSmith.init(tmp_path / "project")
    app.layout.current_run_pointer.write_text(
        json.dumps({"run_id": "../../outside"}),
        encoding="utf-8",
    )
    with pytest.raises(IntegrityError):
        load_current_run(app.layout)
