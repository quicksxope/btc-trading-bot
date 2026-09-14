"""Load instrument profiles and data catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

from engine.models import AssetClass, InstrumentId, InstrumentProfile

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENTS_DIR = ROOT / "configs" / "instruments"
CATALOG_PATH = ROOT / "configs" / "data_catalog.yaml"


def load_instrument_profile(instrument: InstrumentId) -> InstrumentProfile:
    path = INSTRUMENTS_DIR / f"{instrument.value.lower()}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    raw = yaml.safe_load(path.read_text())
    return InstrumentProfile(**raw)


def load_data_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {"instruments": {}}
    return yaml.safe_load(CATALOG_PATH.read_text()) or {"instruments": {}}


def catalog_entry(instrument: InstrumentId) -> dict | None:
    cat = load_data_catalog()
    return cat.get("instruments", {}).get(instrument.value)


def catalog_date_bounds(instrument: InstrumentId) -> tuple | None:
    from datetime import date

    entry = catalog_entry(instrument)
    yaml_bounds: tuple[date, date] | None = None
    if entry:
        try:
            start = date.fromisoformat(str(entry["available_from"]))
            end = date.fromisoformat(str(entry["available_to"]))
            if start.year >= 2010 and end.year >= 2010:
                yaml_bounds = (start, end)
        except (KeyError, ValueError, TypeError):
            pass

    try:
        from engine.supabase_client import is_configured
        from engine.warehouse import warehouse_date_bounds

        if is_configured():
            prof = load_instrument_profile(instrument)
            wh = warehouse_date_bounds(prof.data_symbol, "15m")
            if wh:
                if yaml_bounds:
                    start = max(yaml_bounds[0], wh[0])
                    end = min(yaml_bounds[1], wh[1])
                    if start <= end:
                        return start, end
                return wh
    except Exception:
        pass

    return yaml_bounds


def asset_class_for(instrument: InstrumentId) -> AssetClass:
    prof = load_instrument_profile(instrument)
    return prof.asset_class
