import logging
import json

import aiohttp
import asyncio

from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from utils.database import Database


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class Parser:
    def __init__(self) -> None:
        self.url = 'https://pmkspo.ru/schedules/fulltime/'
        self._schedule_data: list[dict[str, dict[str, any]]] = []
        self.ua = UserAgent()

    async def __get_schedule(self, session: aiohttp.ClientSession, date: str) -> None:
        url = self.url + date
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
            return

        formed_elem = soup.find('div', class_='text-muted')
        formed = formed_elem.find('small').text.replace('Сформировано', '').strip() if formed_elem else None

        type_day_elem = soup.find('small', class_='text-muted')
        type_day = type_day_elem.text.split(' ')[-1].lower().strip('()') if type_day_elem else None
        print(type_day)

        alert_elem = soup.find('div', role='alert')
        alert = alert_elem.text.strip() if alert_elem else None

        if alert == 'На эту дату нет расписания занятий':
            logging.info(f"Для даты {date} отсутствует расписание.")
            return

        for card in soup.find_all('div', class_='card-body'):
            group_title = card.find('h4', class_='card-title')
            if not group_title:
                continue
            group_name = group_title.text.strip()

            start_time_elem = card.find('span', class_='badge badge-info')
            start_time = start_time_elem.text.split(' ')[-1].strip() if start_time_elem else None

            subject_elements = card.find('div', class_='card-text')
            if not subject_elements:
                continue
            subject_elements = subject_elements.find_all('strong')
            subjects = []

            for elem in subject_elements:
                subject_number = elem.text.strip()
                subject_name = elem.next_sibling.strip() if elem.next_sibling else None

                instructor_elem = elem.find_next('div', class_='col-7')
                instructor_span = instructor_elem.find('span', class_='small badge badge-pill badge-secondary') if instructor_elem else None
                instructor_name = instructor_span.text.strip() if instructor_span else None

                room_elem = elem.find_next('span', class_='badge badge-pill badge-dark')
                room_number = room_elem.text.strip() if room_elem else None

                subjects.append({
                    'subject_number': subject_number,
                    'subject_name': subject_name,
                    'teacher': instructor_name,
                    'room_number': room_number
                })

            self._schedule_data.append({
                group_name: {
                    'formed': formed,
                    'date': datetime.strptime(date, "%Y-%m-%d").date(),
                    'type_day': type_day,
                    'start_time': start_time,
                    'alert': alert,
                    'subjects': subjects
                }
            })
            logging.info(f"Расписание для группы {group_name} на дату {date} успешно получено.")

    def print_data(self) -> None:
        print(json.dumps(self._schedule_data, default=str, indent=2))

    def __get_date_numbers(self) -> list[str]:
        today = datetime.now()
        return [(today + timedelta(days=i)).date() for i in range(7)]

    async def get_schedule(self) -> None:
        async with aiohttp.ClientSession() as session:
            tasks = [self.__get_schedule(session, date) for date in self.__get_date_numbers()]
            await asyncio.gather(*tasks)

    def get_json_data(self) -> list[dict[str, dict]]:
        return self._schedule_data

    async def save_db_data(self, db: Database) -> None:
        await db.add_schedule(data=self._schedule_data)
        logging.info("Данные расписания сохранены в БД.")
