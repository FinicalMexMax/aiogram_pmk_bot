import asyncio
import logging
from os import getenv
from dotenv import load_dotenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

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
from utils.parser import Parser
from utils.states import GetGroupName


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

router = Router()
load_dotenv()


async def run_parser(db: Database):
    logger.info("Запуск парсера...")
    try:
        parser = Parser()
        await parser.get_schedule()
        await parser.save_db_data(db)
        logger.info("Парсер успешно завершил работу.")
    except Exception as e:
        logger.error(f"Ошибка в парсере: {e}", exc_info=True)


async def scheduler_task(db: Database):
    logger.info("Запуск планировщика...")
    scheduler = AsyncIOScheduler()

    scheduler.add_job(run_parser, IntervalTrigger(hours=2), kwargs={"db": db})
    scheduler.start()


async def welcome_message(
    message: Message | CallbackQuery,
    db: Database,
    group: str = None
):
    if group:
        await db.add_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            group_name=group
        )
        logger.info(f"Добавлен новый пользователь {message.from_user.username} в группу {group}")

    pattern = dict(
        text="Hello",
        reply_markup=inline_builder(
            text=["Расписание", "Заказы", "Профиль"],
            callback_data=["schedules", "order", "profile"],
            sizes=2
        )
    )

    if isinstance(message, CallbackQuery):
        await message.message.edit_text(**pattern)
    else:
        await message.answer(**pattern)


@router.message(CommandStart())
@router.callback_query(F.data == "back_main")
async def main_menu(
    message: Message | CallbackQuery,
    db: Database,
    state: FSMContext
):
    user_id = message.from_user.id

    if not await db.user_exists(user_id):
        groups = await db.get_groups_name()
        await message.answer("Из какой ты группы?", reply_markup=kb_groups(groups))
        await state.set_state(GetGroupName.group_name)
        logger.info(f"Пользователь {user_id} выбирает группу.")
        return

    await welcome_message(message, db)


@router.callback_query(GetGroupName.group_name, F.data)
async def get_group_name(callback_query: CallbackQuery, state: FSMContext, db: Database):
    await state.clear()
    logger.info(f"Пользователь {callback_query.from_user.id} выбрал группу {callback_query.data}")
    await welcome_message(callback_query, db, callback_query.data)


async def main():
    logger.info("Запуск бота...")

    bot = Bot(getenv("TG_TOKEN"))
    dp = Dispatcher()
    db = Database()

    await db.connect()
    await db.create_and_check_table()

    dp.message.middleware(SomeMiddleware())
    dp.pre_checkout_query.register(pre_checkout_query)

    dp.include_routers(
        router, new_order_router, find_router, my_order_router,
        profile_router, support_router, pay_router, admin_router, schedule_router
    )

    asyncio.create_task(scheduler_task(db))

    await bot.delete_webhook(True)
    await dp.start_polling(bot, db=db)

    await db.close()
    logger.info("База данных закрыта. Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
