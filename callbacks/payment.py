from os import getenv
import re

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (LabeledPrice, 
                           Message, 
                           CallbackQuery, 
                           PreCheckoutQuery)

from utils.states import Pay
from utils.db.main import Database

from keyboards.inline import pay, back_profile, back_order


router = Router()


async def send_payment(bot: Bot, user_amount: int, char_id: int, user_id: int, db: Database):
    pay_id = await db.create_replenishment_operations(user_id, user_amount)

    await bot.send_invoice(
        chat_id=char_id,
        title="Пополнение баланса",
        description="...",
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
        reply_markup=pay
    )
    return pay_id


@router.callback_query(F.data == 'replenishment_balance')
async def get_value(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(Pay.amount)
    await callback_query.message.edit_text(
        text='Введи сумму пополнения.',
        reply_markup=back_profile
    )


@router.message(Pay.amount, F.text)
async def message_payment(message: Message, bot: Bot, db: Database):
    user_amount = message.text
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not user_amount.isdigit() and re.findall(r'\d*', user_amount):
        await message.answer('Введи корректное число!')
        return

    user_amount = int(user_amount)
    await send_payment(bot, user_amount, chat_id, user_id, db)


@router.callback_query(F.data.split('|')[0] == 'replenishment_balance')
async def call_payment(callback_query: CallbackQuery, bot: Bot, db: Database):
    user_amount = float(callback_query.data.split('|')[-1])
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    await callback_query.message.delete()
    await send_payment(bot, user_amount, chat_id, user_id, db)


async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, db: Database, state: FSMContext):
    user_id = message.from_user.id
    total_amount = message.successful_payment.total_amount
    pay_id = int(message.successful_payment.invoice_payload)

    await state.clear()
    await db.update_balance(user_id, pay_id)
    await db.payment_replenishment_operations(pay_id, total_amount)
    await message.answer('Успешное пополнеие.', reply_markup=back_profile)



@router.callback_query(F.data.split('|')[0] == 'check_payment')
async def check_payment(callback_query: CallbackQuery, db: Database):
    pay_id = int(callback_query.data.split('|')[-1])

    if await db.check_payment(pay_id):
        await callback_query.message.edit_text(
            text='Готово. Заказ опубликуется после модерации.',
            reply_markup=back_order
        )
    else:
        await callback_query.answer('Оплата еще не прошла!')