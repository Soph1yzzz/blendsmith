from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_FILES, load_schema
from .errors import BlendSmithError
from .orchestrator import BlendSmith
from .skill_install import install_codex_skill, skill_status
from .version import __version__

CAP_STATES = ["AVAILABLE", "UNAVAILABLE", "BROKEN", "UNKNOWN"]


def _json_file(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _views(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Evidence view must be KEY=PATH: {value}")
        key, raw_path = value.split("=", 1)
        if not key or not raw_path:
            raise ValueError(f"Evidence view must be KEY=PATH: {value}")
        result[key] = Path(raw_path)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blendsmith")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema", help="Print an authoritative BlendSmith JSON contract schema")
    schema.add_argument("name", choices=sorted(SCHEMA_FILES))

    skill_install = sub.add_parser("skill-install", help="Install the bundled BlendSmith Codex Skill")
    skill_install.add_argument("--force", action="store_true", help="Replace an older or modified installed Skill")

    sub.add_parser("skill-status", help="Show whether the bundled BlendSmith Codex Skill is installed")
    sub.add_parser("doctor", help="Check whether CLI/Core and the installed Codex Skill are aligned")

    init = sub.add_parser("init", help="Initialize a BlendSmith project")
    init.add_argument("project")
    init.add_argument("--project-id")

    preflight = sub.add_parser("preflight", help="Capture a runtime capability snapshot")
    preflight.add_argument("--project", required=True)
    preflight.add_argument("--blender")
    preflight.add_argument("--live-gui", choices=CAP_STATES)
    preflight.add_argument("--render-review", choices=CAP_STATES)

    start = sub.add_parser("start", help="Start a run and enter the method-selection gate")
    start.add_argument("--project", required=True)
    start.add_argument("--blender")

    hints = sub.add_parser("method-hints", help="Show provider-neutral method discovery hints")
    hints.add_argument("--project", required=True)
    hints.add_argument("--intent")

    method_plan = sub.add_parser("method-plan", help="Submit work units before production begins")
    method_plan.add_argument("--project", required=True)
    method_plan.add_argument("--input", required=True)

    method_select = sub.add_parser("method-select", help="Submit probed specialized-first method selections")
    method_select.add_argument("--project", required=True)
    method_select.add_argument("--input", required=True)

    status = sub.add_parser("status", help="Show current run state")
    status.add_argument("--project", required=True)

    candidate_add = sub.add_parser("candidate-add", help="Ingest a candidate after method selection")
    candidate_add.add_argument("--project", required=True)
    candidate_add.add_argument("--candidate", required=True)
    candidate_add.add_argument("--dependency", action="append", default=[])

    variant = sub.add_parser(
        "variant-add",
        help="Alias for candidate-add; add another candidate in the current iteration",
    )
    variant.add_argument("--project", required=True)
    variant.add_argument("--candidate", required=True)
    variant.add_argument("--dependency", action="append", default=[])

    select = sub.add_parser("candidate-select", help="Select an existing candidate in the active iteration")
    select.add_argument("--project", required=True)
    select.add_argument("--candidate-id", required=True)

    eb = sub.add_parser("evidence-begin", help="Enter evidence generation")
    eb.add_argument("--project", required=True)

    es = sub.add_parser("evidence-submit", help="Copy and verify evidence images")
    es.add_argument("--project", required=True)
    es.add_argument("--view", action="append", default=[], help="KEY=PATH; repeat for each view")

    vr = sub.add_parser("visual-review", help="Submit an external visual-review contract")
    vr.add_argument("--project", required=True)
    vr.add_argument("--input", required=True)

    fp = sub.add_parser("fix-plan", help="Submit an external bounded fix-plan contract")
    fp.add_argument("--project", required=True)
    fp.add_argument("--input", required=True)

    gr = sub.add_parser("gui-review", help="Submit a live-GUI review contract")
    gr.add_argument("--project", required=True)
    gr.add_argument("--input", required=True)

    aa = sub.add_parser("ai-accept", help="Run final AI acceptance gates")
    aa.add_argument("--project", required=True)

    oa = sub.add_parser("owner-accept", help="Accept the exact reviewed candidate SHA")
    oa.add_argument("--project", required=True)
    oa.add_argument("--sha256", required=True)

    rev = sub.add_parser("owner-revise", help="Request another generation")
    rev.add_argument("--project", required=True)
    rev.add_argument("--reason", required=True)

    reject = sub.add_parser("owner-reject-run", help="Terminate the current run")
    reject.add_argument("--project", required=True)
    reject.add_argument("--reason", required=True)

    cp = sub.add_parser("checkpoint", help="Create and pin a resumable checkpoint")
    cp.add_argument("--project", required=True)
    cp.add_argument("--next-action", default="Resume the saved BlendSmith state.")

    resume = sub.add_parser("resume", help="Validate and resume the active checkpoint")
    resume.add_argument("--project", required=True)

    provenance = sub.add_parser("provenance", help="Attach a provenance contract to the run")
    provenance.add_argument("--project", required=True)
    provenance.add_argument("--input", required=True)

    publish = sub.add_parser("publish", help="Publish the exact human-accepted closure")
    publish.add_argument("--project", required=True)

    gc = sub.add_parser("gc", help="Inspect or apply eligible TTL cleanup")
    gc.add_argument("--project", required=True)
    gc.add_argument("--apply", action="store_true", help="Apply verified cleanup; default is dry-run")

    return parser


def _emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "schema":
            _emit(load_schema(args.name))
            return 0
        if args.command == "skill-install":
            _emit(install_codex_skill(force=args.force))
            return 0
        if args.command == "skill-status":
            _emit(skill_status())
            return 0
        if args.command == "doctor":
            installed = skill_status()
            ready = installed["status"] == "CURRENT"
            _emit(
                {
                    "ready": ready,
                    "cli_version": __version__,
                    "skill": installed,
                    "note": (
                        "Skill bytes match this installed BlendSmith package."
                        if ready
                        else "Repair/update the Skill, restart Codex, then retry."
                    ),
                }
            )
            return 0 if ready else 2
        if args.command == "init":
            app = BlendSmith.init(Path(args.project), project_id=args.project_id)
            _emit({"project": str(app.layout.root), "status": "initialized"})
            return 0

        app = BlendSmith(Path(args.project))
        if args.command == "preflight":
            result = app.preflight(
                blender_path=args.blender,
                live_gui_status=args.live_gui,
                render_review_status=args.render_review,
            )
        elif args.command == "start":
            result = app.start(blender_path=args.blender)
        elif args.command == "method-hints":
            result = app.method_hints(args.intent)
        elif args.command == "method-plan":
            result = app.submit_method_plan(_json_file(args.input))
        elif args.command == "method-select":
            result = app.submit_method_selection(_json_file(args.input))
        elif args.command == "status":
            result = app.status()
        elif args.command in {"candidate-add", "variant-add"}:
            result = app.add_variant(
                Path(args.candidate),
                dependencies=[Path(item) for item in args.dependency],
            )
        elif args.command == "candidate-select":
            result = app.select_candidate(args.candidate_id)
        elif args.command == "evidence-begin":
            result = app.begin_evidence()
        elif args.command == "evidence-submit":
            result = app.submit_evidence(_views(args.view))
        elif args.command == "visual-review":
            result = app.submit_visual_review(_json_file(args.input))
        elif args.command == "fix-plan":
            result = app.submit_fix_plan(_json_file(args.input))
        elif args.command == "gui-review":
            result = app.submit_gui_review(_json_file(args.input))
        elif args.command == "ai-accept":
            result = app.ai_accept()
        elif args.command == "owner-accept":
            result = app.owner_accept(args.sha256)
        elif args.command == "owner-revise":
            result = app.owner_revise(args.reason)
        elif args.command == "owner-reject-run":
            result = app.owner_reject_run(args.reason)
        elif args.command == "checkpoint":
            result = app.checkpoint(args.next_action)
        elif args.command == "resume":
            result = app.resume()
        elif args.command == "provenance":
            result = app.set_provenance(_json_file(args.input))
        elif args.command == "publish":
            result = app.publish()
        elif args.command == "gc":
            result = app.gc(dry_run=not args.apply)
        else:
            parser.error(f"Unhandled command: {args.command}")
            return 2
        _emit(result)
        return 0
    except (BlendSmithError, FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
