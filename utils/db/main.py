import json
import logging
from datetime import datetime
from decimal import Decimal
from os import getenv
from typing import Any, Dict, List, Optional

import asyncpg
from asyncpg import Pool

from utils.db.user_service import UserService
from utils.db.payment_service import PaymentService
from utils.db.schedule_manager import ScheduleManager
from utils.db.order_manager import OrderManager
from utils.db.admin_manager import AdminManager

from aiocache import cached, SimpleMemoryCache
from aiocache.serializers import PickleSerializer


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
    PaymentService,
    ScheduleManager,
    OrderManager,
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
            username VARCHAR(100),
            group_name VARCHAR(100),
            role VARCHAR(50) DEFAULT 'заказчик',
            status VARCHAR(50) DEFAULT 'active',
            balance NUMERIC(10, 2) DEFAULT 0,
            signup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            title VARCHAR(50),
            work_type VARCHAR(25),
            about TEXT DEFAULT NULL,
            photo TEXT[],
            file TEXT[],
            price NUMERIC(10, 2),
            status VARCHAR(50) DEFAULT 'На модерации',
            customer BIGINT,
            executor BIGINT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer) REFERENCES users(user_id),
            FOREIGN KEY (executor) REFERENCES users(user_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS support_message (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            message VARCHAR (4096),
            photo TEXT[],
            status VARCHAR DEFAULT 'ожидание ответа',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS replenishment_operations (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount NUMERIC(10, 2),
            tips NUMERIC(10, 2) DEFAULT 0,
            status VARCHAR DEFAULT 'Ожидание оплаты',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS ratings (
            id SERIAL PRIMARY KEY,
            customer BIGINT,
            executor BIGINT,
            rating INTEGER,
            order_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount NUMERIC(10, 2),
            type VARCHAR(50),
            order_id INTEGER,
            related_user BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
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
        CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer);
        CREATE INDEX IF NOT EXISTS idx_orders_executor ON orders(executor);
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