"""Instrument and indicator catalogs for bot + engine."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from engine.instruments import INSTRUMENTS_DIR
from engine.models import AssetClass, InstrumentId

ROOT = Path(__file__).resolve().parents[1]
INDICATORS_PATH = ROOT / "configs" / "indicators.yaml"
RULE_TEMPLATES_PATH = ROOT / "configs" / "rule_templates.yaml"


def list_instruments_for_asset_class(asset_class: str) -> list[InstrumentId]:
    out: list[InstrumentId] = []
    for path in sorted(INSTRUMENTS_DIR.glob("*.yaml")):
        if path.name.startswith("."):
            continue
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (UnicodeDecodeError, yaml.YAMLError, OSError):
            continue
        if raw.get("asset_class") != asset_class:
            continue
        try:
            out.append(InstrumentId(raw["instrument_id"]))
        except (KeyError, ValueError):
            continue
    return out


@lru_cache(maxsize=1)
def load_indicator_catalog() -> dict:
    if not INDICATORS_PATH.exists():
        return {"indicators": {}}
    return yaml.safe_load(INDICATORS_PATH.read_text()) or {"indicators": {}}


def indicator_ids() -> list[str]:
    return list(load_indicator_catalog().get("indicators", {}).keys())


def indicator_meta(indicator_id: str) -> dict:
    return load_indicator_catalog().get("indicators", {}).get(indicator_id, {})


@lru_cache(maxsize=1)
def load_rule_templates() -> dict:
    if not RULE_TEMPLATES_PATH.exists():
        return {"templates": {}}
    return yaml.safe_load(RULE_TEMPLATES_PATH.read_text()) or {"templates": {}}


def list_prop_template_ids() -> list[str]:
    from engine.prop_firm import PACKS_DIR

    return sorted(p.stem for p in PACKS_DIR.glob("*.yaml"))
