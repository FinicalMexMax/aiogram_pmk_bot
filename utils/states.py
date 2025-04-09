from aiogram.fsm.state import State, StatesGroup


class SupportMessage(StatesGroup):
    message = State()
    photo = State()


class EditName(StatesGroup):
    name = State()


class EditGroupName(StatesGroup):
    group_name = State()


class GetGroupName(StatesGroup):
    group_name = State()