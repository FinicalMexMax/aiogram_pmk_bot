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

CACHE_TTL = 600

ORDER_STATUS_MODERATION = "На модерации"
ORDER_STATUS_WAIT_PAYMENT = "Ожидание оплаты"
PAYMENT_STATUS_PAID = "Оплачен"


def cache_builder(func, *args, **kwargs) -> str:
    key = f"{func.__name__}:" + ":".join(map(str, args)) 
    if kwargs:
        key += ":" + ":".join(f"{k}={v}" for k, v in kwargs.items())
    return key


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
            user_name VARCHAR(255),
            user_nick VARCHAR(100),
            group VARCHAR(100),
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
            group_name VARCHAR,
            date DATE,
            type_day VARCHAR,
            formation VARCHAR,
            alert VARCHAR,
            start_time VARCHAR,
            subjects JSONB
        );
        """
        await self.pool.execute(query)
        logging.info("Таблицы проверены/созданы.")

        index_query = """
        CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer);
        CREATE INDEX IF NOT EXISTS idx_orders_executor ON orders(executor);
        CREATE INDEX IF NOT EXISTS idx_schedules_group_date ON schedules(group_name, date);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_schedules_group_date_unique ON schedules(group_name, date);
        """

        await self.pool.execute(index_query)
        logging.info("Индексы проверены/созданы.")

    async def add_schedule(self, data: List[Dict[str, Dict[str, Any]]]) -> None:
        """
        Добавляет информацию о расписании
        """
        query = """
        INSERT INTO schedules (group_name, date, type_day, formation, alert, start_time, subjects)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (group_name, date) 
        DO UPDATE SET
            formation = EXCLUDED.formation,
            alert = EXCLUDED.alert,
            start_time = EXCLUDED.start_time,
            subjects = EXCLUDED.subjects
        WHERE schedules.formation <> EXCLUDED.formation;
        """

        values = []
        for schedule_data in data:
            for group_name, schedule in schedule_data.items():
                values.append((
                    group_name, schedule['date'], schedule['type_day'], schedule['formed'],
                    schedule['alert'], schedule['start_time'], json.dumps(schedule['subjects'])
                ))

        if values:
            await self.pool.executemany(query, values)
            logging.info(f"Обновлено/добавлено {len(values)} записей в расписании.")

    async def add_user(self, user_id: int, user_name: str, group_name: str) -> None:
        """
        Добавляет нового пользователя, если его ещё нет в БД.
        """
        exists = await self.pool.fetchval('SELECT 1 FROM users WHERE user_id=$1', user_id)
        if not exists:
            query = """
            INSERT INTO users (user_id, user_name, user_nick, group)
            VALUES ($1, $2, $2, $3);
            """
            await self.pool.execute(query, user_id, user_name, group_name)
            logging.info(f"Пользователь {user_id} добавлен.")
        else:
            logging.info(f"Пользователь {user_id} уже существует.")

    async def user_exists(self, user_id: int) -> bool:
        """
        Проверяет, существует ли пользователь.
        """
        return await self.pool.fetchval('SELECT 1 FROM users WHERE user_id=$1', user_id) is not None

    async def get_group_name(self) -> List[str]:
        """
        Возвращает список групп из расписания.
        """
        logging.info("Получение названий групп из расписания.")
        records = await self.pool.fetch(
            "SELECT DISTINCT group_name FROM schedules ORDER BY group_name;"
        )
        return [record['group_name'] for record in records]

    async def add_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Добавляет заказ в таблицу orders.
        """
        query = """
        INSERT INTO orders (type_work, title, about, photo, file, price, customer, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, COALESCE($8, 'На модерации'))
        RETURNING id;
        """
        try:
            order_id = await self.pool.fetchval(query, *data.values())
            logging.info(f"Заказ создан с id {order_id}.")
            return {'text': 'Готово. Заказ опубликуется после модерации.', 'order_id': order_id}
        except Exception as e:
            logging.error(f"Ошибка при добавлении заказа: {e}")
            return {'text': 'Произошла ошибка, попробуйте позже.', 'order_id': None}

    async def get_user_group(self, user_id: int) -> Optional[str]:
        """
        Возвращает группу пользователя.
        """
        return await self.pool.fetchval('SELECT group FROM users WHERE user_id=$1;', user_id)

    async def update_group(self, user_id: int, group: str) -> None:
        """
        Обновляет группу пользователя.
        """
        await self.pool.execute('UPDATE users SET group=$1 WHERE user_id=$2', group, user_id)
        logging.info(f"Изменена группа пользователя {user_id} на {group}.")

    async def update_nick(self, user_id: int, nick: str) -> str:
        """
        Изменяет ник пользователя.
        """
        existing_nick = await self.pool.fetchval("SELECT 1 FROM users WHERE user_nick=$1", nick)
        if existing_nick:
            logging.warning(f"Ник {nick} уже занят.")
            return 'Этот ник уже занят.\nВведи другой'

        await self.pool.execute('UPDATE users SET user_nick=$1 WHERE user_id=$2', nick, user_id)
        logging.info(f"Пользователь {user_id} изменил ник на {nick}.")
        return 'Изменил.'

    async def update_balance(self, user_id: int, amount: Decimal) -> Decimal:
        """
        Обновляет баланс пользователя.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                new_balance = await conn.fetchval(
                    "UPDATE users SET balance = balance + $1 WHERE user_id = $2 RETURNING balance",
                    amount, user_id
                )
        logging.info(f"Баланс пользователя {user_id} обновлён: {new_balance}")
        return new_balance

    async def create_replenishment_operations(self, user_id: int, amount: Decimal) -> int:
        """
        Создаёт операцию пополнения баланса.
        """
        query = """
        INSERT INTO replenishment_operations (user_id, amount, status, datetime_create)
        VALUES ($1, $2, $3, NOW()) RETURNING id;
        """
        operation_id = await self.pool.fetchval(query, user_id, amount, ORDER_STATUS_WAIT_PAYMENT)
        logging.info(f"Операция пополнения для {user_id} с id {operation_id} создана.")
        return operation_id

    async def payment_replenishment_operations(self, pay_id: int, total_amount: Decimal) -> None:
        """
        Подтверждает оплату и обновляет баланс.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                amount = await conn.fetchval(
                    "SELECT amount FROM replenishment_operations WHERE id=$1", pay_id
                )
                if amount is None:
                    logging.error(f"Пополнение {pay_id} не найдено.")
                    return

                tips = total_amount - amount
                await conn.execute(
                    """
                    UPDATE replenishment_operations 
                    SET tips=$1, status=$2, datetime_payment=NOW()
                    WHERE id=$3;
                    """,
                    tips, PAYMENT_STATUS_PAID, pay_id
                )
                
                user_id = await conn.fetchval(
                    "SELECT user_id FROM replenishment_operations WHERE id=$1", pay_id
                )
                await self.update_balance(user_id, amount)
        logging.info(f"Оплата {pay_id} подтверждена.")

    async def check_payment(self, order_id: int) -> bool:
        """
        Проверяет, оплачен ли заказ.
        """
        return await self.pool.fetchval(
            "SELECT 1 FROM orders WHERE id=$1 AND status != $2;",
            order_id, ORDER_STATUS_WAIT_PAYMENT
        ) is not None
