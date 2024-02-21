from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.database import Database

from keyboards.builders import inline_builder, admin_panel_kb
from keyboards.inline import back_profile


router = Router()


@router.callback_query(F.data == 'admin_panel')
async def admin_panel(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        text='admin panel',
        reply_markup=admin_panel_kb
    )


@router.callback_query(F.data == 'get_support_message')
async def get_support_messages(
    callback_query: CallbackQuery, 
    db: Database
) -> None:
    ...