from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.database import Database
from utils.states import EditNick

from keyboards.builders import inline_builder
from keyboards.inline import back_profile


router = Router()


@router.callback_query(F.data.in_(['profile', 'back_profile', 'cancel_pay']))
async def profile(callback_query: CallbackQuery, db: Database):
    username = callback_query.from_user.username
    
    data = await db.get_user_info(callback_query.from_user.id)
    text = f'Пользователь, @{username}\n' \
           f'Ник: {data[1].get("user_nick")}\n' \
           f'Роль: {data[1].get("role")}\n' \
           f'Баланс: {data[1].get("balance")} ₽\n' \
           f'Количество активных заказов: {data[0].get("count")}\n' \
           f'Дата регистрации: {data[1].get("datetime_reg")}'
    
    if data[1].get("role") == 'заказчик':
        rep_text = 'Стать исполнителем'
        call_text = 'edit_role|исполнитель'
    else:
        rep_text = 'Стать заказчиком'
        call_text = 'edit_role|заказчик'

    if data[1].get('role') == 'админ':
        count_support_message = await db.get_count_suppoer_message()

        btn = inline_builder(
            text=[
                'Админка', 'Изменить ник',
                'Пополнить баланс',
                f'Обращения - ({count_support_message})',
                'Назад'
            ],
            callback_data=[
                'admin_panel', 'edit_nick',
                'replenishment_balance',
                'get_suppoet_message',
                'back_main'
            ],
            sizes=[2,1]
        )
    else:
        btn = inline_builder(
            text=[
                rep_text, 'Изменить ник',
                'Пополнить баланс',
                'Тех. поддержка',
                'Назад'
            ],
            callback_data=[
                call_text, 'edit_nick',
                'replenishment_balance',
                'support',
                'back_main'
            ],
            sizes=[2,1]
        )

    if callback_query.data == 'cancel_pay':
        await callback_query.message.delete()
        await callback_query.message.answer(
            text=text,
            reply_markup=btn
        )
        return
    
    await callback_query.message.edit_text(
        text=text,
        reply_markup=btn
    )


@router.callback_query(F.data.split('|')[0] == 'edit_role')
async def edit_role(callback_query: CallbackQuery, db: Database):
    user_id = callback_query.from_user.id
    role = callback_query.data.split('|')[1].strip()
    await db.update_role(user_id, role)

    if role == 'исполнитель':
        text = f'Теперь ваша роль, {role}.\n' \
                'При появлении нового заказа отправлю уведомление.'
    else:
        text = f'Теперь ваша роль, {role}.'

    await callback_query.message.edit_text(
        text=text,
        reply_markup=back_profile
    )


@router.callback_query(F.data == 'edit_nick')
async def edit_nick(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(EditNick.name)
    await callback_query.message.edit_text(
        text='Ну и на что изменить?',
        reply_markup=back_profile
    )


@router.message(EditNick.name, F.text)
async def edit_nick_(message: Message, db: Database):
    user_id = message.from_user.id
    nick = message.text.strip()

    answer_edit_nick = await db.edit_nick(user_id, nick)
    await message.answer(text=answer_edit_nick, reply_markup=back_profile)