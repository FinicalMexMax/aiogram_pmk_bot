import asyncio

from os import getenv
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart

from middlewares.album import SomeMiddleware

from callbacks.new_order import router as new_order_router
from callbacks.find_performer import router as find_router
from callbacks.my_order import router as my_order_router
from callbacks.profile import router as profile_router
from callbacks.support import router as support_router
from callbacks.payment import router as pay_router
from callbacks.payment import pre_checkout_query
from callbacks.admin_panel import router as admin_router

from keyboards.builders import inline_builder

from utils.database import Database


router = Router()

load_dotenv()


@router.message(CommandStart())
@router.callback_query(F.data == 'back_main')
async def main_menu(message: Message | CallbackQuery, db: Database) -> None:
    pattern = dict(
        text='hello',
        reply_markup=inline_builder(
            text=[
                'Расписание', 'Заказы',
                'Профиль'
            ],
            callback_data=[
                'schedules', 'order',
                'profile'
            ],
            sizes=2
        )
    )

    await db.add_user(
        user_id=message.from_user.id,
        user_name=message.from_user.username
    )

    if isinstance(message, CallbackQuery):
        await message.message.edit_text(**pattern)
        return

    await message.answer(**pattern)


async def main() -> None:
    bot = Bot(getenv("TOKEN"))
    dp = Dispatcher()
    db = Database()

    await db.connect()
    await db.create_and_check_table()

    dp.message.middleware(SomeMiddleware())

    dp.pre_checkout_query.register(pre_checkout_query)

    dp.include_routers(
        router,
        new_order_router,
        find_router,
        my_order_router,
        profile_router,
        support_router,
        pay_router,
        admin_router
    )

    await bot.delete_webhook(True)
    await dp.start_polling(bot, db=db)


if __name__ == '__main__':
    asyncio.run(main())