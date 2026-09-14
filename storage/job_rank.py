"""Rank backtest jobs: prop PASS first, then net PnL."""

from __future__ import annotations

import json
from typing import Any

import yaml

from engine.models import BacktestResult


def result_from_job(job: dict) -> BacktestResult | None:
    raw = job.get("result_json")
    if not raw:
        return None
    try:
        return BacktestResult.model_validate(json.loads(raw))
    except Exception:
        return None


def prop_enabled_in_job(job: dict) -> bool:
    cfg_yaml = job.get("config_yaml")
    if not cfg_yaml:
        return False
    try:
        cfg = yaml.safe_load(cfg_yaml) or {}
        prop = cfg.get("prop_firm") or {}
        return bool(prop.get("enabled", True))
    except Exception:
        return False


def job_sort_key(job: dict) -> tuple:
    """Lower sorts first: PASS before FAIL, then higher PnL."""
    result = result_from_job(job)
    if result is None:
        return (2, 0.0, job.get("finished_at") or "")
    prop_on = prop_enabled_in_job(job)
    tier = 0 if (not prop_on or result.prop_pass) else 1
    if not prop_on:
        tier = 0
    return (tier, -result.net_pnl_pct, job.get("finished_at") or "")


def sort_jobs_by_score(jobs: list[dict]) -> list[dict]:
    return sorted(jobs, key=job_sort_key)


def job_result_badge(job: dict) -> str:
    result = result_from_job(job)
    if result is None:
        return "?"
    if not prop_enabled_in_job(job):
        return f"PnL {result.net_pnl_pct:+.1f}%"
    if result.prop_pass:
        return f"PASS {result.net_pnl_pct:+.1f}%"
    reason = (result.prop_fail_reason or "fail")[:28]
    return f"FAIL {result.net_pnl_pct:+.1f}% ({reason})"


def job_config_hint(job: dict) -> str:
    cfg_yaml = job.get("config_yaml")
    if not cfg_yaml:
        return job.get("id", "")
    try:
        cfg = yaml.safe_load(cfg_yaml) or {}
        parts = []
        inst = (cfg.get("instrument") or "")[:12]
        if inst:
            parts.append(inst)
        tf = (cfg.get("timeframes") or {}).get("primary")
        if tf:
            parts.append(tf)
        prop = cfg.get("prop_firm") or {}
        if prop.get("enabled"):
            parts.append(prop.get("pack_id", "prop"))
        strat = cfg.get("strategy") or {}
        if strat.get("mode") == "preset" and strat.get("preset"):
            parts.append(strat["preset"])
        elif strat.get("mode") == "custom":
            n = len(strat.get("custom_indicators") or [])
            parts.append(f"custom×{n}")
        return " · ".join(parts) if parts else job.get("id", "")
    except Exception:
        return job.get("id", "")


def job_button_label(job: dict) -> str:
    result = result_from_job(job)
    jid = job.get("id", "?")
    if result is None:
        return jid
    prop_on = prop_enabled_in_job(job)
    if not prop_on:
        icon = "📊"
    elif result.prop_pass:
        icon = "✅"
    else:
        icon = "❌"
    return f"{icon} {jid} {result.net_pnl_pct:+.1f}%"


def rank_among_jobs(job: dict, pool: list[dict]) -> int | None:
    """1-based rank among pool after prop-score sort."""
    ranked = sort_jobs_by_score(pool)
    for i, j in enumerate(ranked, 1):
        if j.get("id") == job.get("id"):
            return i
    return None


def leaderboard_text(jobs: list[dict], *, limit: int = 10) -> str:
    ranked = sort_jobs_by_score(jobs)[:limit]
    if not ranked:
        return "<b>Leaderboard</b>\n<i>No completed runs.</i>"
    lines = [
        "<b>Leaderboard</b>",
        "<i>PASS prop first, then highest net PnL. Tap a job for detail.</i>",
        "",
    ]
    for i, job in enumerate(ranked, 1):
        jid = job.get("id", "?")
        badge = job_result_badge(job)
        hint = job_config_hint(job)
        icon = "✅" if "PASS" in badge or badge.startswith("PnL") else "❌"
        if badge.startswith("FAIL"):
            icon = "❌"
        elif badge.startswith("PASS"):
            icon = "✅"
        else:
            icon = "·"
        lines.append(f"{i}. {icon} <code>{jid}</code> — {badge}")
        lines.append(f"   <i>{hint}</i>")
    return "\n".join(lines)
