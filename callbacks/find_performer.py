from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from utils.sender import answer_text
from utils.database import Database


router = Router()


@router.callback_query(F.data == 'find_performer')
async def profile(callback_query: CallbackQuery, db: Database):
    ...