from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import Any

from .capabilities import latest_snapshot
from .paths import atomic_write_json, ensure_within
from .project import ProjectLayout
from .timeutil import iso_now

# v0.0.2 deliberately caches only discovery facts whose freshness can be
# derived from the Core-owned Blender/runtime identity. Project catalogs,
# adapters, extensions, asset contents, and external Node Tools must be
# rechecked until they gain source-specific fingerprints.
CACHEABLE_DISCOVERY_SOURCES = frozenset({"BLENDER_NATIVE"})
CACHEABLE_METHOD_SOURCES = frozenset({"BLENDER_NATIVE"})


def method_cache_fingerprint(layout: ProjectLayout, project_config: dict[str, Any]) -> dict[str, Any]:
    snapshot = latest_snapshot(layout)
    if snapshot is None:
        return {"status": "UNAVAILABLE", "reason": "no_capability_snapshot", "fingerprint": None}

    method_environment = snapshot["capabilities"].get("method_environment", {})
    if method_environment.get("status") != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "reason": "method_environment_not_available",
            "fingerprint": None,
        }
    environment_fingerprint = method_environment.get("details", {}).get("fingerprint")
    if not environment_fingerprint:
        return {"status": "UNAVAILABLE", "reason": "method_environment_has_no_fingerprint", "fingerprint": None}

    catalog_bytes = (
        resources.files("blendsmith.profiles") / "method_catalog.default.json"
    ).read_bytes()
    catalog_sha256 = hashlib.sha256(catalog_bytes).hexdigest()
    blender_version = (
        snapshot["capabilities"].get("blender_backend", {}).get("details", {}).get("version")
    )
    cache_epoch = int(project_config["method_selection"].get("method_cache_epoch", 0))
    identity = {
        "method_environment_fingerprint": environment_fingerprint,
        "blender_version": blender_version,
        "catalog_sha256": catalog_sha256,
        "cache_epoch": cache_epoch,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "status": "AVAILABLE",
        "reason": None,
        "fingerprint": hashlib.sha256(canonical).hexdigest(),
        "identity": identity,
    }


def cache_path(layout: ProjectLayout):
    root = ensure_within(layout.control, layout.control / "method-cache")
    return ensure_within(root, root / "cache.json")


def load_method_cache(
    layout: ProjectLayout,
    project_config: dict[str, Any],
    *,
    intent: str | None = None,
) -> dict[str, Any]:
    current = method_cache_fingerprint(layout, project_config)
    path = cache_path(layout)
    if not path.is_file():
        return {
            "status": "EMPTY" if current["status"] == "AVAILABLE" else "UNAVAILABLE",
            "current_fingerprint": current.get("fingerprint"),
            "reason": current.get("reason"),
            "entries": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        return {
            "status": "STALE",
            "current_fingerprint": current.get("fingerprint"),
            "cached_fingerprint": payload.get("fingerprint"),
            "reason": "unsupported_cache_schema",
            "entries": [],
        }
    if current["status"] != "AVAILABLE" or payload.get("fingerprint") != current["fingerprint"]:
        return {
            "status": "STALE",
            "current_fingerprint": current.get("fingerprint"),
            "cached_fingerprint": payload.get("fingerprint"),
            "reason": current.get("reason") or "environment_fingerprint_changed",
            "entries": [],
        }
    entries = payload.get("entries", [])
    if intent is not None:
        needle = intent.casefold().strip()
        entries = [item for item in entries if item["intent"].casefold() == needle]
    return {
        "status": "VALID",
        "fingerprint": current["fingerprint"],
        "created_at": payload.get("created_at"),
        "entries": entries,
        "cache_scope": payload.get("cache_scope", []),
        "uncached_sources": payload.get("uncached_sources", []),
        "discovery_sources": payload.get("discovery_sources", []),
        "note": (
            "Cached discovery facts are reusable evidence, not method-selection authority. "
            "Sources without a Core-owned freshness fingerprint must be rechecked live."
        ),
    }


def save_method_cache(
    layout: ProjectLayout,
    project_config: dict[str, Any],
    *,
    plan: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any] | None:
    current = method_cache_fingerprint(layout, project_config)
    if current["status"] != "AVAILABLE":
        return None

    operations: dict[str, dict[str, Any]] = {}
    for unit in plan["work_units"]:
        for operation in unit["method_operations"]:
            operations[operation["operation_id"]] = operation

    entries: list[dict[str, Any]] = []
    for selected in selection["selections"]:
        operation = operations[selected["operation_id"]]
        cacheable_methods = [
            method
            for method in selected["candidate_methods"]
            if method["source"] in CACHEABLE_METHOD_SOURCES
        ]
        if not cacheable_methods:
            continue
        cacheable_ids = {method["method_id"] for method in cacheable_methods}
        previous_selected = (
            selected["selected_method_id"]
            if selected["selected_method_id"] in cacheable_ids
            else None
        )
        entries.append(
            {
                "operation_id": selected["operation_id"],
                "work_unit_id": selected["work_unit_id"],
                "intent": operation["intent"],
                "requirements": operation["requirements"],
                "candidate_methods": cacheable_methods,
                "previous_selected_method_id": previous_selected,
                "previous_selection_reason": (
                    selected["selection_reason"] if previous_selected is not None else None
                ),
            }
        )

    discovery_sources = [
        source
        for source in selection["discovery_sources"]
        if source["source"] in CACHEABLE_DISCOVERY_SOURCES
    ]
    uncached_sources = sorted(
        {
            source["source"]
            for source in selection["discovery_sources"]
            if source["source"] not in CACHEABLE_DISCOVERY_SOURCES
        }
    )
    payload = {
        "schema_version": 1,
        "fingerprint": current["fingerprint"],
        "identity": current["identity"],
        "created_at": iso_now(),
        "cache_scope": sorted(CACHEABLE_DISCOVERY_SOURCES),
        "uncached_sources": uncached_sources,
        "discovery_sources": discovery_sources,
        "entries": entries,
    }
    path = cache_path(layout)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)
    return payload
