import logging
from os import getenv

import asyncpg
from asyncpg import Pool

from utils.db.user_service import UserService
from utils.db.schedule_manager import ScheduleManager
from utils.db.admin_manager import AdminManager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)


class Database(
    UserService,
    ScheduleManager,
    AdminManager
):
    def __init__(self, pool: Pool = None):
        self.pool = pool
        super().__init__(self.pool)

    async def connect(self) -> None:
        """
        Устанавливает подключение к базе данных.
        """
        self.pool = await asyncpg.create_pool(
            host=getenv('DB_HOST'),
            database=getenv('DB_DATABASE'),
            user=getenv('DB_USER'),
            password=getenv("DB_PASSWORD")
        )

        super().__init__(self.pool)

        logging.info("Подключение к базе данных установлено.")

    async def create_and_check_table(self) -> None:
        """
        Создаёт таблицы, если они не существуют.
        """
        query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            group_name VARCHAR(100),
            status VARCHAR(50) DEFAULT 'active',
            signup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS support_message (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            message VARCHAR (4096),
            photo TEXT[],
            status VARCHAR DEFAULT 'ожидание ответа',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id SERIAL PRIMARY KEY,
            group_name VARCHAR(13),
            date DATE,
            weekday TEXT,
            formation VARCHAR,
            alert VARCHAR,
            start_at VARCHAR(5),
            subjects JSONB
        );
        """
        await self.pool.execute(query)
        logging.info("Таблицы проверены/созданы.")

        index_query = """
        CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_schedules_group_date_unique ON schedules(group_name, date);
        """

        await self.pool.execute(index_query)
        logging.info("Индексы проверены/созданы.")

    async def close(self) -> None:
        """
        Закрывает пул соединений.
        """
        await self.pool.close()
        logging.info("Подключение к базе данных закрыто.")