import locale
import logging
import json

import aiohttp
import asyncio

from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from utils.db.main import Database


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8")
    ]
)

locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')


class Parser:
    def __init__(self) -> None:
        self.url = 'https://pmkspo.ru/schedules/fulltime/'
        self._schedule_data: list[dict[str, dict[str, any]]] = []
        self.ua = UserAgent()

    def extract_text_from_soup(self, soup_elem, default=None):
        """Общий метод для извлечения текста из элемента BeautifulSoup"""
        return soup_elem.text.strip() if soup_elem else default

    def parse_schedule_card(self, card):
        group_name = card.find('h4', class_='card-title').text.strip()
        start_at = card.find('span', class_='badge badge-info')
        start_at = start_at.text.split(' ')[-1].strip() if start_at else None

        subjects = []

        # каждая пара — это div.col-12 + badge-secondary (преподаватель) и badge-dark (аудитория)
        col_blocks = card.find_all('div', class_='col-12')
        teachers = card.find_all('span', class_='small badge badge-pill badge-secondary')
        rooms = card.find_all('span', class_='badge badge-pill badge-dark')

        for i, col in enumerate(col_blocks):
            # номер пары
            subject_number_tag = col.find('strong')
            subject_number = subject_number_tag.text.strip() if subject_number_tag else None

            # название предмета — оставшийся текст после strong
            subject_name = subject_number_tag.next_sibling.strip() if subject_number_tag and subject_number_tag.next_sibling else None

            # преподаватель — по порядку
            instructor_name = teachers[i].text.strip() if i < len(teachers) else None

            # аудитория — по порядку
            room_number = rooms[i].text.strip() if i < len(rooms) else None

            subjects.append({
                'subject_number': subject_number,
                'subject_name': subject_name,
                'teacher': instructor_name,
                'room_number': room_number
            })

        return group_name, start_at, subjects



    def __get_date_numbers(self) -> list[str]:
        """Возвращает список дат на неделю от текущего дня"""
        today = datetime.now()
        return [(today + timedelta(days=i)).date() for i in range(7)]

    async def __get_schedule(self, session: aiohttp.ClientSession, date: str) -> None:
        """Получение и парсинг расписания для указанной даты"""
        url = self.url + date.strftime('%Y-%m-%d')
        headers = {'User-Agent': self.ua.random}
        
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                text = await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Ошибка запроса для даты {date}: {e}")
            return

        soup = BeautifulSoup(text, 'lxml')

        if "На эту дату нет расписания занятий." in soup.text:
            logging.info(f"Для даты {date} отсутствует расписание.")
            return

        formation_elem = soup.find('div', class_='text-muted')
        formation = self.extract_text_from_soup(formation_elem.find('small') if formation_elem else None, None)

        weekday = date.strftime('%A')

        alert_elem = soup.find('div', role='alert')
        alert = self.extract_text_from_soup(alert_elem, None)

        if alert == 'На эту дату нет расписания занятий':
            logging.info(f"Для даты {date} отсутствует расписание.")
            return

        for card in soup.find_all('div', class_='card-body'):
            group_name, start_at, subjects = self.parse_schedule_card(card)
            self._schedule_data.append({
                group_name: {
                    'formation': formation,
                    'date': date,
                    'weekday': weekday,
                    'start_at': start_at,
                    'alert': alert,
                    'subjects': subjects
                }
            })
            logging.info(f"Расписание для группы {group_name} на дату {date} успешно получено.")

    async def get_schedule(self) -> None:
        """Получение расписания для недели"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.__get_schedule(session, date) for date in self.__get_date_numbers()]
            await asyncio.gather(*tasks)

    def print_data(self) -> None:
        """Вывод данных расписания в формате JSON"""
        print(json.dumps(self._schedule_data, default=str, indent=4))

    def get_json_data(self) -> list[dict[str, dict]]:
        """Возвращает данные расписания в формате списка"""
        return self._schedule_data

    async def save_db_data(self, db: Database) -> None:
        """Сохраняет расписание в базу данных"""
        if self._schedule_data:
            await db.add_schedule(data=self._schedule_data)
            logging.info(f"Данные расписания сохранены в БД, количество записей: {len(self._schedule_data)}.")
            self._schedule_data.clear()