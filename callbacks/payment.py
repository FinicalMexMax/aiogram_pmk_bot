import logging
from os import getenv
from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (LabeledPrice, 
                           Message, 
                           CallbackQuery, 
                           PreCheckoutQuery)

from utils.states import Pay
from utils.db.main import Database

from callbacks.profile import send_profile

from keyboards.inline import kb_pay, kb_back_profile, kb_back_order


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


async def send_payment(bot: Bot, user_amount: int, char_id: int, user_id: int, db: Database):
    pay_id = await db.create_replenishment_operations(user_id, user_amount)

    await bot.send_invoice(
        chat_id=char_id,
        title="Пополнение баланса",
        description="номер карты для тестовой оплаты - 4918019199883839",
        provider_token=getenv('TG_PAYMENT_TOKEN'),
        currency="rub",
        photo_url="https://www.aroged.com/wp-content/uploads/2022/06/Telegram-has-a-premium-subscription.jpg",
        photo_width=416,
        photo_height=234,
        photo_size=416,
        is_flexible=False,
        max_tip_amount=5000000,
        suggested_tip_amounts=[10000, 25000, 50000],
        prices=[
            LabeledPrice(label="Пополнение баланса", amount=user_amount*100)
        ],
        payload=str(pay_id),
        reply_markup=kb_pay
    )
    return pay_id


@router.callback_query(F.data.in_('replenishment_balance'))
async def get_value(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(Pay.amount)
    await callback_query.message.edit_text(
        text='Введи сумму пополнения.',
        reply_markup=kb_back_profile
    )

@router.callback_query(F.data == 'cancel_payment')
async def cancel_payment(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer(
        text="Пополнение отменено.",
        reply_markup=kb_back_profile
    )


@router.message(Pay.amount, F.text)
async def message_payment(message: Message, bot: Bot, db: Database):
    user_amount = message.text
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not user_amount.isdigit() or int(user_amount) < 100:
        await message.answer('Введи корректное число!\n\nОно должно быть четным и больше 100₽!')
        return

    user_amount = Decimal(user_amount)
    await send_payment(bot, user_amount, chat_id, user_id, db)


@router.callback_query(F.data.startswith('replenishment_balance'))
async def call_payment(callback_query: CallbackQuery, bot: Bot, db: Database):
    try:
        user_amount = Decimal(callback_query.data.split('|')[-1])
    except ValueError:
        await callback_query.answer('Некорректная сумма!')
        return

    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    await callback_query.message.delete()
    await send_payment(bot, user_amount, chat_id, user_id, db)


async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery, bot: Bot):
    try:
        await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)
    except Exception as e:
        logging.error(f"Ошибка при ответе на pre_checkout_query: {e}")


@router.message(F.successful_payment)
async def successful_payment(message: Message, db: Database, state: FSMContext):
    user_id = message.from_user.id
    total_amount = Decimal(message.successful_payment.total_amount) / Decimal(100)
    pay_id = int(message.successful_payment.invoice_payload)

    logging.info(f"Пользователь {user_id} успешно оплатил платежа с ID {pay_id}.")

    await db.payment_replenishment_operations(pay_id, total_amount)
    await db.clear_cache(user_id)

    await state.clear()

    await message.answer(
        text=f"Ваш платеж на сумму {total_amount}₽ был успешно обработан!",
        reply_markup=kb_back_profile
    )


@router.callback_query(F.data.startswith('check_payment'))
async def check_payment(callback_query: CallbackQuery, db: Database):
    pay_id = int(callback_query.data.split('|')[-1])

    if await db.check_payment(pay_id):
        await callback_query.message.edit_text(
            text='Готово. Заказ опубликуется после модерации.',
            reply_markup=kb_back_order
        )
    else:
        await callback_query.answer('Оплата еще не прошла!')