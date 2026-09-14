# Telegram wizard (v1.5)

Full **New backtest** wizard — no Quick playbook on Home.

## Steps

1. Asset class → Instrument (shows Supabase coverage when configured)
2. Date range (6mo / 1y / max available / custom)
3. Session + toggles
4. Primary TF (15m, **30m**, 1h, …) + context (1h / 4h / 1d)
5. Strategy: **Preset** (Cipher_B, EMA, RSI) or **Custom** indicators
6. Prop: **None**, **Generic** (% sliders), **FTMO-like** only
7. Balance → Review → Run or Save as preset

## 30m data

Coinbase has no native 30m candles. The engine loads **15m** from Supabase/CSV and **resamples to 30m** for the backtest.

## Hola Prime packs (advanced — not in wizard)

`holaprime_10k` and `holaprime_1step_10k` live under `configs/prop_firms/` but are **not** on the Prop keyboard until Phase B (USD caps, consistency, SL/TP parity).

**Use today:**

1. Copy an example such as [`configs/examples/cipher_b_holaprime_1step_30m.yaml`](../configs/examples/cipher_b_holaprime_1step_30m.yaml)
2. Run locally with CLI, or edit and **Save as preset** after a wizard run (paste fields manually into a saved preset workflow), or queue via preset name once stored in SQLite
3. Admin: `/admin` lists prop packs and notes Hola = preset-only

Prop evaluation for Hola YAML uses **approximate % rules** from the pack file, not full Hola Prime folder simulation.

## Cipher B

Preset **cipher_b** = WaveTrend cross + RSI + Bressert (see `engine/strategy.py`). Recommended primary **30m**.

## Phase B (later)

Hola packs return to wizard Prop menu when engine supports USD intraday rules, consistency reporting, and optional SL/TP execution.
