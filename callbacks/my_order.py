from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.media_group import MediaGroupBuilder

from utils.sender import answer_text
from utils.db.main import Database

from keyboards.builders import Pagination, paginator_orders, inline_builder


router = Router()


def get_text(data: dict):
    text = f'Статус: {data.get("status")}\n\n' \
           f'Название: {data.get("title")}\n' \
           f'Тип работы {data.get("work_type")}\n' \
           f'Описание: {data.get("about")}\n' \
           f'Прайс: {data.get("price")} ₽\n' \
    
    photo_list = data.get('photo')
    if photo_list:
        count = len(photo_list)
        text = f'{text}' \
               f"\nКол-во фотографий: {count}"
        
    file_list = data.get('file')
    if file_list:
        count = len(file_list)
        text = f'{text}' \
               f"\nКол-во файлов: {count}\n"
        
    return text


@router.callback_query(F.data == 'my_order')
async def profile(callback_query: CallbackQuery, db: Database):
    user_id = callback_query.from_user.id
    data = await db.get_order_data(user_id)

    if not data:
        await callback_query.answer('Нет заказов!')
        return

    text = get_text(data[0])

    await callback_query.message.edit_text(text=text, reply_markup=paginator_orders())


@router.callback_query(Pagination.filter(F.action.in_(['prev', 'next'])))
async def pagination_handler(call: CallbackQuery, callback_data: Pagination, db: Database):
    user_id = call.from_user.id
    data = await db.get_order_data(user_id)

    page_num = int(callback_data.page)
    page = page_num - 1 if page_num > 0 else 0

    if callback_data.action == 'next':
        page = page_num + 1 if page_num < (len(data) - 1) else page_num

    text = get_text(data[page])

    await call.message.edit_text(text=text, reply_markup=paginator_orders(page))