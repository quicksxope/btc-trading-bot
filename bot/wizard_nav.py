"""Wizard back-navigation stack."""

from __future__ import annotations

from aiogram.fsm.context import FSMContext

STEP_ORDER = (
    "home",
    "asset",
    "instrument",
    "dates",
    "timeframe_primary",
    "timeframe_context",
    "study_pool",
    "strategy_mode",
    "strategy_detail",
    "session",
    "session_toggles",
    "risk_reward",
    "prop",
    "prop_params",
    "balance",
    "review",
)


async def push_step(state: FSMContext, step: str) -> None:
    data = await state.get_data()
    stack: list[str] = list(data.get("wizard_stack", []))
    if stack and stack[-1] == step:
        return
    stack.append(step)
    await state.update_data(wizard_stack=stack)


async def pop_step(state: FSMContext) -> str | None:
    data = await state.get_data()
    stack: list[str] = list(data.get("wizard_stack", []))
    if not stack:
        return None
    stack.pop()
    await state.update_data(wizard_stack=stack)
    return stack[-1] if stack else None


async def clear_stack(state: FSMContext) -> None:
    await state.update_data(wizard_stack=[])
