from aiogram.fsm.state import State, StatesGroup


class WizardStates(StatesGroup):
    active = State()
    custom_date = State()
    custom_balance = State()
    custom_rule_long = State()
    custom_rule_short = State()
    preset_name = State()
