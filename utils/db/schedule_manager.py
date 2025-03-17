import json
import logging
from typing import Any, Dict, List

from datetime import date

import asyncpg 

from utils.db.main import Pool


class ScheduleManager:
    def __init__(self, pool: Pool):
        self.pool = pool

    async def add_schedule(self, data: List[Dict[str, Dict[str, Any]]]) -> None:
        """
        Добавляет или обновляет расписание батчем.
        """
        query = """
        INSERT INTO schedules (group_name, date, weekday, formation, alert, start_time, subjects)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (group_name, date) 
        DO UPDATE SET
            weekday = EXCLUDED.weekday,
            formation = EXCLUDED.formation,
            alert = EXCLUDED.alert,
            start_time = EXCLUDED.start_time,
            subjects = EXCLUDED.subjects;
        """

        batch_data = []
        for schedule_data in data:
            for group_name, schedule in schedule_data.items():
                try:
                    batch_data.append((
                        group_name, 
                        schedule['date'], 
                        schedule['weekday'], 
                        schedule['formed'],
                        schedule['alert'], 
                        schedule['start_time'], 
                        json.dumps(schedule['subjects'])
                    ))
                except KeyError as e:
                    logging.error(f"Отсутствует ключ для группы {group_name}: {e}")

        if batch_data:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany(query, batch_data)

        logging.info(f"Добавлено/обновлено {len(batch_data)} записей.")

    async def get_groups_name(self) -> List[asyncpg.Record]:
        """
        Возвращает список групп из расписания.
        """
        logging.info("Получение названий групп из расписания.")
        return await self.pool.fetch(
            "SELECT group_name, MIN(id) AS min_id FROM schedules GROUP BY group_name ORDER BY min_id;"
        )

    
    async def get_schedule_date(self) -> List:
        """
        Получает доуступные даты
        """
        query = """
        SELECT DISTINCT date 
        FROM schedules 
        WHERE date >= CURRENT_DATE 
        ORDER BY date;
        """
        return await self.pool.fetch(query)

    async def get_schedule_by_group(self, group_name: str, date: date) -> Dict[str, Any]:
        """
        Получает расписание для указанной группы
        """
        query = """
        SELECT * FROM schedules 
        WHERE group_name=$1 AND date=$2;
        """
        
        return await self.pool.fetchrow(query, group_name, date)
    

    async def get_schedule_alert(self, date: date) -> List:
        """
        Получает доуступные даты
        """
        query = """
        SELECT DISTINCT alert
        FROM schedules 
        WHERE date = $1
        LIMIT 1;
        """
        return await self.pool.fetchval(query, date)