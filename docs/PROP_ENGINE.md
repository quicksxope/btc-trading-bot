# Prop firm engines

## `pct` (default)

Generic packs (`generic`, `ftmo_like`) use peak drawdown % and worst daily loss % on the equity curve.

## `usd` (Phase B)

Templates under `configs/prop_firms/` with `engine: usd`:

| Pack | Daily | Max loss | Target | Extra |
|------|-------|----------|--------|--------|
| `holaprime_1step_*` | USD cap | Static floor | USD | Min days |
| `holaprime_direct_*` | USD cap | Trailing EOD | — | Hola 20% consistency |
| `topstep_50k_combine` | USD cap | Trailing EOD (lock at start) | USD | Best day ≤ 50% of target |

During the bar loop, new entries stop after a daily or max-loss breach. Final pass/fail uses the same USD rules plus consistency where configured.

## `sltp_risk` execution (Phase C)

Prop templates may set `execution_defaults`:

- Swing high/low stop (`swing_lookback`)
- Take profit at `risk_reward_ratio ×` stop distance
- Position size from `risk_per_trade_usd`, capped at **max prop max-loss / 10** (e.g. $3k MLL → $300/trade max), then by equity fraction & remaining daily loss budget
- Optional `max_trades_per_day`
- Exits on SL/TP intrabar (SL first if both hit)

**Still simplified vs Hola folder:** session/news/weekend guards, daily profit cap, consecutive-loss pause, leverage margin model.
