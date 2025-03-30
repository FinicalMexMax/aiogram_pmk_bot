import json

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta

from typing import Any, Dict, List

from utils.db.main import Database

from keyboards.builders import inline_builder


router = Router()


def get_date():
    date = datetime.now()

    if date.strftime("%A") == 'Воскресенье':
        date = date + timedelta(days=1)

    return date.date()


async def send_schedule_data(
    callback_query: CallbackQuery,
    schedule_data: Dict[str, Any]
):
    if not schedule_data:
        await callback_query.answer('Нету расписания ;(')
        return

    pair_data = ''
    for pair in json.loads(schedule_data['subjects']):
        pair_data += f"{pair['subject_number']}. {pair['subject_name']} - {pair['room_number']}\n" \
                     f"Преподаватель: {pair['teacher']}\n\n"

    text = f'Расписание на {schedule_data["date"]}.\n\n' \
           f'Группа - {schedule_data["group_name"]}\n' \
           f'Начало в {schedule_data["start_at"]}\n\n' \
           f'{pair_data}'
    
    buttons = [
        ('Другая дата', f'schedule_edit_date|{schedule_data["date"]}'),
        ('Назад', 'back_main')
    ]

    if schedule_data["alert"]:
        buttons.insert(0, ('Доп. информация', f'schedule_alert|{schedule_data["date"]}'))

    pattern = dict(
        text=text,
        reply_markup=inline_builder(
            text=[b[0] for b in buttons],
            callback_data=[b[1] for b in buttons],
            sizes=1
        )
    )

    await callback_query.message.edit_text(**pattern)


@router.callback_query(F.data.startswith('schedule_alert'))
async def schedule_edit_date(
    callback_query: CallbackQuery,
    db: Database
):
    str_date = callback_query.data.split('|')[-1]
    date = datetime.strptime(str_date, '%Y-%m-%d').date()

    alert = await db.get_schedule_alert(date)
    await callback_query.message.edit_text(
        text=alert, 
        reply_markup=inline_builder(
            text='Назад', 
            callback_data=f'schedules|{str_date}'
        )
    )


@router.callback_query(F.data.startswith('schedule_edit_date'))
async def schedule_edit_date(
    callback_query: CallbackQuery,
    db: Database
):
    date_list = await db.get_schedule_date()

    date = callback_query.data.split('|')[-1]

    buttons = [
        (
            f"{date['date'].strftime('%Y-%m-%d')} ({date['date'].strftime('%A')})", 
            f'schedules|{date["date"].strftime("%Y-%m-%d")}'
        ) 
        for date in date_list
    ]
    buttons.append(('Назад', f'schedules|{date}'))

    await callback_query.message.edit_reply_markup(
        reply_markup=inline_builder(
            text=[b[0] for b in buttons],
            callback_data=[b[1] for b in buttons],
            sizes=1
        )
    )


@router.callback_query(F.data.startswith('schedules'))
async def get_schedules(
    callback_query: CallbackQuery, 
    db: Database
):
    user_id = callback_query.from_user.id
    
    date = callback_query.data.split('|')[-1] if '|' in callback_query.data else get_date()

    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d').date()

    group_name = await db.get_group(user_id)
    schedule_data = await db.get_schedule_by_group(group_name, date)
    await send_schedule_data(
        callback_query=callback_query,
        schedule_data=schedule_data
    )