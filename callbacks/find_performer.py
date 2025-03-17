from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from utils.sender import answer_text
from utils.db.order_manager import OrderManager
from utils.db.user_service import UserService


router = Router()


@router.callback_query(F.data == 'find_performer')
async def profile(callback_query: CallbackQuery, order_manager: OrderManager):
    ...