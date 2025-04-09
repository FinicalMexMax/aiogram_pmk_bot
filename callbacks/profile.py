import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.db.main import Database

from utils.states import EditName, EditGroupName
from keyboards.builders import inline_builder, kb_groups
from keyboards.inline import kb_back_profile


router = Router()


async def send_profile(
    user_id: int,
    db: Database,
    message: Message = None,
    callback_query: CallbackQuery = None
) -> None:
    """
    Универсальная функция для отображения профиля пользователя.
    Может вызываться как из Message, так и из CallbackQuery.
    """
    try:
        data = await db.get_user_info(user_id)
    except Exception as e:
        logging.error(f"Ошибка при получении информации пользователя: {e}")
        error_text = "Ошибка при получении профиля."
        if callback_query:
            await callback_query.answer(error_text, show_alert=True)
        elif message:
            await message.answer(error_text)
        return

    username = (message.from_user.username if message else callback_query.from_user.username)
    logging.debug(f"Полученные данные профиля: {data}")

    date_str = data.get("signup_date", "неизвестно").strftime('%d.%m.%Y') if isinstance(data.get("signup_date"), datetime) else "неизвестно"
    text = (
        f'Пользователь, @{username}\n'
        f'Группа: {data.get("group_name", "не указана")}\n'
        f'Дата регистрации: {date_str}'
    )

    buttons = [
        ('Тех. поддержка', 'support'),
        ('Изменить группу', 'update_group'),
        ('Назад', 'back_main')
    ]

    if data.get("role") == 'admin':
        buttons.insert(2, (f'Админка', 'admin_panel'))

    btn = inline_builder(
        text=[b[0] for b in buttons],
        callback_data=[b[1] for b in buttons],
        sizes=[2, 1, 1]
    )

    if callback_query:
        await callback_query.message.edit_text(text=text, reply_markup=btn)
    elif message:
        await message.answer(text=text, reply_markup=btn)


@router.callback_query(F.data.in_(['profile', 'back_profile']))
async def profile(callback_query: CallbackQuery, db: Database) -> None:
    """
    Обработчик для отображения профиля через CallbackQuery.
    """
    await send_profile(callback_query.from_user.id, db, callback_query=callback_query)


@router.callback_query(F.data.in_('update_group'))
async def update_group_name(
    callback_query: CallbackQuery, 
    db: Database, 
    state: FSMContext
) -> None:
    """
    Запускает процесс изменения группы пользователя.
    Отображает список групп для выбора.
    """
    try:
        group_name = await db.get_groups_name()
    except Exception as e:
        logging.error(f"Ошибка при получении списка групп: {e}")
        await callback_query.answer("Ошибка при получении списка групп.", show_alert=True)
        return

    await callback_query.message.edit_text(
        text='Выберите группу:',
        reply_markup=kb_groups(group_name)
    )
    await state.set_state(EditGroupName.group_name)


@router.callback_query(EditGroupName.group_name, F.data)
async def get_group_name(
    callback_query: CallbackQuery, 
    state: FSMContext, 
    db: Database
) -> None:
    """
    Обрабатывает выбор группы пользователем, обновляет группу в базе и отображает профиль.
    """
    await state.clear()
    group = callback_query.data
    user_id = callback_query.from_user.id
    await db.update_group(user_id, group)
    await send_profile(user_id, db, callback_query=callback_query)