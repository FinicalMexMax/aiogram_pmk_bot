from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


kb_back_main = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Назад', callback_data='back_main')]
    ]
)

kb_back_profile = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Назад', callback_data='back_profile')]
    ]
)

kb_skip = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Пропустить', callback_data='skip')],
        [InlineKeyboardButton(text='Назад', callback_data='back_order')]
    ]
)