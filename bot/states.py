from aiogram.fsm.state import State, StatesGroup


class WizardStates(StatesGroup):
    active = State()
    custom_date = State()
    custom_balance = State()
    preset_name = State()
