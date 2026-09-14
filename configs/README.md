# Configuration files

| Path | Used by |
|------|---------|
| `instruments/*.yaml` | Symbol profile, asset class, data symbol |
| `prop_firms/*.yaml` | Wizard prop templates + USD/% engines |
| `indicators.yaml` | Custom builder + indicator study catalog |
| `rule_templates.yaml` | Wizard rule templates + study sweep defaults |
| `data_catalog.yaml` | Bot display labels for data sources |
| `examples/*.yaml` | Presets to import (Cipher B + Hola, etc.) |

Edit YAML here; restart bot/worker after deploy. Indicator study requires `sweep_template` on each indicator in `indicators.yaml`.
