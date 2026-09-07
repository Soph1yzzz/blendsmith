from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .capabilities import capture_capabilities, latest_snapshot
from .checkpoint import materialize_checkpoint, restore_checkpoint_methods, verify_checkpoint
from .closure import materialize_candidate_closure, verify_candidate_manifest
from .contracts import validate_contract
from .errors import AuthorityError, CapabilityError, ContractError, IntegrityError
from .evidence import materialize_evidence, verify_evidence_bundle
from .gc import execute_gc, plan_gc
from .hashing import sha256_file
from .method_cache import load_method_cache, method_cache_fingerprint, save_method_cache
from .methods import load_method_hints, validate_method_plan, validate_method_selection
from .paths import append_jsonl, atomic_write_json, ensure_within
from .project import initialize_project, load_project
from .provenance import save_provenance, validate_for_candidate
from .publication import publish_verified, retract_current_publication, verify_current_publication
from .retention import RetentionRegistry
from .review import (
    validate_change_impact,
    validate_fix_plan,
    validate_global_reassessment,
    validate_live_gui_review,
    validate_visual_review,
)
from .run_store import create_run, load_current_run, save_run, transition
from .state_machine import RunState
from .timeutil import iso_now, parse_iso


class BlendSmith:
    def __init__(self, project_root: Path):
        self.layout, self.config = load_project(project_root)
        self.retention = RetentionRegistry(self.layout)

    @classmethod
    def init(cls, project_root: Path, *, project_id: str | None = None) -> BlendSmith:
        initialize_project(project_root, project_id=project_id)
        return cls(project_root)

    def preflight(
        self,
        *,
        blender_path: str | None = None,
        live_gui_status: str | None = None,
        render_review_status: str | None = None,
    ) -> dict[str, Any]:
        return capture_capabilities(
            self.layout,
            blender_path=blender_path,
            live_gui_status=live_gui_status,
            render_review_status=render_review_status,
        )

    def start(self, *, blender_path: str | None = None) -> dict[str, Any]:
        run_dir, run = create_run(self.layout, self.config["project_id"])
        transition(run_dir, run, RunState.INSTALLATION_PIN_RESOLVED, reason="installation lock present")
        transition(run_dir, run, RunState.ENVIRONMENT_PIN_RESOLVED, reason="environment identity lock present")
        transition(run_dir, run, RunState.CAPABILITY_PREFLIGHT, reason="begin runtime capability preflight")
        report = (
            self.preflight(blender_path=blender_path)
            if blender_path is not None
            else latest_snapshot(self.layout) or self.preflight()
        )
        blender_status = report["capabilities"]["blender_backend"]["status"]
        if blender_status != "AVAILABLE":
            probe_details = report["capabilities"]["blender_backend"].get("details", {})
            attempts = int(probe_details.get("probe_attempts", 1))
            retries = int(probe_details.get("probe_retries", max(0, attempts - 1)))
            self._owner_action(
                run_dir,
                run,
                category="blender_backend_unavailable",
                failed_operation="start",
                retryable=blender_status == "BROKEN",
                attempts=attempts,
                retries=retries,
                requested="Restore or configure a compatible Blender runtime and rerun preflight.",
            )
            return run
        transition(run_dir, run, RunState.BLENDER_PREFLIGHT, reason="Blender backend available")
        run["metadata"]["method_selection_round"] = 0
        run["metadata"]["method_plan_revision"] = 0
        run["metadata"]["local_repair_streak"] = 0
        run["metadata"]["method_plan_history"] = []
        save_run(run_dir, run)
        transition(
            run_dir,
            run,
            RunState.AWAITING_METHOD_PLAN,
            reason="decompose production work before candidate generation",
        )
        return run

    def method_hints(self, intent: str | None = None) -> dict[str, Any]:
        return load_method_hints(intent)

    def method_cache(self, intent: str | None = None) -> dict[str, Any]:
        return load_method_cache(self.layout, self.config, intent=intent)

    def submit_method_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.AWAITING_METHOD_PLAN:
            raise ContractError("Method plan is not currently awaited")
        validate_method_plan(payload, run=run)
        revision = int(run["metadata"].get("method_plan_revision", 0))
        path = run_dir / "methods" / f"method-plan-r{revision}.json"
        atomic_write_json(path, payload)
        plan_sha = sha256_file(path)
        run["metadata"]["method_plan_path"] = path.relative_to(run_dir).as_posix()
        run["metadata"]["method_plan_id"] = payload["plan_id"]
        run["metadata"]["method_plan_sha256"] = plan_sha
        history = run["metadata"].setdefault("method_plan_history", [])
        history.append(
            {
                "revision": revision,
                "path": path.relative_to(run_dir).as_posix(),
                "sha256": plan_sha,
                "supersedes_sha256": payload.get("supersedes_sha256"),
            }
        )
        run["metadata"].pop("previous_method_plan_sha256", None)
        run["metadata"].pop("pending_plan_revision_reason", None)
        save_run(run_dir, run)
        transition(run_dir, run, RunState.METHOD_PLAN_VALIDATED, reason="method work plan validated")
        transition(
            run_dir,
            run,
            RunState.AWAITING_METHOD_SELECTION,
            reason="specialized production methods must be evaluated before generation",
        )
        return run

    def submit_method_selection(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.AWAITING_METHOD_SELECTION:
            raise ContractError("Method selection is not currently awaited")
        plan_path = self._method_plan_file_path(run_dir, run)
        plan_sha = sha256_file(plan_path)
        if plan_sha != run["metadata"].get("method_plan_sha256"):
            raise IntegrityError("Validated method plan bytes changed before method selection")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        cache_identity = method_cache_fingerprint(self.layout, self.config)
        expected_cache_fingerprint = (
            cache_identity.get("fingerprint")
            if cache_identity.get("status") == "AVAILABLE"
            else None
        )
        validate_method_selection(
            payload,
            run=run,
            plan=plan,
            project_config=self.config,
            expected_plan_sha256=plan_sha,
            expected_cache_fingerprint=expected_cache_fingerprint,
        )
        round_id = int(run["metadata"].get("method_selection_round", 0))
        path = run_dir / "methods" / f"method-selection-r{round_id}.json"
        atomic_write_json(path, payload)
        run["metadata"]["method_selection_path"] = path.relative_to(run_dir).as_posix()
        run["metadata"]["method_selection_sha256"] = sha256_file(path)
        history = run["metadata"].setdefault("method_selection_history", [])
        history.append(path.relative_to(run_dir).as_posix())
        cached = save_method_cache(
            self.layout,
            self.config,
            plan=plan,
            selection=payload,
        )
        if cached is not None:
            run["metadata"]["method_cache_fingerprint"] = cached["fingerprint"]
        save_run(run_dir, run)
        transition(
            run_dir,
            run,
            RunState.METHOD_SELECTION_VALIDATED,
            reason="specialized-first method policy validated",
        )
        transition(run_dir, run, RunState.WORKING, reason="external production may proceed")
        return run

    def add_variant(self, candidate: Path, *, dependencies: Iterable[Path] = ()) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.WORKING:
            raise ContractError("Candidates may be added only while WORKING")
        self._validate_current_method_selection(run_dir, run)
        iteration = run["iteration"]
        existing = []
        for path in (run_dir / "candidates").glob("*/candidate.manifest.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("iteration") == iteration:
                existing.append(payload)
        variant_index = len(existing) + 1
        limit = self.config["qa"]["max_variants_per_iteration"]
        if variant_index > limit:
            raise ContractError(f"Candidate variant budget exceeded for iteration {iteration}: max {limit}")
        self._materialize_active_candidate(
            run_dir,
            run,
            candidate=Path(candidate),
            dependencies=list(dependencies),
            iteration=iteration,
            variant_index=variant_index,
        )
        save_run(run_dir, run)
        return run

    def select_candidate(self, candidate_id: str) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.WORKING:
            raise ContractError("Candidate selection is allowed only while WORKING")
        candidate_root = ensure_within(run_dir / "candidates", run_dir / "candidates" / candidate_id)
        manifest_path = ensure_within(candidate_root, candidate_root / "candidate.manifest.json")
        manifest = verify_candidate_manifest(manifest_path)
        if manifest["run_id"] != run["run_id"] or manifest["candidate_id"] != candidate_id:
            raise IntegrityError("Candidate manifest identity does not match the selected candidate")
        if manifest["iteration"] != run["iteration"]:
            raise ContractError("Only a candidate from the active iteration may be selected")
        run["active_candidate_id"] = candidate_id
        run["metadata"]["candidate_manifest_path"] = manifest_path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        return run

    def begin_evidence(self) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.WORKING:
            raise ContractError("Evidence generation may begin only while WORKING")
        if not run.get("active_candidate_id"):
            raise ContractError("A method-selected candidate must be ingested before evidence generation")
        manifest = verify_candidate_manifest(self._manifest_path(run_dir, run))
        self._verify_candidate_method_binding(run_dir, run, manifest)
        if manifest["iteration"] != run["iteration"]:
            raise ContractError("Active candidate belongs to an earlier improvement iteration")
        transition(run_dir, run, RunState.RENDERING_EVIDENCE, reason="begin evidence generation")
        return run

    def submit_evidence(self, views: dict[str, Path]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.RENDERING_EVIDENCE:
            raise ContractError("Evidence may be submitted only while RENDERING_EVIDENCE")
        bundle_path, _ = materialize_evidence(
            run_dir,
            candidate_id=run["active_candidate_id"],
            views=views,
            minimum_width=self.config["qa"]["minimum_render_width"],
            minimum_height=self.config["qa"]["minimum_render_height"],
            review_max_edge=self.config["qa"]["review_max_edge"],
            tile_size=self.config["qa"]["tile_size"],
            tile_overlap=self.config["qa"]["tile_overlap"],
            jpeg_quality=self.config["qa"]["jpeg_quality"],
            evidence_profiles=self.config["qa"].get("evidence_profiles", {}),
        )
        run["metadata"]["evidence_bundle_path"] = bundle_path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        transition(run_dir, run, RunState.EVIDENCE_READY, reason="evidence bundle verified")
        transition(run_dir, run, RunState.AWAITING_VISUAL_REVIEW, reason="external visual review required")
        return run

    def submit_visual_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.AWAITING_VISUAL_REVIEW:
            raise ContractError("Visual review is not currently awaited")
        manifest_path = self._manifest_path(run_dir, run)
        bundle_path = self._evidence_path(run_dir, run)
        bundle = verify_evidence_bundle(run_dir, bundle_path)
        known_views = {item["key"] for item in bundle["views"]}
        unknown_opened = set(payload.get("opened_evidence", [])) - known_views
        if unknown_opened:
            raise ContractError(f"Visual review cites unknown evidence: {sorted(unknown_opened)}")
        validate_visual_review(
            payload,
            run=run,
            manifest_path=manifest_path,
            project_config=self.config,
        )
        path = run_dir / "reviews" / f"visual-i{run['iteration']}.json"
        atomic_write_json(path, payload)
        run["metadata"]["visual_review_path"] = path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        transition(run_dir, run, RunState.VISUAL_REVIEW_VALIDATED, reason="visual review contract validated")
        if payload["verdict"] == "ACCEPT":
            transition(run_dir, run, RunState.RENDER_QA_ACCEPTED, reason="render evidence QA accepted")
            transition(run_dir, run, RunState.LIVE_GUI_DECISION, reason="resolve live GUI requirement")
            self._resolve_gui_requirement(run_dir, run)
        elif payload["verdict"] == "REVISE":
            run["metadata"]["change_impact_source"] = "VISUAL_REVIEW"
            save_run(run_dir, run)
            transition(
                run_dir,
                run,
                RunState.AWAITING_CHANGE_IMPACT,
                reason="classify the revision at the correct abstraction level",
            )
        else:
            self._owner_action(
                run_dir,
                run,
                category="visual_review_blocked",
                failed_operation="visual_review",
                retryable=False,
                attempts=1,
                retries=0,
                requested="Resolve the blocking visual-review condition.",
            )
        return run

    def submit_change_impact(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.AWAITING_CHANGE_IMPACT:
            raise ContractError("Change-impact classification is not currently awaited")

        source = run["metadata"].get("change_impact_source")
        if payload["source"] != source:
            raise ContractError(f"Change-impact source mismatch: expected {source}, got {payload['source']}")

        plan_path = self._method_plan_file_path(run_dir, run)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        selection_path = self._method_selection_file_path(run_dir, run)
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        source_review = self._source_review_for_change_impact(run_dir, run, source)
        validate_change_impact(
            payload,
            run=run,
            manifest_path=self._manifest_path(run_dir, run),
            method_plan=plan,
            method_selection=selection,
            source_review=source_review,
        )

        path = run_dir / "reviews" / f"change-impact-i{run['iteration']}.json"
        atomic_write_json(path, payload)
        run["metadata"]["change_impact_path"] = path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        transition(run_dir, run, RunState.CHANGE_IMPACT_VALIDATED, reason=f"change classified as {payload['scope']}")

        scope = payload["scope"]
        if scope == "LOCAL":
            streak = int(run["metadata"].get("local_repair_streak", 0)) + 1
            run["metadata"]["local_repair_streak"] = streak
            save_run(run_dir, run)
            threshold = int(
                self.config.get("production_structure", {}).get(
                    "global_reassessment_after_local_repairs",
                    2,
                )
            )
            if payload["global_reassessment_recommended"] or streak >= threshold:
                transition(
                    run_dir,
                    run,
                    RunState.AWAITING_GLOBAL_REASSESSMENT,
                    reason="local repair streak requires a whole-plan reassessment",
                )
            else:
                transition(run_dir, run, RunState.AWAITING_FIX_PLAN, reason="bounded local repair authorized")
        elif scope == "METHOD":
            run["metadata"]["local_repair_streak"] = 0
            save_run(run_dir, run)
            self._prepare_method_reconsideration(run_dir, run, reason="change-impact gate requires method reselection")
        elif scope in {"STRUCTURAL", "CONTRACT"}:
            run["metadata"]["local_repair_streak"] = 0
            run["metadata"]["stale_work_units"] = self._downstream_work_units(
                plan,
                payload["affected_work_units"],
            )
            save_run(run_dir, run)
            self._prepare_plan_revision(run_dir, run, reason=payload["upstream_change_summary"])
        return run

    def submit_global_reassessment(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.AWAITING_GLOBAL_REASSESSMENT:
            raise ContractError("Global reassessment is not currently awaited")
        plan = json.loads(self._method_plan_file_path(run_dir, run).read_text(encoding="utf-8"))
        validate_global_reassessment(
            payload,
            run=run,
            manifest_path=self._manifest_path(run_dir, run),
            method_plan=plan,
        )
        path = run_dir / "reviews" / f"global-reassessment-i{run['iteration']}.json"
        atomic_write_json(path, payload)
        run["metadata"]["global_reassessment_path"] = path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        transition(
            run_dir,
            run,
            RunState.GLOBAL_REASSESSMENT_VALIDATED,
            reason=f"global reassessment decided {payload['decision']}",
        )

        decision = payload["decision"]
        if decision == "CONTINUE_LOCAL":
            run["metadata"]["local_repair_streak"] = 0
            save_run(run_dir, run)
            transition(run_dir, run, RunState.AWAITING_FIX_PLAN, reason="global view still supports local repair")
        elif decision == "RESELECT_METHOD":
            run["metadata"]["local_repair_streak"] = 0
            save_run(run_dir, run)
            self._prepare_method_reconsideration(run_dir, run, reason="global reassessment requires method reselection")
        elif decision in {"REVISE_STRUCTURE", "REVISE_CONTRACT"}:
            run["metadata"]["local_repair_streak"] = 0
            affected = payload.get("affected_work_units") or self._read_metadata_json(
                run_dir,
                run,
                "change_impact_path",
            )["affected_work_units"]
            run["metadata"]["stale_work_units"] = self._downstream_work_units(plan, affected)
            save_run(run_dir, run)
            self._prepare_plan_revision(run_dir, run, reason=payload["rationale"])
        return run

    def submit_fix_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.AWAITING_FIX_PLAN:
            raise ContractError("Fix plan is not currently awaited")
        change_impact = self._read_metadata_json(run_dir, run, "change_impact_path")
        source_review = self._source_review_for_change_impact(
            run_dir,
            run,
            change_impact["source"],
        )
        validate_fix_plan(
            payload,
            run=run,
            manifest_path=self._manifest_path(run_dir, run),
            source_review=source_review,
            change_impact=change_impact,
        )
        path = run_dir / "reviews" / f"fix-plan-i{run['iteration']}.json"
        atomic_write_json(path, payload)
        run["metadata"]["fix_plan_path"] = path.relative_to(run_dir).as_posix()
        run["iteration"] += 1
        save_run(run_dir, run)
        transition(run_dir, run, RunState.FIX_PLAN_VALIDATED, reason="bounded fix plan validated")
        transition(run_dir, run, RunState.WORKING, reason="external repair may proceed")
        return run

    def submit_gui_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.AWAITING_LIVE_GUI_REVIEW:
            raise ContractError("Live GUI review is not currently awaited")
        status = self._gui_capability_status()
        validate_live_gui_review(
            payload,
            run=run,
            manifest_path=self._manifest_path(run_dir, run),
            current_capability_status=status,
            project_config=self.config,
        )
        path = run_dir / "reviews" / f"gui-i{run['iteration']}.json"
        atomic_write_json(path, payload)
        run["metadata"]["live_gui_review_path"] = path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        transition(run_dir, run, RunState.LIVE_GUI_VALIDATED, reason="live GUI contract validated")
        if payload["status"] == "PASS":
            run["assurance_level"] = "live_gui_verified"
            save_run(run_dir, run)
            transition(run_dir, run, RunState.FINAL_AI_VALIDATION, reason="live GUI QA passed")
        elif payload["status"] == "REVISE":
            run["metadata"]["change_impact_source"] = "LIVE_GUI_REVIEW"
            save_run(run_dir, run)
            transition(
                run_dir,
                run,
                RunState.AWAITING_CHANGE_IMPACT,
                reason="exploratory GUI review found a change requiring impact classification",
            )
        else:
            self._owner_action(
                run_dir,
                run,
                category="live_gui_blocked",
                failed_operation="live_gui_review",
                retryable=False,
                attempts=1,
                retries=0,
                requested="Resolve the blocking live GUI condition.",
            )
        return run

    def ai_accept(self) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.FINAL_AI_VALIDATION:
            raise ContractError("Run is not ready for final AI validation")
        manifest = verify_candidate_manifest(self._manifest_path(run_dir, run))
        self._verify_candidate_method_binding(run_dir, run, manifest)
        review = self._read_metadata_json(run_dir, run, "visual_review_path")
        validate_visual_review(
            review,
            run=run,
            manifest_path=self._manifest_path(run_dir, run),
            project_config=self.config,
        )
        if review["verdict"] != "ACCEPT":
            raise ContractError("Latest visual review is not ACCEPT")
        verify_evidence_bundle(run_dir, self._evidence_path(run_dir, run))
        gui_status = self._gui_capability_status()
        if gui_status == "AVAILABLE":
            gui_review = self._read_metadata_json(run_dir, run, "live_gui_review_path")
            validate_live_gui_review(
                gui_review,
                run=run,
                manifest_path=self._manifest_path(run_dir, run),
                current_capability_status=gui_status,
                project_config=self.config,
            )
            if gui_review["status"] != "PASS":
                raise ContractError("Available live GUI capability requires PASS")
        elif gui_status != "UNAVAILABLE":
            raise CapabilityError(f"Live GUI capability must be AVAILABLE or explicitly UNAVAILABLE, got {gui_status}")
        run["metadata"]["owner_review_candidate_sha256"] = manifest["candidate_sha256"]
        save_run(run_dir, run)
        transition(run_dir, run, RunState.AI_ACCEPTED, reason="all AI acceptance gates passed")
        transition(run_dir, run, RunState.OWNER_REVIEW, reason="human authority gate required")
        return run

    def owner_accept(self, candidate_sha256: str) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        state = RunState(run["state"])
        if state not in {RunState.OWNER_REVIEW, RunState.HUMAN_ACCEPTED_SHA_LOCKED}:
            raise AuthorityError("Owner acceptance is allowed only during OWNER_REVIEW or acceptance recovery")
        manifest_path = self._manifest_path(run_dir, run)
        manifest = verify_candidate_manifest(manifest_path)
        self._verify_candidate_method_binding(run_dir, run, manifest)
        bound_sha = run["metadata"].get("owner_review_candidate_sha256")
        if candidate_sha256 != bound_sha or candidate_sha256 != manifest["candidate_sha256"]:
            raise AuthorityError("Owner ACCEPT must match the exact candidate SHA presented for review")

        if state == RunState.OWNER_REVIEW:
            decision = {
                "schema_version": 1,
                "run_id": run["run_id"],
                "decision": "ACCEPT",
                "decided_at": iso_now(),
                "reason": None,
                "candidate_sha256": candidate_sha256,
            }
            validate_contract("owner_decision", decision)
            append_jsonl(self.layout.history / "owner_decisions.jsonl", decision)
            run["accepted_candidate_sha256"] = candidate_sha256
            save_run(run_dir, run)
            transition(
                run_dir,
                run,
                RunState.HUMAN_ACCEPTED_SHA_LOCKED,
                reason="owner accepted exact candidate SHA",
            )
        elif run.get("accepted_candidate_sha256") != candidate_sha256:
            raise AuthorityError("Interrupted acceptance no longer matches the accepted SHA")

        candidate_root = manifest_path.parent
        relative_root = candidate_root.relative_to(self.layout.control).as_posix()
        record = next(
            (
                item
                for item in self.retention.records().values()
                if item["class"] == "PINNED_CURRENT_FINAL" and item["relative_path"] == relative_root
            ),
            None,
        )
        if record is None:
            record = self.retention.register(candidate_root, "PINNED_CURRENT_FINAL")
        run["metadata"]["current_final_retention_id"] = record["record_id"]
        save_run(run_dir, run)
        transition(run_dir, run, RunState.CURRENT_FINAL_PINNED, reason="accepted dependency closure pinned")
        return run

    def owner_revise(self, reason: str) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        state = RunState(run["state"])
        if state not in {
            RunState.OWNER_REVIEW,
            RunState.HUMAN_ACCEPTED_SHA_LOCKED,
            RunState.CURRENT_FINAL_PINNED,
            RunState.PUBLISHED,
        }:
            raise AuthorityError(f"Revision cannot be requested from {state}")
        manifest = verify_candidate_manifest(self._manifest_path(run_dir, run))
        decision = {
            "schema_version": 1,
            "run_id": run["run_id"],
            "decision": "REQUEST_REVISION",
            "decided_at": iso_now(),
            "reason": reason,
            "candidate_sha256": manifest["candidate_sha256"],
        }
        validate_contract("owner_decision", decision)
        append_jsonl(self.layout.history / "owner_decisions.jsonl", decision)
        transition(run_dir, run, RunState.OWNER_REVISION_REQUESTED, reason="owner requested revision")

        if self.layout.publication_current.exists():
            retract_current_publication(self.layout, run_dir=run_dir)
            transition(run_dir, run, RunState.PUBLICATION_RETRACTED, reason="current publication retracted")

        run["accepted_candidate_sha256"] = None
        run["assurance_level"] = None
        run["metadata"]["pending_owner_revision_reason"] = reason
        run["metadata"]["pending_owner_revision_issue_id"] = f"owner-revision-i{run['iteration']}"
        run["metadata"]["change_impact_source"] = "OWNER_REVISION"
        save_run(run_dir, run)
        transition(
            run_dir,
            run,
            RunState.AWAITING_CHANGE_IMPACT,
            reason="owner revision must be classified before choosing a repair depth",
        )
        return run

    def owner_reject_run(self, reason: str) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.OWNER_REVIEW:
            raise AuthorityError("REJECT_RUN is allowed only during OWNER_REVIEW")
        manifest_path = self._manifest_path(run_dir, run)
        manifest = verify_candidate_manifest(manifest_path)
        decision = {
            "schema_version": 1,
            "run_id": run["run_id"],
            "decision": "REJECT_RUN",
            "decided_at": iso_now(),
            "reason": reason,
            "candidate_sha256": manifest["candidate_sha256"],
        }
        validate_contract("owner_decision", decision)
        append_jsonl(self.layout.history / "owner_decisions.jsonl", decision)
        self.retention.register(
            manifest_path.parent,
            "EPHEMERAL",
            ttl_hours=self.config["storage"]["ephemeral_ttl_hours"],
        )
        transition(run_dir, run, RunState.OWNER_REJECTED_RUN, reason="owner rejected run")
        return run

    def checkpoint(self, next_action: str = "Resume the saved BlendSmith state.") -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        resume_state = RunState(run["state"])
        run["resume_state"] = resume_state.value
        save_run(run_dir, run)
        transition(run_dir, run, RunState.CHECKPOINTING, reason="checkpoint requested")
        method_plan_path, method_selection_path = self._checkpoint_method_paths(run_dir, run)
        checkpoint_path, checkpoint = materialize_checkpoint(
            run_dir,
            run=run,
            candidate_manifest_path=(
                self._manifest_path(run_dir, run) if run.get("active_candidate_id") else None
            ),
            method_plan_path=method_plan_path,
            method_selection_path=method_selection_path,
            resume_state=resume_state.value,
            next_action=next_action,
            review_path=run["metadata"].get("visual_review_path"),
            fix_plan_path=run["metadata"].get("fix_plan_path"),
        )
        record = self.retention.register(checkpoint_path.parent, "PINNED_ACTIVE_CHECKPOINT")
        self._replace_active_checkpoint(run, checkpoint, record)
        save_run(run_dir, run)
        transition(run_dir, run, RunState.CHECKPOINTED, reason="checkpoint snapshot verified and pinned")
        transition(run_dir, run, RunState.RESUMABLE, reason="run may be resumed")
        return run

    def resume(self) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        state = RunState(run["state"])
        if state == RunState.CHECKPOINTING:
            saved_state = run.get("resume_state")
            if not saved_state:
                raise IntegrityError("Interrupted checkpoint has no recorded resume state")
            method_plan_path, method_selection_path = self._checkpoint_method_paths(run_dir, run)
            checkpoint_path, checkpoint = materialize_checkpoint(
                run_dir,
                run=run,
                candidate_manifest_path=(
                    self._manifest_path(run_dir, run) if run.get("active_candidate_id") else None
                ),
                method_plan_path=method_plan_path,
                method_selection_path=method_selection_path,
                resume_state=saved_state,
                next_action="Resume the interrupted checkpoint.",
                review_path=run["metadata"].get("visual_review_path"),
                fix_plan_path=run["metadata"].get("fix_plan_path"),
            )
            record = self.retention.register(checkpoint_path.parent, "PINNED_ACTIVE_CHECKPOINT")
            self._replace_active_checkpoint(run, checkpoint, record)
            save_run(run_dir, run)
            transition(run_dir, run, RunState.CHECKPOINTED, reason="interrupted checkpoint recovered")
            transition(run_dir, run, RunState.RESUMABLE, reason="recovered checkpoint is resumable")
        elif state == RunState.CHECKPOINTED:
            transition(run_dir, run, RunState.RESUMABLE, reason="completed checkpoint is resumable")
        elif state != RunState.RESUMABLE:
            raise ContractError("Run is not in a resumable checkpoint state")

        checkpoint_rel = run["metadata"].get("active_checkpoint_path")
        if not checkpoint_rel:
            raise IntegrityError("No active checkpoint is recorded")
        checkpoint_path = ensure_within(run_dir, run_dir / checkpoint_rel)
        checkpoint = verify_checkpoint(checkpoint_path)
        resume_state = RunState(checkpoint["resume_state"])

        restored_methods = restore_checkpoint_methods(checkpoint_path, run_dir)
        if restored_methods["method_plan_path"] is not None:
            run["metadata"]["method_plan_path"] = restored_methods["method_plan_path"]
            run["metadata"]["method_plan_id"] = restored_methods["method_plan_id"]
            run["metadata"]["method_plan_revision"] = restored_methods["method_plan_revision"]
            run["metadata"]["method_plan_sha256"] = restored_methods["method_plan_sha256"]
        else:
            run["metadata"].pop("method_plan_path", None)
            run["metadata"].pop("method_plan_id", None)
            run["metadata"]["method_plan_revision"] = checkpoint["method_plan_revision"]
            run["metadata"].pop("method_plan_sha256", None)
        run["metadata"]["method_selection_round"] = checkpoint["method_selection_round"]
        if restored_methods["method_selection_path"] is not None:
            run["metadata"]["method_selection_path"] = restored_methods["method_selection_path"]
            run["metadata"]["method_selection_sha256"] = restored_methods["method_selection_sha256"]
            if restored_methods["method_selection_round"] != checkpoint["method_selection_round"]:
                raise IntegrityError("Restored method-selection round does not match checkpoint state")
        else:
            run["metadata"].pop("method_selection_path", None)
            run["metadata"].pop("method_selection_sha256", None)

        if checkpoint["candidate_manifest_path"] is not None:
            snapshot_manifest_path = checkpoint_path.parent / checkpoint["candidate_manifest_path"]
            snapshot_manifest = verify_candidate_manifest(snapshot_manifest_path)
            candidate_id = snapshot_manifest["candidate_id"]
            canonical_manifest_path = ensure_within(
                run_dir / "candidates",
                run_dir / "candidates" / candidate_id / "candidate.manifest.json",
            )
            try:
                canonical_manifest = verify_candidate_manifest(canonical_manifest_path)
            except (FileNotFoundError, IntegrityError):
                canonical_manifest = None
            if (
                canonical_manifest is None
                or canonical_manifest["candidate_sha256"] != checkpoint["candidate_sha256"]
                or canonical_manifest["closure_sha256"] != checkpoint["closure_sha256"]
            ):
                raise IntegrityError(
                    "Canonical candidate no longer matches the pinned checkpoint; automatic overwrite is refused"
                )
            run["active_candidate_id"] = candidate_id
            run["metadata"]["candidate_manifest_path"] = canonical_manifest_path.relative_to(run_dir).as_posix()
        else:
            run["active_candidate_id"] = None
            run["metadata"].pop("candidate_manifest_path", None)
        run["resume_state"] = None
        save_run(run_dir, run)
        transition(run_dir, run, resume_state, reason="checkpoint identity revalidated", resume_target=resume_state)
        return run

    def publish(self) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        state = RunState(run["state"])
        if state not in {RunState.CURRENT_FINAL_PINNED, RunState.PUBLICATION_STAGING}:
            raise AuthorityError("Publication requires CURRENT_FINAL_PINNED or publication recovery")
        manifest_path = self._manifest_path(run_dir, run)
        manifest = verify_candidate_manifest(manifest_path)
        self._verify_candidate_method_binding(run_dir, run, manifest)
        provenance = None
        if run["metadata"].get("provenance_path"):
            provenance = self._read_metadata_json(run_dir, run, "provenance_path")
        validate_for_candidate(
            manifest,
            provenance,
            required=self.config["provenance"]["required_for_publication"],
        )
        if state == RunState.CURRENT_FINAL_PINNED:
            transition(run_dir, run, RunState.PUBLICATION_STAGING, reason="stage exact accepted closure")

        if self.layout.publication_current.exists():
            publication = verify_current_publication(self.layout)
            if (
                publication["run_id"] != run["run_id"]
                or publication["candidate_id"] != manifest["candidate_id"]
                or publication["accepted_candidate_sha256"] != run.get("accepted_candidate_sha256")
            ):
                raise IntegrityError("Existing current publication does not match the interrupted publication")
            current = self.layout.publication_current
        else:
            current, publication = publish_verified(
                self.layout,
                run=run,
                candidate_manifest_path=manifest_path,
            )
        run["metadata"]["publication_path"] = str(current)
        run["metadata"]["publication_manifest"] = publication
        save_run(run_dir, run)
        transition(run_dir, run, RunState.PUBLISHED, reason="staged hashes matched accepted bytes")
        return run

    def set_provenance(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        path = run_dir / "provenance.json"
        save_provenance(path, payload)
        run["metadata"]["provenance_path"] = path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        return run

    def gc(self, *, dry_run: bool = True) -> list[dict[str, Any]]:
        return plan_gc(self.retention) if dry_run else execute_gc(self.retention)

    def status(self) -> dict[str, Any]:
        _, run = load_current_run(self.layout)
        return run

    def next_action(self) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        state = RunState(run["state"])
        commands = {
            RunState.AWAITING_METHOD_PLAN: (
                "blendsmith method-plan --project <project> --input <method_plan.json>"
            ),
            RunState.AWAITING_METHOD_SELECTION: (
                "blendsmith method-select --project <project> --input <method_selection.json>"
            ),
            RunState.RENDERING_EVIDENCE: (
                "blendsmith evidence-submit --project <project> --view KEY=PATH"
            ),
            RunState.AWAITING_VISUAL_REVIEW: (
                "blendsmith visual-review --project <project> --input <visual_review.json>"
            ),
            RunState.AWAITING_CHANGE_IMPACT: (
                "blendsmith change-impact --project <project> --input <change_impact.json>"
            ),
            RunState.AWAITING_GLOBAL_REASSESSMENT: (
                "blendsmith global-reassess --project <project> --input <global_reassessment.json>"
            ),
            RunState.AWAITING_FIX_PLAN: (
                "blendsmith fix-plan --project <project> --input <fix_plan.json>"
            ),
            RunState.AWAITING_LIVE_GUI_REVIEW: (
                "blendsmith gui-review --project <project> --input <live_gui_review.json>"
            ),
            RunState.FINAL_AI_VALIDATION: "blendsmith ai-accept --project <project>",
            RunState.OWNER_REVIEW: "owner decision required: ACCEPT / REQUEST_REVISION / REJECT_RUN",
            RunState.OWNER_ACTION_REQUIRED: (
                "blendsmith owner-action-recover --project <project> after resolving and "
                "reprobing the recorded condition"
            ),
            RunState.RESUMABLE: "blendsmith resume --project <project>",
        }
        if state == RunState.WORKING:
            command = (
                "blendsmith evidence-begin --project <project>"
                if run.get("active_candidate_id")
                else "blendsmith candidate-add --project <project> --candidate <scene.blend>"
            )
        else:
            command = commands.get(state)

        result: dict[str, Any] = {
            "run_id": run["run_id"],
            "state": state.value,
            "iteration": run["iteration"],
            "next_command": command,
            "method_plan_revision": run["metadata"].get("method_plan_revision"),
            "method_plan_sha256": run["metadata"].get("method_plan_sha256"),
            "method_selection_round": run["metadata"].get("method_selection_round"),
            "method_selection_sha256": run["metadata"].get("method_selection_sha256"),
            "method_cache": load_method_cache(self.layout, self.config),
            "active_candidate_id": run.get("active_candidate_id"),
        }
        if run.get("active_candidate_id"):
            manifest_path = self._manifest_path(run_dir, run)
            manifest = verify_candidate_manifest(manifest_path)
            candidate_record = next(item for item in manifest["files"] if item["role"] == "candidate")
            candidate_path = ensure_within(
                manifest_path.parent / "closure",
                manifest_path.parent / "closure" / candidate_record["pinned_path"],
            )
            result["candidate_sha256"] = manifest["candidate_sha256"]
            result["candidate_path"] = str(candidate_path)
        owner_action_path = run["metadata"].get("owner_action_path")
        if owner_action_path:
            result["owner_action"] = self._read_metadata_json(run_dir, run, "owner_action_path")
        return result

    def recover_owner_action(self) -> dict[str, Any]:
        run_dir, run = load_current_run(self.layout)
        if RunState(run["state"]) != RunState.OWNER_ACTION_REQUIRED:
            raise ContractError("Owner-action recovery requires OWNER_ACTION_REQUIRED")
        action = self._read_metadata_json(run_dir, run, "owner_action_path")
        validate_contract("owner_action_required", action)
        category = action["failure_category"]
        if category not in {"live_gui_broken", "live_gui_unknown"}:
            raise ContractError(
                f"Automatic same-run recovery is not supported for owner-action category {category}"
            )
        snapshot = latest_snapshot(self.layout)
        if snapshot is None:
            raise CapabilityError("Owner-action recovery requires a fresh capability snapshot")
        if parse_iso(snapshot["captured_at"]) <= parse_iso(action["raised_at"]):
            raise CapabilityError("Owner-action recovery requires a capability snapshot newer than the failure")
        gui = snapshot["capabilities"].get("live_blender_gui_review", {})
        if (
            gui.get("status") not in {"AVAILABLE", "UNAVAILABLE"}
            or not gui.get("observed_at")
            or gui.get("details", {}).get("source") != "explicit"
        ):
            raise CapabilityError("Live GUI must be explicitly reprobed to AVAILABLE or UNAVAILABLE")
        if parse_iso(gui["observed_at"]) < parse_iso(snapshot["captured_at"]):
            raise CapabilityError("Live GUI recovery observation is stale within the capability snapshot")
        target = RunState(action["last_healthy_state"])
        if target not in {RunState.LIVE_GUI_DECISION, RunState.AWAITING_LIVE_GUI_REVIEW}:
            raise ContractError(f"Recorded live-GUI recovery target is not supported: {target.value}")
        transition(run_dir, run, RunState.RESUMABLE, reason="owner-action condition was reprobed and resolved")
        run["metadata"].pop("owner_action_path", None)
        run["metadata"]["last_owner_action_recovery"] = {
            "category": category,
            "recovered_to": target.value,
            "capability_status": gui["status"],
            "observed_at": gui["observed_at"],
        }
        save_run(run_dir, run)
        transition(
            run_dir,
            run,
            target,
            reason="resolved owner-action condition restored same-run authority",
            resume_target=target,
        )
        if target == RunState.LIVE_GUI_DECISION:
            self._resolve_gui_requirement(run_dir, run)
        return run

    def _materialize_active_candidate(
        self,
        run_dir: Path,
        run: dict[str, Any],
        *,
        candidate: Path,
        dependencies: list[Path],
        iteration: int,
        variant_index: int,
    ) -> dict[str, Any]:
        plan_id, selection_round, selection_sha = self._current_method_selection_identity(run_dir, run)
        manifest_path, manifest = materialize_candidate_closure(
            run_dir,
            run_id=run["run_id"],
            iteration=iteration,
            variant_index=variant_index,
            method_plan_id=plan_id,
            method_selection_round=selection_round,
            method_selection_sha256=selection_sha,
            candidate=candidate,
            dependencies=dependencies,
        )
        run["active_candidate_id"] = manifest["candidate_id"]
        run["metadata"]["candidate_manifest_path"] = manifest_path.relative_to(run_dir).as_posix()
        return manifest

    def _seed_replacement(self, run_dir: Path, run: dict[str, Any], manifest_path: Path):
        old = verify_candidate_manifest(manifest_path)
        closure_root = Path(manifest_path).parent / "closure"
        candidate_record = next(item for item in old["files"] if item["role"] == "candidate")
        candidate = closure_root / candidate_record["pinned_path"]
        dependencies = [closure_root / item["pinned_path"] for item in old["files"] if item["role"] == "dependency"]
        run["iteration"] += 1
        plan_id, selection_round, selection_sha = self._current_method_selection_identity(run_dir, run)
        return materialize_candidate_closure(
            run_dir,
            run_id=run["run_id"],
            iteration=run["iteration"],
            variant_index=1,
            method_plan_id=plan_id,
            method_selection_round=selection_round,
            method_selection_sha256=selection_sha,
            candidate=candidate,
            dependencies=dependencies,
        )

    def _replace_active_checkpoint(
        self,
        run: dict[str, Any],
        checkpoint: dict[str, Any],
        new_record: dict[str, Any],
    ) -> None:
        old_record_id = run["metadata"].get("active_checkpoint_retention_id")
        run["active_checkpoint_id"] = checkpoint["checkpoint_id"]
        run["metadata"]["active_checkpoint_retention_id"] = new_record["record_id"]
        run["metadata"]["active_checkpoint_path"] = f"checkpoints/{checkpoint['checkpoint_id']}/checkpoint.json"
        if old_record_id:
            self.retention.transition(
                old_record_id,
                "EPHEMERAL",
                ttl_hours=self.config["storage"]["ephemeral_ttl_hours"],
                replaced_by=checkpoint["checkpoint_id"],
            )

    def _resolve_gui_requirement(self, run_dir: Path, run: dict[str, Any]) -> None:
        status = self._gui_capability_status()
        if status == "AVAILABLE":
            transition(run_dir, run, RunState.AWAITING_LIVE_GUI_REVIEW, reason="live GUI capability is available")
        elif status == "UNAVAILABLE":
            run["assurance_level"] = "render_verified"
            save_run(run_dir, run)
            transition(run_dir, run, RunState.FINAL_AI_VALIDATION, reason="live GUI explicitly unavailable")
        else:
            self._owner_action(
                run_dir,
                run,
                category=f"live_gui_{status.lower()}",
                failed_operation="live_gui_decision",
                retryable=status == "BROKEN",
                attempts=1,
                retries=0,
                requested="Reprobe live GUI capability; do not downgrade BROKEN/UNKNOWN to UNAVAILABLE.",
            )

    def _gui_capability_status(self) -> str:
        snapshot = latest_snapshot(self.layout)
        if snapshot is None:
            return "UNKNOWN"
        return snapshot["capabilities"].get("live_blender_gui_review", {}).get("status", "UNKNOWN")

    def _manifest_path(self, run_dir: Path, run: dict[str, Any]) -> Path:
        relative = run["metadata"].get("candidate_manifest_path")
        candidate_id = run.get("active_candidate_id")
        if not relative or not candidate_id:
            raise IntegrityError("Run has no active candidate manifest")
        actual = ensure_within(run_dir, run_dir / relative)
        expected = ensure_within(
            run_dir / "candidates",
            run_dir / "candidates" / candidate_id / "candidate.manifest.json",
        )
        if actual != expected:
            raise IntegrityError("Run candidate manifest path does not match the active candidate id")
        return actual

    def _evidence_path(self, run_dir: Path, run: dict[str, Any]) -> Path:
        relative = run["metadata"].get("evidence_bundle_path")
        if not relative:
            raise IntegrityError("Run has no evidence bundle")
        return ensure_within(run_dir, run_dir / relative)

    def _metadata_path(self, run_dir: Path, run: dict[str, Any], key: str) -> Path:
        relative = run["metadata"].get(key)
        if not relative:
            raise IntegrityError(f"Run has no {key}")
        return ensure_within(run_dir, run_dir / relative)

    def _read_metadata_json(self, run_dir: Path, run: dict[str, Any], key: str) -> dict[str, Any]:
        path = self._metadata_path(run_dir, run, key)
        return json.loads(path.read_text(encoding="utf-8"))

    def _checkpoint_method_paths(
        self,
        run_dir: Path,
        run: dict[str, Any],
    ) -> tuple[Path | None, Path | None]:
        plan_path = (
            self._method_plan_file_path(run_dir, run)
            if run["metadata"].get("method_plan_path")
            else None
        )
        selection_path = (
            self._method_selection_file_path(run_dir, run)
            if run["metadata"].get("method_selection_path")
            else None
        )
        if selection_path is not None and plan_path is None:
            raise IntegrityError("Active method selection has no authoritative method plan")
        return plan_path, selection_path

    def _method_plan_file_path(self, run_dir: Path, run: dict[str, Any]) -> Path:
        actual = self._metadata_path(run_dir, run, "method_plan_path")
        revision = int(run["metadata"].get("method_plan_revision", 0))
        expected = ensure_within(
            run_dir,
            run_dir / "methods" / f"method-plan-r{revision}.json",
        )
        if actual != expected:
            raise IntegrityError("Run method-plan path does not match the active plan revision")
        return actual

    def _method_selection_file_path(self, run_dir: Path, run: dict[str, Any]) -> Path:
        actual = self._metadata_path(run_dir, run, "method_selection_path")
        round_id = int(run["metadata"].get("method_selection_round", 0))
        expected = ensure_within(
            run_dir,
            run_dir / "methods" / f"method-selection-r{round_id}.json",
        )
        if actual != expected:
            raise IntegrityError("Run method-selection path does not match the active selection round")
        return actual

    def _validate_current_method_selection(
        self,
        run_dir: Path,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        plan_path = self._method_plan_file_path(run_dir, run)
        plan_sha = sha256_file(plan_path)
        recorded_plan_sha = run["metadata"].get("method_plan_sha256")
        if not recorded_plan_sha or plan_sha != recorded_plan_sha:
            raise IntegrityError("Validated method plan bytes changed outside the authorized lifecycle")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))

        selection_path = self._method_selection_file_path(run_dir, run)
        selection_sha = sha256_file(selection_path)
        recorded_selection_sha = run["metadata"].get("method_selection_sha256")
        if not recorded_selection_sha or selection_sha != recorded_selection_sha:
            raise IntegrityError("Validated method selection bytes changed outside the authorized lifecycle")
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        cache_identity = method_cache_fingerprint(self.layout, self.config)
        expected_cache_fingerprint = (
            cache_identity.get("fingerprint")
            if cache_identity.get("status") == "AVAILABLE"
            else None
        )
        return validate_method_selection(
            selection,
            run=run,
            plan=plan,
            project_config=self.config,
            expected_plan_sha256=plan_sha,
            expected_cache_fingerprint=expected_cache_fingerprint,
        )

    def _current_method_selection_identity(
        self,
        run_dir: Path,
        run: dict[str, Any],
    ) -> tuple[str, int, str]:
        selection = self._validate_current_method_selection(run_dir, run)
        path = self._method_selection_file_path(run_dir, run)
        return selection["plan_id"], selection["selection_round"], sha256_file(path)

    def _verify_candidate_method_binding(
        self,
        run_dir: Path,
        run: dict[str, Any],
        manifest: dict[str, Any],
    ) -> None:
        plan_id, selection_round, selection_sha = self._current_method_selection_identity(run_dir, run)
        if manifest["method_plan_id"] != plan_id:
            raise IntegrityError("Candidate method plan does not match the active method plan")
        if manifest["method_selection_round"] != selection_round:
            raise IntegrityError("Candidate method-selection round does not match the active selection")
        if manifest["method_selection_sha256"] != selection_sha:
            raise IntegrityError("Candidate is not bound to the current method-selection contract")

    def _downstream_work_units(
        self,
        plan: dict[str, Any],
        changed_work_units: Iterable[str],
    ) -> list[str]:
        reverse: dict[str, set[str]] = {}
        for unit in plan["work_units"]:
            for dependency in unit["depends_on"]:
                reverse.setdefault(dependency, set()).add(unit["work_unit_id"])
        stale = set(changed_work_units)
        queue = list(changed_work_units)
        while queue:
            current = queue.pop(0)
            for dependent in sorted(reverse.get(current, set())):
                if dependent not in stale:
                    stale.add(dependent)
                    queue.append(dependent)
        return sorted(stale)

    def _source_review_for_change_impact(
        self,
        run_dir: Path,
        run: dict[str, Any],
        source: str | None,
    ) -> dict[str, Any] | None:
        if source == "VISUAL_REVIEW":
            return self._read_metadata_json(run_dir, run, "visual_review_path")
        if source == "LIVE_GUI_REVIEW":
            return self._read_metadata_json(run_dir, run, "live_gui_review_path")
        if source == "OWNER_REVISION":
            return None
        raise ContractError(f"Unknown change-impact source: {source}")

    def _prepare_method_reconsideration(
        self,
        run_dir: Path,
        run: dict[str, Any],
        *,
        reason: str = "review identified a method-selection mismatch",
    ) -> None:
        transition(
            run_dir,
            run,
            RunState.METHOD_RECONSIDERATION,
            reason=reason,
        )
        run["iteration"] += 1
        run["metadata"]["method_selection_round"] = int(
            run["metadata"].get("method_selection_round", 0)
        ) + 1
        run["metadata"]["local_repair_streak"] = 0
        run["active_candidate_id"] = None
        run["assurance_level"] = None
        for key in (
            "method_selection_path",
            "method_selection_sha256",
            "candidate_manifest_path",
            "evidence_bundle_path",
            "visual_review_path",
            "fix_plan_path",
            "live_gui_review_path",
            "change_impact_path",
            "global_reassessment_path",
        ):
            run["metadata"].pop(key, None)
        save_run(run_dir, run)
        transition(
            run_dir,
            run,
            RunState.AWAITING_METHOD_SELECTION,
            reason="new specialized-method selection required before another candidate",
        )

    def _prepare_plan_revision(self, run_dir: Path, run: dict[str, Any], *, reason: str) -> None:
        current_plan_path = self._method_plan_file_path(run_dir, run)
        current_plan_sha = sha256_file(current_plan_path)
        if current_plan_sha != run["metadata"].get("method_plan_sha256"):
            raise IntegrityError("Cannot revise a method plan whose authoritative bytes changed")

        run["iteration"] += 1
        run["metadata"]["previous_method_plan_sha256"] = current_plan_sha
        run["metadata"]["method_plan_revision"] = int(
            run["metadata"].get("method_plan_revision", 0)
        ) + 1
        run["metadata"]["method_selection_round"] = int(
            run["metadata"].get("method_selection_round", 0)
        ) + 1
        run["metadata"]["pending_plan_revision_reason"] = reason
        run["metadata"]["local_repair_streak"] = 0
        run["active_candidate_id"] = None
        run["assurance_level"] = None
        for key in (
            "method_plan_path",
            "method_plan_id",
            "method_plan_sha256",
            "method_selection_path",
            "method_selection_sha256",
            "candidate_manifest_path",
            "evidence_bundle_path",
            "visual_review_path",
            "fix_plan_path",
            "live_gui_review_path",
            "change_impact_path",
            "global_reassessment_path",
        ):
            run["metadata"].pop(key, None)
        save_run(run_dir, run)
        transition(
            run_dir,
            run,
            RunState.AWAITING_METHOD_PLAN,
            reason="upstream production structure or contract must be revised before more work",
        )

    def _owner_action(
        self,
        run_dir: Path,
        run: dict[str, Any],
        *,
        category: str,
        failed_operation: str,
        retryable: bool,
        attempts: int,
        retries: int,
        requested: str,
    ) -> None:
        payload = {
            "schema_version": 1,
            "run_id": run["run_id"],
            "raised_at": iso_now(),
            "failure_category": category,
            "retryable": retryable,
            "failed_operation": failed_operation,
            "attempts": attempts,
            "retries": retries,
            "last_healthy_state": run["state"],
            "checkpoint": run.get("active_checkpoint_id"),
            "evidence": [],
            "requested_owner_action": requested,
            "resume_hint": (
                "Resolve the stated condition, reprobe, then resume from the active checkpoint when present."
            ),
            "final_safety_status": (
                "No new human acceptance or publication is permitted while this owner action is unresolved."
            ),
        }
        validate_contract("owner_action_required", payload)
        path = run_dir / "owner_action_required.json"
        atomic_write_json(path, payload)
        run["metadata"]["owner_action_path"] = path.relative_to(run_dir).as_posix()
        save_run(run_dir, run)
        transition(run_dir, run, RunState.OWNER_ACTION_REQUIRED, reason=category)
