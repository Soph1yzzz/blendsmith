"""Re-open the exact pinned .blend in Blender and check its reference images."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .errors import IntegrityError

_MARKER = "BLENDSMITH_SCENE_AUDIT:"

# This runs inside Blender, not in the agent's Python interpreter. It never saves the scene.
_PROBE = """
import bpy, hashlib, json, os
expected = json.loads(os.environ['BLENDSMITH_EXPECTED_REFERENCES'])
images = []
for img in bpy.data.images:
    if img.source not in {'FILE', 'SEQUENCE', 'MOVIE'}:
        continue
    path = bpy.path.abspath(img.filepath) if img.filepath else ''
    packed = img.packed_file is not None
    resolved_hash = None
    if packed:
        resolved_hash = hashlib.sha256(bytes(img.packed_file.data)).hexdigest()
    elif path and os.path.isfile(path):
        with open(path, 'rb') as source:
            resolved_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    images.append({'name': img.name, 'filepath': img.filepath, 'sha256': resolved_hash,
                   'users': img.users, 'packed': packed})
missing_assets = [img['name'] for img in images if img['sha256'] is None and img['users'] > 0]
missing_references = [ref['reference_id'] for ref in expected
    if ref['require_in_blend'] and not any(
        img['sha256'] == ref['sha256'] and img['users'] > 0 and img['packed'] for img in images)]
result = {'missing_assets': missing_assets, 'missing_references': missing_references,
          'images_inspected': len(images), 'scene_loaded': bool(bpy.data.filepath)}
print('BLENDSMITH_SCENE_AUDIT:' + json.dumps(result, sort_keys=True))
"""


def inspect_saved_blend(
    blender_executable: str,
    blend_path: Path,
    references: list[dict[str, Any]],
    *,
    timeout_seconds: int = 150,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["BLENDSMITH_EXPECTED_REFERENCES"] = json.dumps(references, ensure_ascii=False)
    try:
        proc = subprocess.run(
            [blender_executable, "--background", "--disable-autoexec", str(blend_path),
             "--python-expr", _PROBE],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            check=False,
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IntegrityError(f"Independent Blender re-open failed: {type(exc).__name__}: {exc}") from exc
    results = [line.partition(_MARKER)[2] for line in proc.stdout.splitlines() if _MARKER in line]
    if proc.returncode or len(results) != 1:
        raise IntegrityError(f"Independent Blender re-open did not produce a valid audit (exit={proc.returncode})")
    try:
        audit = json.loads(results[0])
    except (ValueError, TypeError) as exc:
        raise IntegrityError("Independent Blender scene audit returned malformed data") from exc
    if not audit.get("scene_loaded") or audit.get("missing_assets") or audit.get("missing_references"):
        raise IntegrityError(
            "Saved .blend has missing image data or registered references: "
            + json.dumps(audit, ensure_ascii=False)
        )
    return audit
