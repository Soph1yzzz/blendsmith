from __future__ import annotations

import json
import uuid
from typing import Any

from .blender import probe_blender
from .contracts import validate_contract
from .paths import ensure_within
from .project import ProjectLayout
from .timeutil import iso_now

CAPABILITY_STATES = {"AVAILABLE", "UNAVAILABLE", "BROKEN", "UNKNOWN"}


def latest_snapshot(layout: ProjectLayout) -> dict[str, Any] | None:
    capabilities_root = ensure_within(layout.control, layout.capabilities)
    paths = sorted(capabilities_root.glob("*.json"))
    if not paths:
        return None
    payload = json.loads(paths[-1].read_text(encoding="utf-8"))
    validate_contract("capability_report", payload)
    return payload


def _observed_status(
    name: str,
    observed: str,
    previous: dict[str, Any] | None,
    *,
    actually_probed: bool,
) -> str:
    if observed not in CAPABILITY_STATES:
        raise ValueError(f"Invalid capability state for {name}: {observed}")
    if not actually_probed:
        return observed
    if previous is None:
        return observed
    previous_status = previous.get("capabilities", {}).get(name, {}).get("status")
    if previous_status == "AVAILABLE" and observed == "UNAVAILABLE":
        return "BROKEN"
    return observed


def capture_capabilities(
    layout: ProjectLayout,
    *,
    blender_path: str | None = None,
    live_gui_status: str | None = None,
    render_review_status: str | None = None,
) -> dict[str, Any]:
    previous = latest_snapshot(layout)
    blender_attempts = 0
    blender = None
    for attempt in range(1, 5):
        blender_attempts = attempt
        blender = probe_blender(blender_path)
        if blender.status != "BROKEN":
            break
    assert blender is not None
    captured_at = iso_now()

    blender_status = _observed_status(
        "blender_backend",
        blender.status,
        previous,
        actually_probed=True,
    )
    gui_status = _observed_status(
        "live_blender_gui_review",
        live_gui_status or "UNKNOWN",
        previous,
        actually_probed=live_gui_status is not None,
    )
    review_status = _observed_status(
        "render_image_review",
        render_review_status or "UNKNOWN",
        previous,
        actually_probed=render_review_status is not None,
    )

    report = {
        "schema_version": 1,
        "captured_at": captured_at,
        "capabilities": {
            "filesystem": {
                "status": "AVAILABLE",
                "details": {"root": str(layout.root)},
                "observed_at": captured_at,
            },
            "blender_backend": {
                "status": blender_status,
                "details": {
                    **blender.as_dict(),
                    "probe_attempts": blender_attempts,
                    "probe_retries": blender_attempts - 1,
                },
                "observed_at": captured_at,
            },
            "render_image_review": {
                "status": review_status,
                "details": {"source": "explicit" if render_review_status else "not_probed"},
                "observed_at": captured_at if render_review_status else None,
            },
            "live_blender_gui_review": {
                "status": gui_status,
                "details": {"source": "explicit" if live_gui_status else "not_probed"},
                "observed_at": captured_at if live_gui_status else None,
            },
        },
    }
    validate_contract("capability_report", report)
    filename = captured_at.replace(":", "-").replace("+", "_") + f"-{uuid.uuid4().hex[:8]}.json"
    from .paths import atomic_write_json

    atomic_write_json(layout.capabilities / filename, report)
    return report
