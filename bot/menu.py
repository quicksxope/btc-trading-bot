"""Telegram slash menu (BotCommand) — selaras dengan tombol home."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


USER_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="Menu utama"),
    BotCommand(command="new", description="Backtest baru (wizard)"),
    BotCommand(command="status", description="Antrian & job aktif"),
    BotCommand(command="last", description="Hasil backtest terakhir"),
    BotCommand(command="presets", description="Preset tersimpan"),
    BotCommand(command="help", description="Glosarium & sumber data"),
    BotCommand(command="cancel", description="Batalkan wizard"),
]


def help_message_html() -> str:
    return (
        "<b>Bantuan — Agnostic Backtest Bot</b>\n\n"
        "<b>Menu</b> (tombol home = perintah slash):\n"
        "• New backtest → /new\n"
        "• My presets → /presets\n"
        "• Last results → /last\n"
        "• Status → /status\n"
        "• Help → /help\n\n"
        "<b>Glosarium</b>\n"
        "• Session: Asia / London / NY (UTC)\n"
        "• Fill: next bar open\n"
        "• Prop: daily loss &amp; max drawdown pada equity\n"
        "• MTF: context TF harus lebih tinggi dari primary\n\n"
        "<b>Data</b>\n"
        "Crypto: OHLCV di Supabase; gap di-fetch dari Coinbase saat <b>Run</b> "
        "(bukan cron harian). Step instrument menampilkan coverage DB.\n"
        "CFD: CSV lokal (fase berikutnya)."
    )


async def register_user_commands(bot: Bot) -> None:
    await bot.set_my_commands(USER_COMMANDS)
