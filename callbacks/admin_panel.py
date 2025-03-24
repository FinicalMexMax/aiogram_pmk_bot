import logging

from aiocache import Cache

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.db.main import Database
from utils.parser import Parser

from keyboards.builders import inline_builder, admin_panel_kb
from keyboards.inline import back_profile


router = Router()

cache = Cache.from_url("memory://")


async def invalidate_cache_db():
    try:
        await cache.clear()

        logging.info("Кэш успешно очищен.")
        return "Кэш очищен"
    except Exception as ex:
        logging.error(f"Ошибка при очистке кеша: {ex}")
        return str(ex)



@router.callback_query(F.data == 'invalidate_cache')
async def invalidate_cache(
    callback_query: CallbackQuery,
    db: Database
):
    response = await invalidate_cache_db(db)
    await callback_query.answer(response)


@router.callback_query(F.data == 'admin_panel')
async def admin_panel(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        text='admin panel',
        reply_markup=admin_panel_kb
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
        reply_markup=admin_panel_kb
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
