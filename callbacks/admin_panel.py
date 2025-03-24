import logging

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.db.main import Database
from utils.parser import Parser

from keyboards.builders import inline_builder, kb_admin_panel


router = Router()


@router.callback_query(F.data == 'admin_panel')
async def admin_panel(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        text='admin panel',
        reply_markup=kb_admin_panel
    )


@router.callback_query(F.data == 'update_schedule')
async def update_schedules(
    callback_query: CallbackQuery,
    db: Database
):
    parser = Parser()
    await parser.get_schedule()
    await parser.save_db_data(db)

    await callback_query.answer(
        text='Успешно обновлено.',
        reply_markup=kb_admin_panel
    )


@router.callback_query(F.data == 'get_support_message')
async def get_support_messages(
    callback_query: CallbackQuery, 
    db: Database
) -> None:
    support_messages = await db.get_support_messages()
    
    if support_messages:
        await callback_query.answer("Сообщения поддержки: \n" + "\n".join(support_messages))
    else:
        await callback_query.answer("Нет сообщений поддержки.")
