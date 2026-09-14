"""Job leaderboard ranking."""

from storage.job_rank import job_sort_key, sort_jobs_by_score


def _job(jid: str, prop_pass: bool, pnl: float, *, prop_enabled: bool = True) -> dict:
    prop = {"enabled": prop_enabled, "pack_id": "generic"}
    return {
        "id": jid,
        "finished_at": jid,
        "result_json": (
            f'{{"net_pnl_pct": {pnl}, "max_drawdown_pct": 1, "win_rate": 50, '
            f'"trade_count": 1, "profit_factor": 1, "prop_pass": {str(prop_pass).lower()}, '
            f'"equity_final": 100000}}'
        ),
        "config_yaml": f"prop_firm:\n  enabled: {str(prop_enabled).lower()}\ninstrument: BTC_PERP\n",
    }


def test_pass_ranks_above_fail():
    jobs = [
        _job("a", False, 50.0),
        _job("b", True, 5.0),
        _job("c", False, 80.0),
    ]
    ranked = sort_jobs_by_score(jobs)
    assert ranked[0]["id"] == "b"
    assert ranked[1]["id"] in ("a", "c")
    assert ranked[-1]["id"] in ("a", "c")
    assert ranked[1]["id"] != ranked[0]["id"]


def test_pass_tiebreak_pnl():
    jobs = [_job("low", True, 3.0), _job("high", True, 20.0)]
    ranked = sort_jobs_by_score(jobs)
    assert ranked[0]["id"] == "high"
