"""FSM states for the backtest wizard (locked step order)."""

from enum import IntEnum, auto


class WizardStep(IntEnum):
    """One screen = one decision; order is fixed."""

    HOME = auto()
    ASSET_CLASS = auto()
    INSTRUMENT = auto()
    DATE_RANGE = auto()
    SESSION = auto()
    SESSION_TOGGLES = auto()
    TIMEFRAMES_PRIMARY = auto()
    TIMEFRAMES_CONTEXT = auto()
    STRATEGY_MODE = auto()
    STRATEGY_PRESET = auto()
    STRATEGY_CUSTOM_INDICATORS = auto()
    STRATEGY_CUSTOM_RULE = auto()
    PROP_FIRM = auto()
    PROP_FIRM_PARAMS = auto()
    EXECUTION_BALANCE = auto()
    REVIEW = auto()
    CUSTOM_DATE_INPUT = auto()
    CUSTOM_BALANCE_INPUT = auto()
    PRESET_NAME_INPUT = auto()


# Linear wizard path (excluding home, review sub-edits, text inputs)
WIZARD_LINEAR: tuple[WizardStep, ...] = (
    WizardStep.ASSET_CLASS,
    WizardStep.INSTRUMENT,
    WizardStep.DATE_RANGE,
    WizardStep.SESSION,
    WizardStep.SESSION_TOGGLES,
    WizardStep.TIMEFRAMES_PRIMARY,
    WizardStep.TIMEFRAMES_CONTEXT,
    WizardStep.STRATEGY_MODE,
    WizardStep.PROP_FIRM,
    WizardStep.EXECUTION_BALANCE,
    WizardStep.REVIEW,
)


def step_index(step: WizardStep) -> int:
    try:
        return WIZARD_LINEAR.index(step)
    except ValueError:
        return -1


def previous_step(step: WizardStep) -> WizardStep | None:
    idx = step_index(step)
    if idx <= 0:
        return WizardStep.HOME if step != WizardStep.HOME else None
    return WIZARD_LINEAR[idx - 1]


def next_step(step: WizardStep) -> WizardStep | None:
    idx = step_index(step)
    if idx < 0 or idx >= len(WIZARD_LINEAR) - 1:
        return None
    return WIZARD_LINEAR[idx + 1]
