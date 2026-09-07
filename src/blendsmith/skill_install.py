from __future__ import annotations

import hashlib
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any

from .errors import ContractError, SafetyError
from .paths import atomic_write_text, ensure_within
from .version import __version__

SKILL_RELATIVE_PATH = Path("skills") / "codex" / "SKILL.md"
SKILL_NAME = "blendsmith"


def bundled_skill_bytes() -> bytes:
    package = resources.files("blendsmith")
    return (package / SKILL_RELATIVE_PATH.as_posix()).read_bytes()


def bundled_skill_sha256() -> str:
    return hashlib.sha256(bundled_skill_bytes()).hexdigest()


def _skill_metadata_version(payload: bytes) -> str | None:
    text = payload.decode("utf-8")
    match = re.search(r'^\s*version:\s*["\']([^"\']+)["\']\s*$', text, flags=re.MULTILINE)
    return match.group(1) if match else None


def bundled_skill_version() -> str | None:
    return _skill_metadata_version(bundled_skill_bytes())


def codex_skill_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    root = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return root / "skills" / SKILL_NAME / "SKILL.md"


def _safe_codex_skill_path() -> Path:
    destination = codex_skill_path()
    root = destination.parents[2]
    return ensure_within(root, destination)


def skill_status() -> dict[str, Any]:
    destination = codex_skill_path()
    expected = bundled_skill_sha256()
    bundled_version = bundled_skill_version()
    bundle_version_matches_cli = bundled_version == __version__
    try:
        destination = _safe_codex_skill_path()
    except SafetyError:
        state = "UNSAFE_TARGET"
        actual = None
    else:
        if destination.is_symlink():
            state = "UNSAFE_TARGET"
            actual = None
            installed_version = None
        elif not destination.exists():
            state = "NOT_INSTALLED"
            actual = None
            installed_version = None
        elif not destination.is_file():
            state = "UNSAFE_TARGET"
            actual = None
            installed_version = None
        else:
            installed_payload = destination.read_bytes()
            actual = hashlib.sha256(installed_payload).hexdigest()
            installed_version = _skill_metadata_version(installed_payload)
            if not bundle_version_matches_cli:
                state = "BUNDLE_VERSION_MISMATCH"
            else:
                state = "CURRENT" if actual == expected else "STALE_OR_MODIFIED"
    if 'installed_version' not in locals():
        installed_version = None
    return {
        "skill": SKILL_NAME,
        "path": str(destination),
        "status": state,
        "bundled_sha256": expected,
        "installed_sha256": actual,
        "cli_version": __version__,
        "bundled_skill_version": bundled_version,
        "installed_skill_version": installed_version,
        "bundle_version_matches_cli": bundle_version_matches_cli,
        "restart_required_after_install": True,
    }


def install_codex_skill(*, force: bool = False) -> dict[str, Any]:
    destination = codex_skill_path()
    payload = bundled_skill_bytes()
    expected = hashlib.sha256(payload).hexdigest()
    metadata_version = _skill_metadata_version(payload)
    if metadata_version != __version__:
        raise ContractError(
            f"Bundled BlendSmith Skill version {metadata_version!r} does not match CLI/Core version {__version__!r}"
        )

    try:
        destination = _safe_codex_skill_path()
    except SafetyError as exc:
        raise ContractError(f"Refusing unsafe Codex Skill target: {destination}") from exc
    if destination.is_symlink():
        raise ContractError(f"Refusing unsafe Codex Skill target: {destination}")
    if destination.exists():
        if not destination.is_file():
            raise ContractError(f"Refusing unsafe Codex Skill target: {destination}")
        actual = hashlib.sha256(destination.read_bytes()).hexdigest()
        if actual == expected:
            return {
                "skill": SKILL_NAME,
                "path": str(destination),
                "status": "UNCHANGED",
                "sha256": expected,
                "restart_required": False,
            }
        if not force:
            raise ContractError(
                "Installed BlendSmith Skill differs from the bundled Skill; rerun with --force to replace it"
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination = _safe_codex_skill_path()
    except SafetyError as exc:
        raise ContractError(f"Refusing unsafe Codex Skill target: {destination}") from exc
    atomic_write_text(destination, payload.decode("utf-8"))
    actual = hashlib.sha256(destination.read_bytes()).hexdigest()
    if actual != expected:
        raise ContractError("Installed BlendSmith Skill failed SHA-256 verification")
    return {
        "skill": SKILL_NAME,
        "path": str(destination),
        "status": "INSTALLED" if not force else "INSTALLED_OR_UPDATED",
        "sha256": actual,
        "restart_required": True,
    }
