import re

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards.builders import inline_builder
from keyboards.inline import kb_back_order, kb_skip, kb_back_main, check_payment_kb

from utils.states import NewOrder
from utils.sender import answer_text, answer_file, answer_photo
from utils.db.main import Database


router = Router()


@router.callback_query(F.data == 'order')
@router.callback_query(F.data == 'back_order')
async def main_order(callback_query: CallbackQuery, state: FSMContext):
    if callback_query.data == 'back_order':
        await state.clear()

    text = "Тут ты можешь разместить свой заказ на выполнение любой работы.\n" \
           "P.S. Всё, представленное в этом разделе, реализовано в образовательных целях!"

        
    pattern = dict(
        text=text,
        reply_markup=inline_builder(
            text=[
                'Создать заказ', 'Найти исполнителя',
                'Мои заказы',
                'Назад'
            ],
            callback_data=[
                'create_order', 'find_performer',
                'my_order',
                'back_main'
            ],
            sizes=[2, 1]
        )
    )

    await callback_query.message.edit_text(**pattern)


@router.callback_query(F.data == 'create_order')
async def order_create(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(NewOrder.type_work)
    await callback_query.message.edit_text(
        text='Что за работа? Выбери или напиши свой вариант.', 
        reply_markup=inline_builder(
            text=['Практическая', 'Самостоятельная', 'Отмена'],
            callback_data=['Практическая', 'Самостоятельная', 'back_order'],
            sizes=[2, 1]
        )
    )


@router.message(NewOrder.type_work, F.text)
@router.callback_query(F.data.in_(['Практическая', 'Самостоятельная']))
async def order_title(message: Message | CallbackQuery, state: FSMContext):
    if isinstance(message, CallbackQuery):
        await state.update_data(type_work=message.data)
        await message.message.edit_text(text='Введи название работы', reply_markup=kb_back_order)
    else:
        await state.update_data(type_work=message.text)
        await message.answer(text='Введи название работы', reply_markup=kb_back_order)

    await state.set_state(NewOrder.title)


@router.message(NewOrder.title, F.text)
async def order_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(NewOrder.about)
    await message.answer(text='А теперь описание работы', reply_markup=kb_skip)


@router.callback_query(NewOrder.about, F.data == 'skip')
async def order_skip_photo(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(about=None)
    await state.set_state(NewOrder.photo)
    await callback_query.message.edit_text(
        text='Ну а сейчас скинь фото, если это надо\nНо не больше 10', 
        reply_markup=kb_skip
    )


@router.message(NewOrder.about, F.text)
async def order_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(NewOrder.photo)
    await message.answer(text='Ну а сейчас скинь фото, если это надо\nНо не больше 10', reply_markup=kb_skip)


@router.message(NewOrder.photo, F.photo)
async def order_photo(message: Message, album: list[Message], state: FSMContext):
    photo_list = []
    for photo in album[:10]:
        photo_list.append(photo.photo[-1].file_id)

    await state.update_data(photo=photo_list)
    await state.set_state(NewOrder.file)
    await message.answer(text='Файл-ы, так же если надо', reply_markup=kb_skip)


@router.callback_query(NewOrder.photo, F.data == 'skip')
async def order_skip_photo(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(photo=[])
    await state.set_state(NewOrder.file)
    await callback_query.message.edit_text(text='Файл-ы, так же если надо\nВсе так же, не больше 10', reply_markup=kb_skip)


@router.message(NewOrder.file, F.document)
async def order_file(message: Message | CallbackQuery, album: list[Message], state: FSMContext):
    file_list = []
    for file in album[:10]:
        file_list.append(file.document.file_id)

    await state.update_data(file=file_list)
    await state.set_state(NewOrder.price)
    await message.answer(text='Сумма вознаграждения за работу', reply_markup=kb_back_order)


@router.callback_query(NewOrder.file, F.data == 'skip')
async def order_skip_photo(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(file=[])
    await state.set_state(NewOrder.price)
    await callback_query.message.edit_text(text='Сумма вознаграждения за работу', reply_markup=kb_back_order)


@router.message(NewOrder.price, F.text)
async def order_price(message: Message, state: FSMContext):
    text = message.text
    if not text.isdigit():
        await message.answer('Введи корректное число!')
        return
    
    await state.update_data(price=int(text))
    data = await state.get_data()

    confirmation_text = (
        f"Тип работы: {data['type_work']}\n"
        f"Название работы: {data['title']}\n"
        f"Описание работы: {data.get('about', 'Не указано')}\n"
        f"Фото: {len(data.get('photo', []))} шт.\n"
        f"Файлы: {len(data.get('file', []))} шт.\n"
        f"Цена: {data['price']} ₽\n\n"
        "Все верно?"
    )
    
    await message.answer(
        confirmation_text,
        reply_markup=inline_builder(
            text=['Подтвердить', 'Изменить'],
            callback_data=['order_completed', 'edit_order'],
            sizes=[2]
        )
    )


@router.callback_query(F.data == 'edit_order')
async def edit_order(callback_query: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    await callback_query.message.edit_text('Что ты хочешь изменить?')
    await state.set_state(NewOrder.type_work)


@router.callback_query(F.data == 'order_completed')
async def order_completed(callback_query: CallbackQuery, db: Database, state: FSMContext):
    user_id = callback_query.from_user.id
    data = await state.get_data()
    data['customer'] = user_id
    price = data['price']

    balance = await db.get_balance(user_id)
    if balance < price:
        price = price - balance
        pattern = dict(
            text='Недостаточно средств на счету!',
            reply_markup=inline_builder(
                text=[
                    f'Пополнить баланс на {price} ₽',
                    'Отмена'
                ],
                callback_data=[
                    f'replenishment_balance|{price}',
                    'back_order'
                ],
                sizes=1
            )
        )

        data['status'] = 'Ожидание оплаты'

        await callback_query.message.answer(**pattern)
        order_id = await db.add_order(data)

        data['reply_markup'] = check_payment_kb(order_id['order_id'])

        await answer_text(callback_query.message, data)
        return

    await state.clear()
    answer_db = await db.add_order(data)
    await callback_query.message.edit_text(
        text=answer_db['text'],
        reply_markup=kb_back_main
    )
