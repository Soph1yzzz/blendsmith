"""Read-only evaluated-mesh contact proximity checks in an independent Blender process.

This proves sampled evaluated vertices are near target mesh surfaces. It does not
certify physical attachment, intersection freedom, strength, or manufacturability.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .errors import IntegrityError

_MARKER = "BLENDSMITH_GEOMETRY_AUDIT:"

_PROBE = r"""
import bpy, json, os
from mathutils.bvhtree import BVHTree
from math import isfinite

checks = json.loads(os.environ['BLENDSMITH_GEOMETRY_CHECKS'])
dg = bpy.context.evaluated_depsgraph_get()
scale = bpy.context.scene.unit_settings.scale_length
results = []

def world_mesh(name):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != 'MESH':
        raise ValueError('Object absent or not a mesh: ' + name)
    evaluated = obj.evaluated_get(dg)
    mesh = evaluated.to_mesh()
    try:
        points = [tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]
        faces = [tuple(p.vertices) for p in mesh.polygons]
        if any(not all(isfinite(component) for component in point) for point in points):
            raise ValueError('Evaluated mesh contains non-finite coordinates: ' + name)
    finally:
        evaluated.to_mesh_clear()
    return points, faces

for check in checks:
    result = {'check_id': check['check_id'], 'status': 'FAIL',
              'max_distance_mm': None, 'vertices_inspected': 0, 'reason': ''}
    try:
        if scale <= 0:
            raise ValueError('Invalid Blender scene unit scale')
        targets = []
        for name in check['target_objects']:
            points, faces = world_mesh(name)
            if not points or not faces:
                raise ValueError('Target has no evaluated mesh surface: ' + name)
            targets.append(BVHTree.FromPolygons(points, faces, all_triangles=False))
        max_distance = 0.0
        count = 0
        for name in check['source_objects']:
            points, _ = world_mesh(name)
            if not points:
                raise ValueError('Source mesh is empty: ' + name)
            count += len(points)
            if count > 200000:
                raise ValueError('Source vertices exceed full-inspection limit (200000)')
            for point in points:
                distances = [hit[3] for tree in targets
                             if (hit := tree.find_nearest(point)) is not None and hit[3] is not None]
                if not distances:
                    raise ValueError('No nearest target surface was found')
                max_distance = max(max_distance, min(distances))
        result['vertices_inspected'] = count
        result['max_distance_mm'] = max_distance * scale * 1000.0
        if count < check['min_source_vertices']:
            result['reason'] = 'Insufficient evaluated source vertices'
        elif result['max_distance_mm'] > check['max_distance_mm']:
            result['reason'] = 'Maximum surface gap exceeds configured limit'
        else:
            result['status'] = 'PASS'
            result['reason'] = 'All evaluated source vertices checked'
    except Exception as exc:
        result['reason'] = str(exc)
    results.append(result)

print('BLENDSMITH_GEOMETRY_AUDIT:' + json.dumps(results, sort_keys=True))
"""


def inspect_contact_proximity(
    blender_executable: str,
    blend_path: Path,
    checks: list[dict[str, Any]],
    *,
    timeout_seconds: int = 180,
) -> list[dict[str, Any]]:
    if not checks:
        return []
    env = dict(os.environ)
    env["BLENDSMITH_GEOMETRY_CHECKS"] = json.dumps(checks, ensure_ascii=False)
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
        raise IntegrityError(f"Independent geometry audit failed: {type(exc).__name__}: {exc}") from exc
    outputs = [line.partition(_MARKER)[2] for line in proc.stdout.splitlines() if _MARKER in line]
    if proc.returncode or len(outputs) != 1:
        raise IntegrityError(f"Independent geometry audit produced no valid result (exit={proc.returncode})")
    try:
        result = json.loads(outputs[0])
    except (TypeError, ValueError) as exc:
        raise IntegrityError("Geometry audit produced invalid JSON") from exc
    if not isinstance(result, list) or len(result) != len(checks):
        raise IntegrityError("Geometry audit omitted declared structural checks")
    for check, entry in zip(checks, result, strict=True):
        if not isinstance(entry, dict) or entry.get("check_id") != check["check_id"]:
            raise IntegrityError("Geometry audit check identity mismatch")
        if entry.get("status") not in {"PASS", "FAIL"}:
            raise IntegrityError("Geometry audit reported an unknown status")
        count = entry.get("vertices_inspected")
        distance = entry.get("max_distance_mm")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise IntegrityError("Geometry audit returned invalid vertex count")
        if distance is not None and (not isinstance(distance, (int, float))
                                     or isinstance(distance, bool) or not 0 <= distance < float("inf")):
            raise IntegrityError("Geometry audit returned invalid proximity distance")
        if entry["status"] == "PASS" and (
            count < check["min_source_vertices"] or distance is None
            or distance > check["max_distance_mm"]
        ):
            raise IntegrityError("Geometry audit reported PASS without meeting the objective limit")
    return result
