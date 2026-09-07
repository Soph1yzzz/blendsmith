from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path

from .errors import IntegrityError
from .paths import _is_reparse_point

CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    path = Path(path)
    if path.is_symlink():
        raise IntegrityError(f"Refusing to hash symlink: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_regular_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for dirname in list(dirs):
            candidate = current_path / dirname
            if _is_reparse_point(candidate):
                raise IntegrityError(f"Refusing directory tree containing reparse point: {candidate}")
        for filename in files:
            candidate = current_path / filename
            if _is_reparse_point(candidate):
                raise IntegrityError(f"Refusing directory tree containing reparse point: {candidate}")
            if candidate.is_file():
                yield candidate


def tree_manifest(root: Path) -> list[dict[str, str | int]]:
    root = Path(root)
    if _is_reparse_point(root):
        raise IntegrityError(f"Refusing reparse-point directory root: {root}")
    root = root.resolve()
    if not root.is_dir():
        raise IntegrityError(f"Not a directory: {root}")
    items: list[dict[str, str | int]] = []
    for path in sorted(_iter_regular_files(root), key=lambda p: p.relative_to(root).as_posix()):
        items.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    return items


def tree_sha256(root: Path) -> str:
    payload = json.dumps(tree_manifest(root), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_path(path: Path) -> str:
    path = Path(path)
    if path.is_file():
        return sha256_file(path)
    if path.is_dir():
        return tree_sha256(path)
    raise IntegrityError(f"Path is not a regular file or directory: {path}")
