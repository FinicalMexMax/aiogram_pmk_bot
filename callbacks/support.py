from random import choice

from aiogram import F, Router, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder

from utils.db.main import Database
from utils.states import SupportMessage

from keyboards.inline import back_profile, skip
from keyboards.builders import support_completed, inline_builder


router = Router()


@router.callback_query(F.data.in_(['support', 'back_profile']))
async def support(
    callback_query: CallbackQuery, 
    state: FSMContext
) -> None:
    await state.set_state(SupportMessage.message)
    await callback_query.message.edit_text(
        text='Что случилось?',
        reply_markup=back_profile
    )


@router.message(SupportMessage.message, F.text)
async def support_message(
    message: Message,
    state: FSMContext
) -> None:
    await state.update_data(message=message.text.strip())
    await state.set_state(SupportMessage.photo)
    await message.answer(
        text='Можно прикрепить фото, если оно поможет решить проблему.', 
        reply_markup=skip
    )


@router.callback_query(SupportMessage.photo, F.data == 'skip')
async def skip_photo(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(photo=[])
    data = await state.get_data()

    text = f"{data.get('message')}\n\n" \
           'Отправляю?'

    await callback_query.message.edit_text(
        text=text, 
        reply_markup=support_completed
    )


@router.message(SupportMessage.photo, F.photo)
async def support_photo(
    message: Message,
    album: list[Message],
    state: FSMContext
) -> None:
    photo_list = []
    for photo in album[:10]:
        photo_list.append(photo.photo[-1].file_id)

    await state.update_data(photo=photo_list)
    data = await state.get_data()

    photo_list = data['photo']
    if photo_list:
        media_group = MediaGroupBuilder(caption=data.get('message'))
        for photo in photo_list:
            media_group.add_photo(media=photo)
        await message.answer_media_group(media=media_group.build())
        await message.answer(text='Отправляю?', reply_markup=support_completed)
        return

    text = f"{data.get('message')}\n\n" \
           f"Отправляю?"
    await message.answer(text=text, reply_markup=support_completed)


@router.callback_query(F.data == 'support_completed')
async def support_complete(
    callback_query: CallbackQuery,
    bot: Bot,
    db: Database,
    state: FSMContext
) -> None:
    user_id = callback_query.from_user.id

    data = await state.get_data()
    await state.clear()

    text = await db.add_support_message(user_id, data)

    count_support_message = await db.get_count_support_message()

    btn = inline_builder(
        text=[
            f'Обращения - ({count_support_message})',
            'Назад'
        ],
        callback_data=[
            'get_suppoet_message',
            'back_main'
        ],
        sizes=[1]
    )

    for id in await db.get_admin_ids():
        await bot.send_message(id['user_id'], 'Новое обращение!', reply_markup=btn)

    await callback_query.message.edit_text(
        text=text,
        reply_markup=back_profile
    )