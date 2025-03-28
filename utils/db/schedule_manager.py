import json
import logging
from typing import Any, Dict, List
from datetime import date

import asyncpg
from async_lru import alru_cache

from utils.db.main import Pool


class ScheduleManager:
    def __init__(self, pool: Pool):
        self.pool = pool

    async def add_schedule(self, data: List[Dict[str, Dict[str, Any]]]) -> None:
        """
        Добавляет или обновляет расписание батчем.
        """
        query = """
        INSERT INTO schedules (group_name, date, weekday, formation, alert, start_at, subjects)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (group_name, date) 
        DO UPDATE SET
            weekday = EXCLUDED.weekday,
            formation = EXCLUDED.formation,
            alert = EXCLUDED.alert,
            start_at = EXCLUDED.start_at,
            subjects = EXCLUDED.subjects;
        """

        batch_data = []
        for schedule_data in data:
            for group_name, schedule in schedule_data.items():
                try:
                    batch_data.append((
                        group_name,
                        schedule["date"],
                        schedule["weekday"],
                        schedule["formation"],
                        schedule["alert"],
                        schedule["start_at"],
                        json.dumps(schedule["subjects"]),
                    ))
                except KeyError as e:
                    logging.error(f"Отсутствует ключ для группы {group_name}: {e}")

        if batch_data:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany(query, batch_data)

        logging.info(f"Добавлено/обновлено {len(batch_data)} записей.")

        # Очистка кэша после обновления данных
        await self.clear_cache_schedule()

    @alru_cache(maxsize=128)
    async def get_groups_name(self) -> List[asyncpg.Record]:
        """
        Возвращает список групп из расписания.
        """
        logging.info("Получение названий групп из кэша или базы данных.")
        return await self.pool.fetch(
            "SELECT group_name, MIN(id) AS min_id FROM schedules GROUP BY group_name ORDER BY min_id;"
        )

    @alru_cache(maxsize=128)
    async def get_schedule_date(self) -> List:
        """
        Получает доступные даты.
        """
        logging.info("Получение доступных дат из кэша или базы данных.")
        query = """
        SELECT DISTINCT date 
        FROM schedules 
        WHERE date >= CURRENT_DATE 
        ORDER BY date;
        """
        return await self.pool.fetch(query)

    @alru_cache(maxsize=128)
    async def get_schedule_by_group(self, group_name: str, date: date) -> Dict[str, Any]:
        """
        Получает расписание для указанной группы.
        """
        logging.info(f"Получение расписания для группы {group_name} на {date} из кэша или базы данных.")
        query = """
        SELECT * FROM schedules 
        WHERE group_name=$1 AND date=$2;
        """
        return await self.pool.fetchrow(query, group_name, date)

    @alru_cache(maxsize=128)
    async def get_schedule_alert(self, date: date) -> List:
        """
        Получает alert для указанной даты.
        """
        logging.info(f"Получение alert для {date} из кэша или базы данных.")
        query = """
        SELECT DISTINCT alert
        FROM schedules 
        WHERE date = $1
        LIMIT 1;
        """
        return await self.pool.fetchval(query, date)

    async def clear_cache_schedule(self):
        """
        Очистка кэша после обновления данных.
        """
        self.get_groups_name.cache_clear()
        self.get_schedule_date.cache_clear()
        self.get_schedule_by_group.cache_clear()
        self.get_schedule_alert.cache_clear()
        logging.info("Кэш очищен после обновления расписания.")
