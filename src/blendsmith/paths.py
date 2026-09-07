from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from .errors import SafetyError


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if path.is_symlink():
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attributes & flag)


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def ensure_within(root: Path, candidate: Path, *, reject_reparse: bool = True) -> Path:
    """Return an absolute lexical path only when it stays inside *root*.

    The check intentionally happens before resolving links so a junction/symlink cannot
    redirect a managed path outside the storage boundary.
    """

    root_abs = _lexical_absolute(Path(root))
    candidate_abs = _lexical_absolute(Path(candidate))
    try:
        common = Path(os.path.commonpath([root_abs, candidate_abs]))
    except ValueError as exc:
        raise SafetyError(f"Path is on a different filesystem boundary: {candidate}") from exc
    if os.path.normcase(os.fspath(common)) != os.path.normcase(os.fspath(root_abs)):
        raise SafetyError(f"Path escapes managed root: {candidate}")

    if reject_reparse:
        relative = candidate_abs.relative_to(root_abs)
        cursor = root_abs
        if _is_reparse_point(cursor):
            raise SafetyError(f"Managed root is a reparse point: {root_abs}")
        for part in relative.parts:
            cursor = cursor / part
            if cursor.exists() and _is_reparse_point(cursor):
                raise SafetyError(f"Reparse/symlink path is not allowed: {cursor}")
    return candidate_abs


def relative_managed_path(root: Path, candidate: Path) -> str:
    safe = ensure_within(root, candidate)
    return safe.relative_to(_lexical_absolute(root)).as_posix()


def atomic_write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
