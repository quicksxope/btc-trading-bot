# Telegram wizard

Full **New backtest** wizard (no Quick playbook on Home).

## Steps

1. Asset class → Instrument (from `configs/instruments/*.yaml` catalog)
2. Date range
3. Session + toggles
4. Primary TF (15m, 30m, 1h, 4h, 1m, 5m) + context (1h / 4h / 1d)
5. Strategy — **Preset** (Cipher_B, EMA, RSI) or **Custom (guided)**
6. Prop — None / Generic / **Custom %** / **From template** / FTMO-like
7. Balance → Review → Run or Save as preset

## Custom strategy (guided)

- Add indicators from `configs/indicators.yaml` (RSI, EMA, ATR, MACD, WaveTrend, Bressert) on primary or context TF.
- **Rule templates** from `configs/rule_templates.yaml` apply DSL `long_when` / `short_when`.
- Advanced: send DSL text for long/short (see `engine/rules.py`).

Refs examples: `primary_RSI_value`, `primary_close`, `cross_above(primary_WAVETREND_wt, primary_WAVETREND_signal)`.

## Custom prop (%)

- **Hola 1-Step $50K** / **TopStep $50K** shortcuts, or **More templates…** for all packs in `configs/prop_firms/`.
- **Last results** / `/last`: leaderboard — **prop PASS first**, then net PnL; tap a job for detail.
- Templates with `engine: usd` run **Phase B** (daily/max loss in USD, Hola consistency, TopStep 50% best-day vs target). Signal backtest is still flip-at-close — not per-trade SL/TP sizing.
- Hola packs appear in templates (~% rules); full USD/consistency in a later engine phase.

## 30m data

Resampled from 15m in Supabase/CSV (Coinbase has no native 30m).

## Presets

**My presets** stores full `BacktestConfig` YAML. Examples: `configs/examples/cipher_b_holaprime_1step_30m.yaml`.

## Back

**« Back** uses a step stack (partial); **Cancel** returns home.
