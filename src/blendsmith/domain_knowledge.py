from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from .contracts import validate_contract
from .errors import ContractError, IntegrityError
from .paths import atomic_write_json, ensure_within
from .project import ProjectLayout
from .timeutil import iso_now, parse_iso, utc_now

DOMAIN_RISK_SIGNALS = {
    "REAL_WORLD_FUNCTION",
    "DIMENSIONAL_CONSTRAINT",
    "STRUCTURAL_RELATIONSHIP",
    "CONSTRUCTION_OR_MANUFACTURING_PROCESS",
    "SAFETY_OR_CLEARANCE",
    "REGULATION_OR_STANDARD",
    "SPECIALIST_PRACTICE",
}
CONFIDENCE_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _payload_digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def research_scope_fingerprint(research: dict[str, Any]) -> str:
    scope = {
        "domain": research["domain"],
        "topics": sorted(
            (
                {
                    "topic_key": item["topic_key"],
                    "question": item["question"],
                    "purpose": item["purpose"],
                    "volatility": item["volatility"],
                }
                for item in research.get("topics", [])
            ),
            key=lambda item: item["topic_key"],
        ),
    }
    return _payload_digest(scope)


def validate_domain_research(payload: dict[str, Any], *, run: dict[str, Any]) -> dict[str, Any]:
    validate_contract("domain_research", payload)
    if payload["run_id"] != run["run_id"]:
        raise ContractError("Domain research run_id does not match active run")

    expected_revision = int(run["metadata"].get("domain_research_revision", 0))
    if payload["revision"] != expected_revision:
        raise ContractError(
            f"Domain research revision is stale: expected {expected_revision}, got {payload['revision']}"
        )
    if expected_revision > 0:
        expected_supersedes = run["metadata"].get("previous_domain_research_sha256")
        if not expected_supersedes:
            raise ContractError("Revised domain research has no authoritative predecessor SHA")
        if payload.get("supersedes_sha256") != expected_supersedes:
            raise ContractError("Revised domain research must supersede the exact previous research SHA")

    checks = payload["risk_checks"]
    check_signals = [item["signal"] for item in checks]
    if len(check_signals) != len(set(check_signals)):
        raise ContractError("Domain research risk checks must be unique")
    if set(check_signals) != DOMAIN_RISK_SIGNALS:
        missing = sorted(DOMAIN_RISK_SIGNALS - set(check_signals))
        extra = sorted(set(check_signals) - DOMAIN_RISK_SIGNALS)
        raise ContractError(
            f"Domain research must account for every risk family; missing={missing}, extra={extra}"
        )
    applicable = {item["signal"] for item in checks if item["status"] == "APPLICABLE"}
    if set(payload["risk_signals"]) != applicable:
        raise ContractError("Domain research risk_signals must exactly match APPLICABLE risk checks")
    if payload["decision"] == "RESEARCH_REQUIRED" and not applicable:
        raise ContractError("RESEARCH_REQUIRED needs at least one APPLICABLE domain risk check")
    if payload["decision"] == "NOT_REQUIRED" and applicable:
        raise ContractError("NOT_REQUIRED requires every domain risk check to be NOT_APPLICABLE")

    topic_keys = [item["topic_key"] for item in payload["topics"]]
    if len(topic_keys) != len(set(topic_keys)):
        raise ContractError("Domain research topic_key values must be unique")
    return payload


