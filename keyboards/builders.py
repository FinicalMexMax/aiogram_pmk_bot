from random import choice

from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


def inline_builder(
    text: str | list[str],
    callback_data: str | list[str],
    sizes: int | list[int]=2,
    **kwargs
) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    if isinstance(text, str):
        text = [text]
    if isinstance(callback_data, str):
        callback_data = [callback_data]
    if isinstance(sizes, int):
        sizes = [sizes]

    [
        builder.button(text=txt, callback_data=cb)
        for txt, cb in zip(text, callback_data)
    ]

    builder.adjust(*sizes)
    return builder.as_markup(**kwargs)


def reply_builder(
    text: str | list[str],
    sizes: int | list[int],
    **kwargs
) -> ReplyKeyboardBuilder:
    builder = ReplyKeyboardBuilder()

    if isinstance(text, str):
        text = [text]
    if isinstance(text, int):
        sizes = [text]

    [
        builder.button(text=txt)
        for txt in text
    ]

    builder.adjust(*sizes)
    return builder.as_markup(**kwargs)


support_completed = inline_builder(
    text=[
        choice(['Да. Все гуд', 'Да', 'Угу', 'Отправляй']),
        'Отмена'
    ],
    callback_data=[
        'support_completed',
        'back_profile'
    ],
    sizes=1
)


admin_panel_kb = inline_builder(
    text=[
        'Пользователи', 'Уведомления',
        'Управление заказами',
        'Назад'
    ],
    callback_data=[
        'admin_users', 'admin_notif',
        'admin_order',
        'back_profile'
    ],
    sizes=[2,1]
)


class Pagination(CallbackData, prefix='pag'):
    action: str
    page: int


def paginator(page: int=0):
    return inline_builder(
        text=[
            '⬅️',
            '➡️',
            'Назад'
        ],
        callback_data=[
            Pagination(action='prev', page=page),
            Pagination(action='next', page=page),
            'back_order'
        ]
    )