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

kb_pay = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Пополнить', pay=True)],
        [InlineKeyboardButton(text='Отмена', callback_data='back_profile')]
    ]
)


def check_payment_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Проверить оплату', callback_data=f'check_payment|{order_id}')],
            [InlineKeyboardButton(text='Отмена', callback_data='back_profile')]
        ]
    )

kb_back_order = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Назад', callback_data='back_order')]
    ]
)

kb_skip = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Пропустить', callback_data='skip')],
        [InlineKeyboardButton(text='Назад', callback_data='back_order')]
    ]
)