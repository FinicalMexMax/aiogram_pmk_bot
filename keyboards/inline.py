from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


back_main = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Назад', callback_data='back_main')]
    ]
)

back_profile = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Назад', callback_data='back_profile')]
    ]
)

pay = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Пополнить', pay=True)],
        [InlineKeyboardButton(text='Отмена', callback_data='cancel_pay')]
    ]
)


def check_payment_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Проверить оплату', callback_data=f'check_payment|{order_id}')],
            [InlineKeyboardButton(text='Отмена', callback_data='cancel_pay')]
        ]
    )

back_order = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Назад', callback_data='back_order')]
    ]
)

skip = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Пропустить', callback_data='skip')],
        [InlineKeyboardButton(text='Назад', callback_data='back_order')]
    ]
)