from random import choice

from aiogram import Bot
from aiogram.types import Message
from aiogram.utils.media_group import MediaGroupBuilder

from keyboards.builders import inline_builder


async def answer_text(
    message: Message, 
    data: dict
) -> None:
    text = f'Название: {data.get("title")}\n' \
           f'Тип работы: {data.get("type_work")}\n' \
           f'Описание: {data.get("about")}\n' \
           f'Прайс: {data.get("price")} ₽\n\n' \
           f'Все гуд?'
    
    keyboard = data.get('reply_markup')
    status = data.get('status')
    if status:
        text = f'Статус: {status}\n\n' \
               f'{text}'

    pattern: dict = {'text': text}

    if keyboard:
        pattern['reply_markup'] = keyboard
        await message.edit_text(**pattern)
        return
    
    pattern['reply_markup'] = inline_builder(
        text=[
            choice(['Да. Все гуд', 'Да', 'Угу', 'Отправляй']),
            'Отмена'
        ],
        callback_data=[
            'order_completed',
            'back_order'
        ],
        sizes=1
    )
    
    await message.answer(**pattern)


async def answer_photo(message: Message, data: dict) -> None:
    photo_list = data.get('photo')

    if photo_list:
        if isinstance(photo_list, str):
            photo_list = photo_list.split(',')

        media_group = MediaGroupBuilder()
        for photo in photo_list:
            media_group.add_photo(media=photo)
        await message.answer_media_group(media=media_group.build())


async def answer_file(message: Message, data: dict) -> None:
    file_list = data.get('file')

    if file_list:
        if isinstance(file_list, str):
            file_list = file_list.split(',')

        media_group = MediaGroupBuilder()
        for file in file_list:
            media_group.add_document(media=file)
        await message.answer_media_group(media=media_group.build())