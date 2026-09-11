from __future__ import annotations

import hashlib
import json
import platform
import sys
import uuid
from dataclasses import dataclass
from importlib import metadata, resources
from pathlib import Path
from typing import Any

from .blender import probe_blender
from .contracts import SCHEMA_FILES, validate_contract
from .errors import SafetyError
from .paths import _is_reparse_point, atomic_write_json
from .timeutil import iso_now
from .version import __version__

CONFIG_NAME = "blendsmith.project.json"
CONTROL_DIR = ".blendsmith"


@dataclass(frozen=True)
class ProjectLayout:
    root: Path

    @property
    def config(self) -> Path:
        return self.root / CONFIG_NAME

    @property
    def control(self) -> Path:
        return self.root / CONTROL_DIR

    @property
    def install(self) -> Path:
        return self.control / "install"

    @property
    def capabilities(self) -> Path:
        return self.control / "capabilities"

    @property
    def runs(self) -> Path:
        return self.control / "runs"

    @property
    def history(self) -> Path:
        return self.control / "history"

    @property
    def knowledge(self) -> Path:
        return self.control / "knowledge"

    @property
    def knowledge_cache(self) -> Path:
        return self.knowledge / "cache"

    @property
    def current_run_pointer(self) -> Path:
        return self.control / "current_run.json"

    @property
    def publication_root(self) -> Path:
        return self.root / "publication"

    @property
    def publication_current(self) -> Path:
        return self.publication_root / "current"


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "project_id": "",
    "storage": {"ephemeral_ttl_hours": 24},
    "qa": {
        "live_gui_review": "required_if_capable",
        "max_primary_repair_issues": 2,
        "max_variants_per_iteration": 3,
        "minimum_render_width": 1600,
        "minimum_render_height": 900,
        "review_max_edge": 1920,
        "tile_size": 896,
        "tile_overlap": 96,
        "jpeg_quality": 92,
        "required_evidence": [],
        "required_perspectives": [],
        "evidence_profiles": {},
    },
    "method_selection": {
        "required": True,
        "required_discovery_sources": [
            "BLENDER_NATIVE",
            "GEOMETRY_NODE_TOOLS",
            "ASSET_LIBRARIES",
            "EXTENSIONS",
            "PROJECT_CATALOG",
            "ADAPTERS",
        ],
        "scratch_requires_specialized_exhaustion": True,
        "require_catalog_hint_accounting": True,
        "method_cache_epoch": 0,
    },
    "production_structure": {
        "global_reassessment_after_local_repairs": 2,
        "max_gui_quality_gain_issues": 2,
    },
    "domain_knowledge": {
        "enabled": True,
        "cache_enabled": True,
        "stable_cache_allowed": True,
        "slow_changing_ttl_days": 180,
        "current_ttl_days": 7,
        "cache_epoch": 0,
    },
    "recovery": {"max_retries": 3, "escalate_non_retryable_immediately": True},
    "provenance": {"required_for_publication": False},
}


def _schema_digests() -> dict[str, str]:
    package = resources.files("blendsmith.schemas")
    result: dict[str, str] = {}
    for filename in sorted(set(SCHEMA_FILES.values())):
        data = (package / filename).read_bytes()
        result[filename] = hashlib.sha256(data).hexdigest()
    return result


def initialize_project(root: Path, *, project_id: str | None = None) -> ProjectLayout:
    root = Path(root).expanduser()
    if root.exists() and _is_reparse_point(root):
        raise SafetyError(f"Project root cannot be a symlink/junction/reparse point: {root}")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    layout = ProjectLayout(root)

    if layout.config.exists():
        load_project(root)
        return layout

    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["project_id"] = project_id or root.name or f"blendsmith-{uuid.uuid4().hex[:8]}"
    validate_contract("project", config)
    atomic_write_json(layout.config, config)

    for path in (
        layout.install,
        layout.capabilities,
        layout.runs,
        layout.history,
        layout.knowledge_cache,
    ):
        path.mkdir(parents=True, exist_ok=True)
    create_identity_locks(layout)
    return layout


def _merge_config_defaults(defaults: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(defaults))
    for key, value in current.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config_defaults(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_project(root: Path) -> tuple[ProjectLayout, dict[str, Any]]:
    root = Path(root).expanduser()
    if root.exists() and _is_reparse_point(root):
        raise SafetyError(f"Project root cannot be a symlink/junction/reparse point: {root}")
    root = root.resolve()
    layout = ProjectLayout(root)
    if layout.config.exists() and _is_reparse_point(layout.config):
        raise SafetyError(f"Project config cannot be a symlink/junction/reparse point: {layout.config}")
    if not layout.config.is_file():
        raise FileNotFoundError(f"Not a BlendSmith project: {root}")
    for managed in (
        layout.control,
        layout.install,
        layout.capabilities,
        layout.runs,
        layout.history,
        layout.knowledge,
        layout.knowledge_cache,
    ):
        if managed.exists() and _is_reparse_point(managed):
            raise SafetyError(f"Managed BlendSmith path cannot be a reparse point: {managed}")
    raw_config = json.loads(layout.config.read_text(encoding="utf-8"))
    config = _merge_config_defaults(DEFAULT_CONFIG, raw_config)
    validate_contract("project", config)
    return layout, config


def create_identity_locks(layout: ProjectLayout, *, blender_path: str | None = None) -> None:
    dependencies: dict[str, str] = {}
    for distribution in ("jsonschema", "Pillow"):
        try:
            dependencies[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            dependencies[distribution] = "unknown"

    installation = {
        "schema_version": 1,
        "created_at": iso_now(),
        "blendsmith_version": __version__,
        "dependencies": dependencies,
        "schema_sha256": _schema_digests(),
        "adapters": {"blender_runtime_probe": 1, "external_contract": 1},
    }
    atomic_write_json(layout.install / "installation.lock.json", installation)

    blender = probe_blender(blender_path)
    environment = {
        "schema_version": 1,
        "created_at": iso_now(),
        "platform": platform.platform(),
        "host_python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "blender_identity": {
            "configured_path": blender_path,
            "resolved_executable": blender.executable,
            "version": blender.version,
            "support_level": blender.support_level,
        },
        "note": "Capability status is intentionally stored in separate timestamped snapshots.",
    }
    atomic_write_json(layout.install / "environment.lock.json", environment)
