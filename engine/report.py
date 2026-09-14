"""Write job artifacts and equity chart."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from engine.models import BacktestConfig, BacktestResult


def write_artifacts(
    out_dir: Path,
    config: BacktestConfig,
    result: BacktestResult,
    equity: pd.DataFrame,
    trades: pd.DataFrame,
    daily: pd.DataFrame,
    breach_log: list[str],
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "config": out_dir / "config.yaml",
        "equity": out_dir / "equity.csv",
        "trades": out_dir / "trades.csv",
        "daily": out_dir / "daily.csv",
        "chart": out_dir / "equity.png",
        "breach_log": out_dir / "breach_log.txt",
    }
    paths["config"].write_text(yaml.safe_dump(config.to_yaml_dict(), sort_keys=False))
    equity.to_csv(paths["equity"], index=False)
    trades.to_csv(paths["trades"], index=False)
    daily.to_csv(paths["daily"], index=False)
    paths["breach_log"].write_text("\n".join(breach_log) or "No breaches logged.")

    if not equity.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(equity["timestamp"], equity["equity"], label="Equity")
        if config.prop_firm.enabled:
            initial = config.execution.initial_balance
            daily_limit = initial * (1 - config.prop_firm.daily_loss_pct / 100)
            ax.axhline(daily_limit, color="r", linestyle="--", alpha=0.5, label="Daily loss ref")
        ax.legend()
        ax.set_title(f"{config.instrument.value} backtest")
        fig.tight_layout()
        fig.savefig(paths["chart"], dpi=120)
        plt.close(fig)

    return paths
