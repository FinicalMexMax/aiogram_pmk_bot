import json
import logging
from datetime import datetime
from decimal import Decimal
from os import getenv
from typing import Any, Dict, List, Optional

import asyncpg
from asyncpg import Pool

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


class Database:
    pool: Pool

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
        logging.info("Подключение к базе данных установлено.")

    async def create_and_check_table(self) -> None:
        """
        Создаёт таблицы, если они не существуют.
        """
        query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            user_name VARCHAR(100),
            group_name VARCHAR(100),
            role VARCHAR(50) DEFAULT 'заказчик',
            status VARCHAR(50) DEFAULT 'active',
            balance NUMERIC(10, 2) DEFAULT 0,
            datetime_reg TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            title VARCHAR(50),
            type_work VARCHAR(25),
            about TEXT DEFAULT NULL,
            photo TEXT[],
            file TEXT[],
            price NUMERIC(10, 2),
            status VARCHAR(50) DEFAULT 'На модерации',
            customer BIGINT,
            executor BIGINT DEFAULT NULL,
            datetime_create TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer) REFERENCES users(user_id),
            FOREIGN KEY (executor) REFERENCES users(user_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS support_message (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            message VARCHAR (4096),
            photo TEXT[],
            status VARCHAR DEFAULT 'ожидание ответа',
            send_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS replenishment_operations (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount NUMERIC(10, 2),
            tips NUMERIC(10, 2) DEFAULT 0,
            status VARCHAR DEFAULT 'Ожидание оплаты',
            datetime_create TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            datetime_payment TIMESTAMP DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS ratings (
            id SERIAL PRIMARY KEY,
            customer BIGINT,
            executor BIGINT,
            rating INTEGER,
            order_id INTEGER,
            datetime_create TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id SERIAL PRIMARY KEY,
            group_name VARCHAR(12),
            date DATE,
            weekday TEXT,
            formation VARCHAR,
            alert VARCHAR,
            start_time VARCHAR(5),
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