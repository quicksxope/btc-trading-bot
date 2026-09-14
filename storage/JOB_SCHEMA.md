# Job and artifact schema

## Database tables

See `storage/schema.sql`:

- `users` — Telegram users
- `presets` — saved YAML configs per user
- `jobs` — status, progress, config, result JSON, chat binding
- `job_artifacts` — file paths per job
- `job_queue` — FIFO queue (`seq` ordering)

## Job folder layout

```
jobs/{job_id}/
  config.yaml      # reproducible config
  equity.csv       # timestamp, equity, drawdown_pct
  trades.csv       # exit_time, pnl, side
  daily.csv        # day, pnl_pct
  equity.png       # chart with optional daily loss reference
  breach_log.txt   # prop breach lines
```

## Job statuses

`queued` → `running` → `done` | `failed` | `cancelled`

## Telegram templates

Defined in `storage/templates.py`:

- `home_status`, `job_card`, `progress_message`, `result_summary`, `compare_block`
