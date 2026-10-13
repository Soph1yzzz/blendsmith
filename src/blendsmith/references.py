"""Immutable reference-image receipts for image-guided production."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .errors import ContractError, IntegrityError, SafetyError
from .hashing import sha256_file
from .paths import atomic_write_json, ensure_within

_REF_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_IMAGE_EXTENSIONS = {".png", ".jpeg", ".jpg", ".webp"}


def pin_reference(
    run_dir: Path,
    reference_id: str,
    source: Path,
    *,
    require_in_blend: bool = True,
) -> dict[str, Any]:
    if not _REF_ID.fullmatch(reference_id):
        raise ContractError("Reference ID must contain only letters, digits, underscores or hyphens")
    source = Path(source).expanduser()
    if source.is_symlink() or not source.is_file():
        raise SafetyError(f"Reference must be a regular file, not a link: {source}")
    if source.suffix.lower() not in _IMAGE_EXTENSIONS:
        raise ContractError(f"Unsupported reference image extension: {source.suffix}")
    source = source.resolve()
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(source) as img:
            width, height = img.size
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise IntegrityError(f"Reference is not a valid image: {source}") from exc

    root = ensure_within(run_dir, run_dir / "references")
    manifest_path = root / "index.json"
    previous = verify_references(run_dir) if manifest_path.exists() else {"schema_version": 1, "images": []}
    if any(item["reference_id"] == reference_id for item in previous["images"]):
        raise ContractError(f"Reference ID already exists: {reference_id}")
    dest = root / f"{reference_id}{source.suffix.lower()}"
    if dest.exists():
        raise IntegrityError(f"Reference destination already exists: {dest}")
    root.mkdir(parents=True, exist_ok=True)
    before_hash = sha256_file(source)
    shutil.copy2(source, dest)
    if sha256_file(dest) != before_hash:
        dest.unlink(missing_ok=True)
        raise IntegrityError("Reference changed during pinning")
    record = {
        "reference_id": reference_id,
        "source_name": source.name,
        "managed_path": dest.relative_to(run_dir).as_posix(),
        "sha256": before_hash,
        "width": width,
        "height": height,
        "require_in_blend": require_in_blend,
    }
    previous["images"].append(record)
    atomic_write_json(manifest_path, previous)
    return previous


def verify_references(run_dir: Path, expected_sha256: str | None = None) -> dict[str, Any]:
    path = ensure_within(run_dir, run_dir / "references" / "index.json")
    if not path.is_file() or path.is_symlink():
        if expected_sha256:
            raise IntegrityError("Pinned reference index is missing")
        return {"schema_version": 1, "images": []}
    if expected_sha256 and sha256_file(path) != expected_sha256:
        raise IntegrityError("Reference index changed after registration")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != 1 or not isinstance(receipt.get("images"), list):
        raise IntegrityError("Invalid reference index")
    ids: set[str] = set()
    for item in receipt["images"]:
        ref_id = item.get("reference_id")
        if not isinstance(ref_id, str) or not _REF_ID.fullmatch(ref_id) or ref_id in ids:
            raise IntegrityError("Invalid or repeated reference ID")
        ids.add(ref_id)
        expected = f"references/{ref_id}{Path(item['source_name']).suffix.lower()}"
        if item.get("managed_path") != expected:
            raise IntegrityError("Reference managed path is not canonical")
        pinned = ensure_within(run_dir, run_dir / expected)
        if pinned.is_symlink() or not pinned.is_file():
            raise IntegrityError(f"Pinned reference is missing or unsafe: {ref_id}")
        if sha256_file(pinned) != item["sha256"]:
            raise IntegrityError(f"Pinned reference digest mismatch: {ref_id}")
        if item.get("require_in_blend") not in (True, False):
            raise IntegrityError(f"Reference presence policy is missing: {ref_id}")
    return receipt