def validate_domain_knowledge(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    research: dict[str, Any],
    expected_research_sha256: str,
) -> dict[str, Any]:
    validate_contract("domain_knowledge", payload)
    if payload["run_id"] != run["run_id"]:
        raise ContractError("Domain knowledge run_id does not match active run")
    if payload["research_sha256"] != expected_research_sha256:
        raise ContractError("Domain knowledge is not bound to the active research receipt")
    if payload["domain"] != research["domain"]:
        raise ContractError("Domain knowledge domain does not match the research receipt")

    expected_scope = research_scope_fingerprint(research)
    if payload["scope_fingerprint"] != expected_scope:
        raise ContractError("Domain knowledge scope fingerprint does not match the active research scope")

    collected_at = parse_iso(payload["collected_at"])
    future_tolerance = timedelta(minutes=5)
    if collected_at > utc_now() + future_tolerance:
        raise ContractError("Domain knowledge collected_at cannot be materially in the future")

    expected_topics = {item["topic_key"]: item for item in research["topics"]}
    actual_topics = {item["topic_key"]: item for item in payload["topics"]}
    if len(actual_topics) != len(payload["topics"]):
        raise ContractError("Domain knowledge topic_key values must be unique")
    if set(actual_topics) != set(expected_topics):
        raise ContractError("Domain knowledge must cover every research topic exactly once")

    all_source_ids: set[str] = set()
    all_finding_ids: set[str] = set()
    for topic_key, topic in actual_topics.items():
        expected = expected_topics[topic_key]
        if topic["volatility"] != expected["volatility"]:
            raise ContractError(f"Knowledge volatility changed for topic {topic_key}")
        source_ids = [item["source_id"] for item in topic["sources"]]
        if len(source_ids) != len(set(source_ids)):
            raise ContractError(f"Source IDs must be unique inside topic {topic_key}")
        overlap = all_source_ids.intersection(source_ids)
        if overlap:
            raise ContractError(f"Domain knowledge source IDs must be globally unique: {sorted(overlap)}")
        all_source_ids.update(source_ids)

        finding_ids = [item["finding_id"] for item in topic["findings"]]
        if len(finding_ids) != len(set(finding_ids)):
            raise ContractError(f"Finding IDs must be unique inside topic {topic_key}")
        overlap = all_finding_ids.intersection(finding_ids)
        if overlap:
            raise ContractError(f"Domain knowledge finding IDs must be globally unique: {sorted(overlap)}")
        all_finding_ids.update(finding_ids)

        for source in topic["sources"]:
            accessed_at = parse_iso(source["accessed_at"])
            if accessed_at > collected_at + future_tolerance:
                raise ContractError(
                    f"Domain knowledge source {source['source_id']} cannot be accessed after collected_at"
                )

        local_sources = set(source_ids)
        for finding in topic["findings"]:
            unknown = sorted(set(finding["source_ids"]) - local_sources)
            if unknown:
                raise ContractError(
                    f"Finding {finding['finding_id']} cites sources outside topic {topic_key}: {unknown}"
                )
    return payload


def validate_domain_practice(
    payload: dict[str, Any],
    *,
    run: dict[str, Any],
    knowledge: dict[str, Any],
    expected_knowledge_sha256: str,
) -> dict[str, Any]:
    validate_contract("domain_practice", payload)
    if payload["run_id"] != run["run_id"]:
        raise ContractError("Domain practice run_id does not match active run")
    if payload["knowledge_sha256"] != expected_knowledge_sha256:
        raise ContractError("Domain practice is not bound to the active knowledge receipt")
    if payload["domain"] != knowledge["domain"]:
        raise ContractError("Domain practice domain does not match domain knowledge")

    findings: dict[str, dict[str, Any]] = {}
    for topic in knowledge["topics"]:
        for finding in topic["findings"]:
            findings[finding["finding_id"]] = finding

    rule_ids = [item["rule_id"] for item in payload["rules"]]
    if len(rule_ids) != len(set(rule_ids)):
        raise ContractError("Domain practice rule_id values must be unique")

    used_findings: set[str] = set()
    for rule in payload["rules"]:
        unknown = sorted(set(rule["finding_ids"]) - set(findings))
        if unknown:
            raise ContractError(f"Domain practice rule {rule['rule_id']} cites unknown findings: {unknown}")
        cited = [findings[finding_id] for finding_id in rule["finding_ids"]]
        weakest = min(CONFIDENCE_RANK[item["confidence"]] for item in cited)
        if CONFIDENCE_RANK[rule["confidence"]] > weakest:
            raise ContractError(
                f"Domain practice rule {rule['rule_id']} cannot claim higher confidence than its weakest finding"
            )
        used_findings.update(rule["finding_ids"])

    ignored_ids = [item["finding_id"] for item in payload["ignored_findings"]]
    if len(ignored_ids) != len(set(ignored_ids)):
        raise ContractError("Ignored domain finding IDs must be unique")
    unknown_ignored = sorted(set(ignored_ids) - set(findings))
    if unknown_ignored:
        raise ContractError(f"Domain practice ignores unknown findings: {unknown_ignored}")
    both = sorted(used_findings.intersection(ignored_ids))
    if both:
        raise ContractError(f"A domain finding cannot be both used and ignored: {both}")

    actionable = {finding_id for finding_id, finding in findings.items() if finding["actionable"]}
    unaccounted = sorted(actionable - used_findings - set(ignored_ids))
    if unaccounted:
        raise ContractError(
            "Every actionable domain finding must become a practice rule or be explicitly ignored: "
            + ", ".join(unaccounted)
        )
    return payload


def _knowledge_cache_path(layout: ProjectLayout, scope_fingerprint: str) -> Path:
    return ensure_within(layout.knowledge_cache, layout.knowledge_cache / f"{scope_fingerprint}.json")


