from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PRIMARY_BLENDER_VERSION = (5, 2)


@dataclass(frozen=True)
class BlenderProbe:
    executable: str | None
    status: str
    version: str | None
    support_level: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_blender_executable(configured: str | None = None) -> str | None:
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        return None
    return shutil.which("blender")


def probe_blender(configured: str | None = None, *, timeout_seconds: float = 10.0) -> BlenderProbe:
    executable = resolve_blender_executable(configured)
    if executable is None:
        return BlenderProbe(
            executable=None,
            status="UNAVAILABLE",
            version=None,
            support_level="unavailable",
            details={"reason": "blender_executable_not_found"},
        )

    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return BlenderProbe(
            executable=executable,
            status="BROKEN",
            version=None,
            support_level="unknown",
            details={"reason": "blender_version_probe_failed", "error": type(exc).__name__},
        )

    output = (result.stdout or "") + "\n" + (result.stderr or "")
    match = re.search(r"Blender\s+(\d+)\.(\d+)(?:\.(\d+))?", output)
    if result.returncode != 0 or not match:
        return BlenderProbe(
            executable=executable,
            status="BROKEN",
            version=None,
            support_level="unknown",
            details={"reason": "unexpected_blender_version_output", "returncode": result.returncode},
        )

    major, minor = int(match.group(1)), int(match.group(2))
    patch = int(match.group(3) or 0)
    version = f"{major}.{minor}.{patch}"
    if (major, minor) == PRIMARY_BLENDER_VERSION:
        support_level = "primary"
        status = "AVAILABLE"
    elif major == 5:
        support_level = "best_effort_probe"
        status = "AVAILABLE"
    else:
        support_level = "unsupported"
        status = "UNAVAILABLE"

    return BlenderProbe(
        executable=executable,
        status=status,
        version=version,
        support_level=support_level,
        details={"returncode": result.returncode},
    )


def probe_method_environment(
    executable: str | None,
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    if executable is None:
        return {"status": "UNAVAILABLE", "details": {"reason": "blender_executable_not_found"}}

    expression = (
        "import bpy,json;"
        "addons=sorted(bpy.context.preferences.addons.keys());"
        "libs=sorted((x.name,x.path) for x in bpy.context.preferences.filepaths.asset_libraries);"
        "print('BLENDSMITH_METHOD_ENV='+json.dumps({'addons':addons,'asset_libraries':libs},sort_keys=True))"
    )
    try:
        result = subprocess.run(
            [executable, "--background", "--python-expr", expression],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "BROKEN",
            "details": {"reason": "method_environment_probe_failed", "error": type(exc).__name__},
        }

    if result.returncode != 0:
        return {
            "status": "BROKEN",
            "details": {
                "reason": "method_environment_probe_nonzero",
                "returncode": result.returncode,
            },
        }
    marker = "BLENDSMITH_METHOD_ENV="
    line = next((item for item in (result.stdout or "").splitlines() if item.startswith(marker)), None)
    if line is None:
        return {"status": "BROKEN", "details": {"reason": "method_environment_marker_missing"}}
    try:
        inventory = json.loads(line[len(marker) :])
    except json.JSONDecodeError:
        return {"status": "BROKEN", "details": {"reason": "method_environment_json_invalid"}}
    canonical = json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = hashlib.sha256(canonical).hexdigest()
    return {
        "status": "AVAILABLE",
        "details": {
            "fingerprint": fingerprint,
            "addons": inventory.get("addons", []),
            "asset_libraries": inventory.get("asset_libraries", []),
        },
    }
