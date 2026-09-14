# Repository layout

## Top level

| Path | Role |
|------|------|
| `engine/` | Backtest core, indicators, presets, prop rules, data I/O |
| `bot/` | Telegram wizard, keyboards, handlers |
| `worker/` | SQLite job queue consumer |
| `storage/` | SQLite schema, job ranking, message templates |
| `configs/` | YAML catalogs (instruments, indicators, prop firms, examples) |
| `tests/` | Pytest suite |
| `scripts/` | Deploy, data fetch, sample data |
| `docs/` | Operator and architecture notes |
| `jobs/` | Runtime job artifacts (gitignored) |
| `data/` | Local OHLCV CSV / app DB (gitignored) |

## `engine/`

| Module | Purpose |
|--------|---------|
| `backtest.py` | Bar simulation, prop hook, study-friendly loaders |
| `study.py` | Indicator study (1–3 pool, subset sweep) |
| `strategy.py` | `build_signals` — preset vs custom DSL |
| `rules.py` | Safe entry-rule DSL v2 |
| `catalog.py` | Indicator + instrument catalogs from YAML |
| `models.py` | Pydantic configs shared by CLI, bot, worker |
| `indicators/` | Registry + WaveTrend, Bressert, Fib/sweep |
| `presets/` | Cipher B, EMA cross, RSI mean revert |
| `prop/` | Prop firm packs + USD engine |
| `prop_firm.py`, `prop_usd.py` | Shims → `engine.prop` |
| `execution_sltp.py` | SL/TP risk sizing |
| `data_*.py`, `warehouse.py`, `coinbase.py` | OHLCV pipeline |

## `bot/`

| Path | Purpose |
|------|---------|
| `main.py` | Bot entry |
| `handlers/` | Home, wizard, study, jobs, presets, admin, strategy builder |
| `keyboards/` | Inline keyboards (wizard, study, leaderboard) |
| `fsm/` | `validation.py` (draft → config), legacy step enum |
| `states.py` | Re-export Aiogram `WizardStates` |

## `configs/`

- `instruments/` — per-symbol profile
- `prop_firms/` — challenge templates
- `indicators.yaml`, `rule_templates.yaml` — custom builder + study sweep
- `examples/` — ready-made YAML (Cipher B + Hola, etc.)

## Job types

- **Backtest** — single strategy in `jobs.result_json` (`BacktestResult`)
- **Indicator study** — `meta.job_kind = indicator_study`; result payload with ranked mixes
