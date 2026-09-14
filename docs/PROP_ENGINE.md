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

**Not yet modeled:** fixed `$` risk per trade, SL/TP from swing structure, max trades/day, news/weekend flags (see `backtest-trade-holaprime10k` for full simulator).
