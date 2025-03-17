import json
import logging
from typing import Any, Dict, List

from utils.db.main import Pool


class ScheduleManager:
    def __init__(self, pool: Pool):
        self.pool = pool

    async def add_schedule(self, data: List[Dict[str, Dict[str, Any]]]) -> None:
        """
        Добавляет или обновляет информацию о расписании.
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
            subjects = EXCLUDED.subjects
        WHERE (schedules.weekday, schedules.formation, schedules.alert, 
            schedules.start_time, schedules.subjects) 
            IS DISTINCT FROM (EXCLUDED.weekday, EXCLUDED.formation, 
                                EXCLUDED.alert, EXCLUDED.start_time, 
                                EXCLUDED.subjects);
        """

        for schedule_data in data:
            for group_name, schedule in schedule_data.items():
                try:
                    subjects = schedule['subjects']
                    subjects = json.dumps(subjects)
                except KeyError as e:
                    logging.error(f"Отсутствует ключ 'subjects' для группы {group_name}: {e}")
                    continue

                try:
                    await self.pool.execute(query, 
                        group_name, schedule['date'], schedule['weekday'], schedule['formed'],
                        schedule['alert'], schedule['start_time'], subjects
                    )
                    logging.info(f"Запись для группы {group_name} на {schedule['date']} успешно добавлена/обновлена.")
                except Exception as e:
                    logging.error(f"Ошибка при добавлении/обновлении расписания для группы {group_name}: {e}")

    async def get_group_names(self) -> List[str]:
        """
        Возвращает список уникальных групп из расписания.
        """
        records = await self.pool.fetch("SELECT DISTINCT group_name FROM schedules ORDER BY group_name;")
        groups = [record['group_name'] for record in records]
        logging.info(f"Получено {len(groups)} уникальных групп.")
        return groups

    async def get_schedule_by_group(self, group_name: str) -> List[Dict[str, Any]]:
        """
        Получает расписание для указанной группы.
        """
        query = """
        SELECT date, weekday, formation, alert, start_time, subjects 
        FROM schedules WHERE group_name = $1 ORDER BY date::DATE;
        """
        records = await self.pool.fetch(query, group_name)
        return [dict(record) for record in records]
