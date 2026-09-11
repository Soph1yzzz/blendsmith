from __future__ import annotations

import pytest

from blendsmith.contracts import validate_contract
from blendsmith.errors import ContractError, StateTransitionError
from blendsmith.state_machine import RunState, validate_transition

SHA = "a" * 64


def test_owner_accept_requires_sha() -> None:
    payload = {
        "schema_version": 1,
        "run_id": "run-1",
        "decision": "ACCEPT",
        "decided_at": "2026-09-06T00:00:00Z",
        "reason": None,
        "candidate_sha256": None,
    }
    with pytest.raises(ContractError):
        validate_contract("owner_decision", payload)


def test_gui_pass_requires_concrete_checks() -> None:
    payload = {
        "schema_version": 1,
        "run_id": "run-1",
        "candidate_id": "candidate-1",
        "candidate_sha256": SHA,
        "status": "PASS",
        "capability_status": "AVAILABLE",
        "blend_path_verified": False,
        "dirty_state_checked": True,
        "viewport_interaction_performed": True,
        "exploration_actions": ["ORBIT", "ZOOM", "UNSEEN_ANGLE"],
        "coverage": ["OVERALL_FORM", "THICKNESS_DEPTH", "HIDDEN_SURFACES"],
        "views_observed": ["front", "rear oblique", "underside"],
        "observations": ["Observed full form.", "Observed hidden surfaces."],
        "issues": [],
    }
    with pytest.raises(ContractError):
        validate_contract("live_gui_review", payload)


def test_visual_accept_rejects_high_issue() -> None:
    payload = {
        "schema_version": 1,
        "run_id": "run-1",
        "candidate_id": "candidate-1",
        "candidate_sha256": SHA,
        "verdict": "ACCEPT",
        "opened_evidence": ["front"],
        "perspectives_completed": [],
        "issues": [
            {
                "issue_id": "i1",
                "severity": "high",
                "category": "geometry",
                "view_keys": ["front"],
                "observation": "bad",
                "likely_cause": "cause",
                "recommended_strategy": "fix",
                "regression_risk": "low",
                "acceptance_test": "resolved",
            }
        ],
        "regressions": [],
        "uncertainties": [],
        "next_action": "accept",
    }
    with pytest.raises(ContractError):
        validate_contract("visual_review", payload)


def test_fix_plan_is_bounded_to_two_primary_issues() -> None:
    payload = {
        "schema_version": 1,
        "run_id": "run-1",
        "candidate_id": "candidate-1",
        "candidate_sha256": SHA,
        "primary_issue_ids": ["1", "2", "3"],
        "method_ids_to_preserve": ["modifier.mirror"],
        "steps": ["fix"],
        "expected_acceptance_tests": ["pass"],
    }
    with pytest.raises(ContractError):
        validate_contract("fix_plan", payload)


def test_visual_revise_requires_at_least_one_issue() -> None:
    payload = {
        "schema_version": 1,
        "run_id": "run-1",
        "candidate_id": "candidate-1",
        "candidate_sha256": SHA,
        "verdict": "REVISE",
        "opened_evidence": ["front"],
        "perspectives_completed": [],
        "issues": [],
        "regressions": [],
        "uncertainties": [],
        "next_action": "revise",
    }
    with pytest.raises(ContractError):
        validate_contract("visual_review", payload)


def test_global_reassessment_requires_whole_production_context() -> None:
    payload = {
        "schema_version": 1,
        "run_id": "run-1",
        "candidate_id": "candidate-1",
        "candidate_sha256": SHA,
        "decision": "CONTINUE_LOCAL",
        "revisit_domain_knowledge": False,
        "reviewed_context": ["METHOD_PLAN", "METHOD_SELECTION", "CANDIDATE", "OPEN_ISSUES"],
        "rationale": "Local repair still appears viable.",
        "affected_work_units": ["shape"],
    }
    with pytest.raises(ContractError, match="whole production context"):
        validate_contract("global_reassessment", payload)



def test_invalid_state_transition_is_rejected() -> None:
    with pytest.raises(StateTransitionError):
        validate_transition(RunState.CREATED, RunState.PUBLISHED)


def test_schema_date_time_format_is_enforced() -> None:
    payload = {
        "schema_version": 1,
        "run_id": "run-1",
        "decision": "REJECT_RUN",
        "decided_at": "not-a-date",
        "reason": "stop",
        "candidate_sha256": SHA,
    }
    with pytest.raises(ContractError):
        validate_contract("owner_decision", payload)