def _cache_valid_until(
    knowledge: dict[str, Any],
    project_config: dict[str, Any],
) -> str | None:
    volatility = {topic["volatility"] for topic in knowledge["topics"]}
    collected_at = parse_iso(knowledge["collected_at"])
    policy = project_config["domain_knowledge"]
    if "CURRENT" in volatility:
        expires = collected_at + timedelta(days=int(policy["current_ttl_days"]))
    elif "SLOW_CHANGING" in volatility:
        expires = collected_at + timedelta(days=int(policy["slow_changing_ttl_days"]))
    else:
        return None if policy["stable_cache_allowed"] else collected_at.isoformat()
    return expires.isoformat().replace("+00:00", "Z")


def save_domain_knowledge_cache(
    layout: ProjectLayout,
    project_config: dict[str, Any],
    *,
    research: dict[str, Any],
    knowledge: dict[str, Any],
    knowledge_sha256: str,
) -> dict[str, Any] | None:
    policy = project_config["domain_knowledge"]
    if not policy["cache_enabled"] or knowledge["acquisition"] != "FRESH":
        return None
    scope_fingerprint = research_scope_fingerprint(research)
    if knowledge["scope_fingerprint"] != scope_fingerprint:
        raise IntegrityError("Refusing to cache domain knowledge under a mismatched scope")
    record = {
        "schema_version": 1,
        "scope_fingerprint": scope_fingerprint,
        "cached_at": iso_now(),
        "valid_until": _cache_valid_until(knowledge, project_config),
        "original_knowledge_sha256": knowledge_sha256,
        "cache_epoch": int(policy["cache_epoch"]),
        "knowledge_content_sha256": _payload_digest(knowledge),
        "knowledge": knowledge,
    }
    path = _knowledge_cache_path(layout, scope_fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, record)
    return record


def load_domain_knowledge_cache(
    layout: ProjectLayout,
    project_config: dict[str, Any],
    *,
    research: dict[str, Any],
) -> dict[str, Any]:
    scope_fingerprint = research_scope_fingerprint(research)
    if not project_config["domain_knowledge"]["cache_enabled"]:
        return {"status": "DISABLED", "scope_fingerprint": scope_fingerprint}
    path = _knowledge_cache_path(layout, scope_fingerprint)
    if not path.is_file():
        return {"status": "MISS", "scope_fingerprint": scope_fingerprint}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("scope_fingerprint") != scope_fingerprint:
            raise IntegrityError("Domain knowledge cache scope fingerprint changed")
        current_epoch = int(project_config["domain_knowledge"]["cache_epoch"])
        if record.get("cache_epoch") != current_epoch:
            return {
                "status": "STALE",
                "scope_fingerprint": scope_fingerprint,
                "reason": "cache_epoch_changed",
                "cached_epoch": record.get("cache_epoch"),
                "current_epoch": current_epoch,
            }
        knowledge = record["knowledge"]
        validate_contract("domain_knowledge", knowledge)
        if record.get("knowledge_content_sha256") != _payload_digest(knowledge):
            raise IntegrityError("Domain knowledge cache content digest changed")
        valid_until = record.get("valid_until")
        expected_valid_until = _cache_valid_until(knowledge, project_config)
        if valid_until != expected_valid_until:
            raise IntegrityError("Domain knowledge cache validity window changed")
        if valid_until is not None and parse_iso(valid_until) < utc_now():
            return {
                "status": "STALE",
                "scope_fingerprint": scope_fingerprint,
                "cached_at": record.get("cached_at"),
                "valid_until": valid_until,
            }
        return {
            "status": "VALID",
            "scope_fingerprint": scope_fingerprint,
            "cached_at": record.get("cached_at"),
            "valid_until": valid_until,
            "original_knowledge_sha256": record["original_knowledge_sha256"],
            "knowledge": knowledge,
        }
    except (KeyError, json.JSONDecodeError, ContractError, IntegrityError, TypeError, ValueError) as exc:
        return {
            "status": "INVALID",
            "scope_fingerprint": scope_fingerprint,
            "error": str(exc),
        }


def materialize_cached_domain_knowledge(
    cache: dict[str, Any],
    *,
    run_id: str,
    research_sha256: str,
) -> dict[str, Any]:
    if cache.get("status") != "VALID":
        raise ContractError("Only a VALID domain knowledge cache entry can be materialized")
    knowledge = json.loads(json.dumps(cache["knowledge"]))
    knowledge["run_id"] = run_id
    knowledge["research_sha256"] = research_sha256
    knowledge["knowledge_id"] = f"cache-{cache['scope_fingerprint'][:12]}"
    knowledge["acquisition"] = "CACHE"
    knowledge["cache_origin"] = {
        "scope_fingerprint": cache["scope_fingerprint"],
        "original_knowledge_sha256": cache["original_knowledge_sha256"],
        "cached_at": cache["cached_at"],
        "valid_until": cache["valid_until"],
    }
    return knowledge
