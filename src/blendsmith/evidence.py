from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

from .errors import IntegrityError, SafetyError
from .hashing import sha256_file
from .paths import atomic_write_json, ensure_within
from .timeutil import iso_now

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_SAFE_KEY = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def materialize_evidence(
    run_dir: Path,
    *,
    candidate_id: str,
    views: Mapping[str, Path],
    minimum_width: int = 1600,
    minimum_height: int = 900,
    review_max_edge: int = 1920,
    tile_size: int = 896,
    tile_overlap: int = 96,
    jpeg_quality: int = 92,
) -> tuple[Path, dict]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("Pillow is required for evidence image QA") from exc

    if not views:
        raise ValueError("At least one evidence view is required")
    if tile_overlap >= tile_size:
        raise ValueError("tile_overlap must be smaller than tile_size")
    root = ensure_within(run_dir, Path(run_dir) / "evidence" / candidate_id)
    originals = root / "originals"
    reviews = root / "review"
    tiles_root = root / "tiles"
    originals.mkdir(parents=True, exist_ok=True)
    reviews.mkdir(parents=True, exist_ok=True)
    tiles_root.mkdir(parents=True, exist_ok=True)

    records = []
    for key, source_value in sorted(views.items()):
        if not _SAFE_KEY.fullmatch(key):
            raise ValueError(f"Unsafe evidence key: {key}")
        source = Path(source_value).expanduser()
        if source.is_symlink():
            raise SafetyError(f"Evidence symlink is not accepted: {source}")
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.suffix.lower() not in _ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported evidence image type: {source.suffix}")
        source = source.resolve()
        destination = originals / f"{key}{source.suffix.lower()}"
        source_hash = sha256_file(source)
        shutil.copy2(source, destination)
        copied_hash = sha256_file(destination)
        if copied_hash != source_hash:
            raise IntegrityError(f"Evidence copy verification failed: {source}")

        try:
            with Image.open(destination) as probe:
                width, height = probe.size
                probe.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise IntegrityError(f"Evidence is not a valid readable image: {source}") from exc
        if width < minimum_width or height < minimum_height:
            raise IntegrityError(
                f"Evidence {key} is {width}x{height}; minimum is {minimum_width}x{minimum_height}"
            )

        review_path = reviews / f"{key}.jpg"
        with Image.open(destination) as image:
            review = image.convert("RGB")
            review.thumbnail((review_max_edge, review_max_edge), Image.Resampling.LANCZOS)
            review.save(review_path, "JPEG", quality=jpeg_quality, optimize=True)
        tile_records = _write_tiles(
            review_path,
            tiles_root / key,
            tile_size=tile_size,
            overlap=tile_overlap,
            jpeg_quality=jpeg_quality,
            root=run_dir,
        )

        records.append(
            {
                "key": key,
                "source_path": os.fspath(source),
                "managed_path": destination.relative_to(run_dir).as_posix(),
                "sha256": copied_hash,
                "size": destination.stat().st_size,
                "width": width,
                "height": height,
                "review_path": review_path.relative_to(run_dir).as_posix(),
                "review_sha256": sha256_file(review_path),
                "tiles": tile_records,
            }
        )
    bundle = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "created_at": iso_now(),
        "views": records,
    }
    bundle_path = root / "evidence.bundle.json"
    atomic_write_json(bundle_path, bundle)
    return bundle_path, bundle


def _write_tiles(
    review_path: Path,
    output_dir: Path,
    *,
    tile_size: int,
    overlap: int,
    jpeg_quality: int,
    root: Path,
) -> list[dict]:
    from PIL import Image

    output_dir.mkdir(parents=True, exist_ok=True)
    step = tile_size - overlap
    records: list[dict] = []
    with Image.open(review_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        xs = _positions(width, tile_size, step)
        ys = _positions(height, tile_size, step)
        index = 0
        for top in ys:
            for left in xs:
                index += 1
                right = min(left + tile_size, width)
                bottom = min(top + tile_size, height)
                tile = image.crop((left, top, right, bottom))
                tile_path = output_dir / f"tile-{index:03d}.jpg"
                tile.save(tile_path, "JPEG", quality=jpeg_quality, optimize=True)
                records.append(
                    {
                        "path": tile_path.relative_to(root).as_posix(),
                        "sha256": sha256_file(tile_path),
                        "box": [left, top, right, bottom],
                    }
                )
    return records


def _positions(length: int, tile_size: int, step: int) -> list[int]:
    if length <= tile_size:
        return [0]
    positions = list(range(0, max(1, length - tile_size + 1), step))
    last = length - tile_size
    if positions[-1] != last:
        positions.append(last)
    return positions


def verify_evidence_bundle(run_dir: Path, bundle_path: Path) -> dict:
    import json

    bundle_path = ensure_within(run_dir, bundle_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    seen = set()
    for record in bundle.get("views", []):
        key = record["key"]
        if key in seen:
            raise IntegrityError(f"Duplicate evidence key: {key}")
        seen.add(key)
        managed = ensure_within(run_dir, Path(run_dir) / record["managed_path"])
        if not managed.is_file() or managed.is_symlink():
            raise IntegrityError(f"Evidence file missing or unsafe: {managed}")
        if sha256_file(managed) != record["sha256"]:
            raise IntegrityError(f"Evidence digest mismatch: {managed}")
        review_path = ensure_within(run_dir, Path(run_dir) / record["review_path"])
        if sha256_file(review_path) != record["review_sha256"]:
            raise IntegrityError(f"Review image digest mismatch: {review_path}")
        for tile in record.get("tiles", []):
            tile_path = ensure_within(run_dir, Path(run_dir) / tile["path"])
            if sha256_file(tile_path) != tile["sha256"]:
                raise IntegrityError(f"Review tile digest mismatch: {tile_path}")
    if not seen:
        raise IntegrityError("Evidence bundle is empty")
    return bundle
