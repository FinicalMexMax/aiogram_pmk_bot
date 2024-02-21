from aiogram.fsm.state import State, StatesGroup


class NewOrder(StatesGroup):
    title = State()
    type_work = State()
    about = State()
    photo = State()
    file = State()
    price = State()


class SupportMessage(StatesGroup):
    message = State()
    photo = State()


class EditNick(StatesGroup):
    name = State()


class Pay(StatesGroup):
    id = State()
    amount = State()