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
    callback_query: CallbackQuery = None,
    clear_cache: bool = False
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

    date_str = data.get("datetime_reg", "неизвестно").strftime('%d.%m.%Y') if isinstance(data.get("datetime_reg"), datetime) else "неизвестно"
    text = (
        f'Пользователь, @{username}\n'
        f'Ник: {data.get("user_name", "не указан")}\n'
        f'Группа: {data.get("group_name", "не указана")}\n'
        f'Роль: {data.get("role", "не указана")}\n'
        f'Баланс: {data.get("balance", 0)} ₽\n'
        f'Количество активных заказов: {data.get("orders_count", 0)}\n'
        f'Дата регистрации: {date_str}'
    )

    buttons = [
        ('Изменить ник', 'update_name'),
        ('Изменить группу', 'update_group'),
        ('Пополнить баланс', 'replenishment_balance'),
        ('Тех. поддержка', 'support'),
        ('Назад', 'back_main')
    ]

    if data.get("role") == 'admin':
        buttons.insert(3, (f'Админка', 'admin_panel'))

    else:
        if data.get("role") == 'заказчик':
            buttons.insert(1, ('Стать исполнителем', 'update_role|исполнитель'))
        else:
            buttons.insert(1, ('Стать заказчиком', 'update_role|заказчик'))

    btn = inline_builder(
        text=[b[0] for b in buttons],
        callback_data=[b[1] for b in buttons],
        sizes=[2, 2, 1]
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


@router.callback_query(F.data.startswith('update_role'))
async def update_role(callback_query: CallbackQuery, db: Database) -> None:
    """
    Обработчик для смены роли пользователя.
    """
    user_id = callback_query.from_user.id
    try:
        new_role = callback_query.data.split('|')[1].strip()
    except IndexError:
        logging.error(f"[{user_id}] Неверный формат данных для смены роли: {callback_query.data}")
        await callback_query.answer("Неверный формат запроса.", show_alert=True)
        return

    user_info = await db.get_user_info(user_id)
    current_role = user_info.get("role")

    if current_role == new_role:
        await callback_query.answer("Вы уже в этой роли!", show_alert=True)
        return

    await db.update_role(user_id, new_role)
    logging.info(f"[{user_id}] Роль успешно изменена: {current_role} → {new_role}")
    await callback_query.answer(f"Ваша роль теперь: {new_role}.", show_alert=True)
    await send_profile(user_id, db, callback_query=callback_query)


@router.callback_query(F.data.in_('update_name'))
async def update_name(callback_query: CallbackQuery, state: FSMContext) -> None:
    """
    Запускает процесс изменения ника.
    """
    await state.set_state(EditName.name)
    await callback_query.message.edit_text(
        text='Введите новый ник:',
        reply_markup=kb_back_profile
    )


@router.message(EditName.name, F.text)
async def handle_update_nick(message: Message, db: Database, state: FSMContext) -> None:
    """
    Обрабатывает ввод нового ника, проверяет его валидность и обновляет в базе.
    После изменения ника обновляет профиль пользователя.
    """
    user_id = message.from_user.id
    nick = message.text.strip()
    black_list = ['админ', 'admin', 'администратор', 'administrator']

    if nick.lower() in black_list:
        await message.answer('Ник не может быть таким!', reply_markup=kb_back_profile)
        return

    result = await db.update_nick(user_id, nick)
    if not result:
        await message.answer('Ник уже занят!', reply_markup=kb_back_profile)
        return

    await state.clear()
    await send_profile(user_id, db, message=message)


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