"""Admin commands: health, queue, data catalog."""

from __future__ import annotations

from html import escape

import yaml
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.settings import Settings
from engine.instruments import load_data_catalog
from engine.prop_firm import PACKS_DIR
from storage.db import Database

router = Router()


def _is_admin(user_id: int, settings: Settings) -> bool:
    allowed = settings.allowed_ids()
    return not allowed or user_id in allowed


@router.message(Command("health"))
async def health(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    await message.answer("OK — bot and DB reachable")


@router.message(Command("queue"))
async def queue_info(message: Message, db: Database, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    running, queued = await db.count_active(message.from_user.id)
    await message.answer(f"Your jobs — running: {running}, queued: {queued}")


@router.message(Command("admin"))
async def data_status(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    cat = load_data_catalog().get("instruments", {})
    lines = ["<b>Data catalog</b>"]
    for k, v in cat.items():
        src = v.get("source", "local")
        lines.append(
            f"{k} ({src}): {v.get('available_from')} .. {v.get('available_to')} [{v.get('data_symbol')}]"
        )
    lines.append("")
    lines.append("<b>Indicators</b> (configs/indicators.yaml)")
    from engine.catalog import indicator_ids, indicator_meta

    for iid in indicator_ids():
        meta = indicator_meta(iid)
        lines.append(f"• {iid}: {meta.get('label', iid)}")
    lines.append("")
    lines.append("<b>Prop packs</b> (configs/prop_firms/)")
    wizard_packs = {
        "ftmo_like",
        "holaprime_1step_50k",
        "holaprime_direct_50k",
        "topstep_50k_combine",
    }
    for path in sorted(PACKS_DIR.glob("*.yaml")):
        if path.name.startswith("."):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        label = raw.get("label") or path.stem
        desc = (raw.get("description") or "")[:100]
        wizard = "wizard" if path.stem in wizard_packs else "YAML/preset"
        lines.append(f"• {escape(label)} <code>{path.stem}</code> [{wizard}]")
        if desc:
            lines.append(f"  {escape(desc)}")
    lines.append("")
    lines.append(
        "<i>Hola: use configs/examples/cipher_b_holaprime_1step_30m.yaml → My presets.</i>"
    )
    await message.answer("\n".join(lines))
