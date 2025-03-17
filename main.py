import asyncio
from os import getenv
from dotenv import load_dotenv

import aioredis

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from middlewares.album import SomeMiddleware
from callbacks.new_order import router as new_order_router
from callbacks.find_performer import router as find_router
from callbacks.my_order import router as my_order_router
from callbacks.profile import router as profile_router
from callbacks.support import router as support_router
from callbacks.payment import router as pay_router, pre_checkout_query
from callbacks.admin_panel import router as admin_router
from callbacks.schedule import router as schedule_router

from keyboards.builders import inline_builder, kb_groups
from utils.db.main import Database
from utils.db.user_service import UserService
from utils.db.payment_service import PaymentService
from utils.db.schedule_manager import ScheduleManager
from utils.db.order_manager import OrderManager
from utils.db.admin_manager import AdminManager

from utils.states import GetGroupName
from utils.parser import Parser


router = Router()
load_dotenv()


async def welcome_message(
    message: Message | CallbackQuery,
    user_service: UserService,
    group: str = None
):
    if group:
        await user_service.add_user(
            user_id=message.from_user.id,
            user_name=message.from_user.username,
            group_name=group
        )

    pattern = dict(
        text='Hello',
        reply_markup=inline_builder(
            text=['Расписание', 'Заказы', 'Профиль'],
            callback_data=['schedules', 'order', 'profile'],
            sizes=2
        )
    )

    if isinstance(message, CallbackQuery):
        await message.message.edit_text(**pattern)
    else:
        await message.answer(**pattern)


@router.message(CommandStart())
@router.callback_query(F.data == 'back_main')
async def main_menu(
    message: Message | CallbackQuery,
    user_service: UserService,
    schedule_manager: ScheduleManager,
    state: FSMContext
):
    user_id = message.from_user.id

    if not await user_service.user_exists(user_id):
        groups = await schedule_manager.get_groups_name()
        await message.answer('Из какой ты группы?', reply_markup=kb_groups(groups))
        return await state.set_state(GetGroupName.group_name)

    await welcome_message(message, user_service)


@router.callback_query(GetGroupName.group_name, F.data)
async def get_group_name(callback_query: CallbackQuery, state: FSMContext, user_service: UserService):
    await state.clear()
    await welcome_message(callback_query, user_service, callback_query.data)


async def main():
    bot = Bot(getenv("TG_TOKEN"))
    dp = Dispatcher()
    db = Database()

    await db.connect()
    await db.create_and_check_table()

    user_service = UserService(db.pool)
    schedule_manager = ScheduleManager(db.pool)
    order_manager = OrderManager(db.pool)
    payment_service = PaymentService(db.pool)
    admin_manager = AdminManager(db.pool)

    dp.message.middleware(SomeMiddleware())
    dp.pre_checkout_query.register(pre_checkout_query)

    dp.include_routers(
        router, new_order_router, find_router, my_order_router,
        profile_router, support_router, pay_router, admin_router, schedule_router
    )

    await bot.delete_webhook(True)
    await dp.start_polling(
        bot,
        user_service=user_service,
        admin_manager=admin_manager,
        schedule_manager=schedule_manager,
        order_manager=order_manager,
        payment_service=payment_service
    )

    await db.close()


if __name__ == '__main__':
    asyncio.run(main())