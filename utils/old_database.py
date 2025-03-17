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


def cache_builder(func, *args, **kwargs) -> str:
    key = f"{func.__name__}:" + ":".join(map(str, args)) 
    if kwargs:
        key += ":" + ":".join(f"{k}={v}" for k, v in kwargs.items())
    return key


class Database:
    """
    Класс для работы с базой данных с использованием asyncpg.
    """
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
            user_nick VARCHAR(100),
            groups VARCHAR(100),
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
        """

        await self.pool.execute(index_query)
        logging.info("Индексы проверены/созданы.")

    async def add_schedule(self, data: List[Dict[str, Dict[str, Any]]]) -> None:
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
        request = await self.pool.fetchrow('SELECT user_id FROM users WHERE user_id=$1', user_id)
        if not request:
            query = """
            INSERT INTO users (user_id, user_name, user_nick, groups)
            VALUES ($1, $2, $2, $3);
            """
            await self.pool.execute(query, user_id, user_name, group_name)
            logging.info(f"Пользователь {user_id} добавлен.")
        else:
            logging.info(f"Пользователь {user_id} уже существует.")

    async def check_awable_user(self, user_id: int) -> bool:
        """
        Проверяет, существует ли пользователь с данным user_id.
        """
        request = await self.pool.fetch('SELECT user_id FROM users WHERE user_id=$1', user_id)
        return bool(request)

    async def get_groups_name(self) -> List[asyncpg.Record]:
        """
        Возвращает список групп из расписания.
        """
        logging.info("Получение названий групп из расписания.")
        return await self.pool.fetch(
            "SELECT group_name, MIN(id) AS min_id FROM schedules GROUP BY group_name ORDER BY min_id;"
        )

    async def add_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Добавляет заказ в таблицу orders.
        :param data: Словарь с данными заказа.
        :return: Словарь с текстом ответа и id заказа (если успешно).
        """
        if data.get('status'):
            query = """
            INSERT INTO orders (type_work, title, about, photo, file, price, customer, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id;
            """
        else:
            query = """
            INSERT INTO orders (type_work, title, about, photo, file, price, customer)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id;
            """
        try:
            order_id = await self.pool.fetchval(query, *data.values())
            logging.info(f"Заказ создан с id {order_id}.")
            return {
                'text': 'Готово. Заказ опубликуется после модерации.',
                'order_id': order_id
            }
        except Exception as e:
            logging.error(f"Ошибка при добавлении заказа: {e}")
            return {
                'text': 'Произошла ошибка, попробуйте позже.',
                'order_id': None
            }

    async def add_support_message(self, user_id: int, data: Dict[str, Any]) -> str:
        """
        Добавляет сообщение в таблицу поддержки.
        """
        query = """
        INSERT INTO support_message (user_id, message, photo)
        VALUES ($1, $2, $3);
        """
        try:
            await self.pool.execute(query, user_id, data.get('message'), data.get('photo'))
            logging.info(f"Сообщение поддержки от пользователя {user_id} добавлено.")
            return 'Отправил. Ожидайте ответа.'
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения поддержки: {e}")
            return 'Произошла ошибка, попробуйте позже.'

    async def get_user_group(self, user_id: int) -> Optional[str]:
        """
        Возвращает группу, к которой принадлежит пользователь.
        """
        group = await self.pool.fetchval('SELECT groups FROM users WHERE user_id=$1;', user_id)
        logging.info(f"Получена группа для пользователя {user_id}: {group}")
        return group

    @cached(ttl=CACHE_TTL, cache=SimpleMemoryCache, serializer=PickleSerializer(), key_builder=cache_builder)
    async def get_schedule_data(self, user_id: int, date: str, group_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Возвращает расписание для указанной группы и даты.
        Если group_name не указан, определяется по user_id.
        """
        if not group_name:
            group_name = await self.get_user_group(user_id)
        logging.info(f"Получение расписания для группы {group_name} на дату {date}. Кеширование.")
        query = "SELECT * FROM schedules WHERE group_name=$1 AND date=$2;"
        result = await self.pool.fetchrow(query, group_name, date)
        if result:
            logging.info(f"Данные получены из базы данных: {dict(result)}")
        else:
            logging.info("Данные не найдены.")
        return dict(result) if result else {}


    @cached(ttl=CACHE_TTL, cache=SimpleMemoryCache, serializer=PickleSerializer(), key_builder=cache_builder)
    async def get_order_data(self, user_id: int) -> Dict[str, Any]:
        """
        Возвращает данные заказов для пользователя.
        """
        logging.info(f"Получение данных заказа для пользователя {user_id}.")
        result = await self.pool.fetch(
            "SELECT title, type_work, about, photo, file, status, price FROM orders WHERE customer=$1", 
            user_id
        )
        
        return [dict(record) for record in result] if result else []

    async def get_user_info(self, user_id: int) -> Dict[str, Any]:
        """
        Возвращает информацию о пользователе.
        """
        logging.info(f"Получение информации пользователя {user_id}.")
        result = await self.pool.fetchrow("""
        SELECT 
            u.user_nick,
            u.groups,
            u.role,
            u.balance,
            u.datetime_reg,
            COUNT(o.id) AS orders_count
        FROM 
            users u
        LEFT JOIN 
            orders o ON u.user_id = o.customer AND o.status != 'закрыт'
        WHERE 
            u.user_id = $1
        GROUP BY
            u.user_id, u.user_nick, u.groups, u.role, u.balance, u.datetime_reg;
        """, user_id)
        return dict(result) if result else {}

    async def get_count_support_message(self) -> int:
        """
        Возвращает количество незакрытых сообщений поддержки.
        """
        count = await self.pool.fetchval(
            "SELECT COUNT(id) FROM support_message WHERE status!='закрыт'"
        )
        logging.info(f"Количество незакрытых сообщений поддержки: {count}")
        return count

    @cached(ttl=CACHE_TTL, cache=SimpleMemoryCache, serializer=PickleSerializer(), key_builder=cache_builder)
    async def get_date_list(self) -> List[datetime]:
        """
        Возвращает список уникальных дат из расписания.
        """
        results = await self.pool.fetch('SELECT DISTINCT date FROM schedules ORDER BY date ASC')
        return [record['date'] for record in results]

    async def update_group(self, user_id: int, group: str) -> None:
        """
        Обновляет группу пользователя и инвалидирует кэш для get_user_info.
        """
        await self.pool.execute('UPDATE users SET groups=$1 WHERE user_id=$2', group, user_id)
        logging.info(f"Изменена группа пользователя {user_id} на {group}.")

    async def update_nick(self, user_id: int, nick: str) -> str:
        """
        Изменяет ник пользователя, если он не занят, и инвалидирует кэш профиля.
        """
        try:
            if await self.pool.fetchval("SELECT user_nick FROM users WHERE user_nick=$1", nick):
                logging.warning(f"Попытка изменить ник на уже занятый: {nick}")
                return 'Этот ник уже занят.\nВведи другой'
            
            await self.pool.execute('UPDATE users SET user_nick=$1 WHERE user_id=$2', nick, user_id)
            logging.info(f"Пользователь {user_id} изменил ник на {nick}.")
            
            return 'Изменил.'
        except Exception as ex:
            logging.error(f"Ошибка при изменении ника для пользователя {user_id}: {ex}")
            return 'Ошибка. Попробуй ввести другой ник.'

    async def update_role(self, user_id: int, role: str) -> None:
        """
        Обновляет роль пользователя и инвалидирует кэш профиля (get_user_info).
        """
        await self.pool.execute('UPDATE users SET role=$1 WHERE user_id=$2', role, user_id)
        logging.info(f"Пользователь {user_id} получил роль {role}.")

    async def get_balance(self, user_id: int) -> Decimal:
        """
        Возвращает баланс пользователя.
        """
        balance = await self.pool.fetchval("SELECT balance FROM users WHERE user_id=$1", user_id)
        logging.info(f"Баланс пользователя {user_id}: {balance}")
        return balance

    @cached(ttl=CACHE_TTL, cache=SimpleMemoryCache, serializer=PickleSerializer(), key_builder=cache_builder)
    async def get_admin_ids(self) -> List[int]:
        """
        Возвращает список id администраторов.
        """
        admin_ids = await self.pool.fetch("SELECT user_id FROM users WHERE role='admin';")
        logging.info("Получены id администраторов.")
        return [record['user_id'] for record in admin_ids]

    async def update_balance(self, user_id: int, pay_id: int) -> Decimal:
        """
        Обновляет баланс пользователя после платежа.
        """
        current_balance = await self.get_balance(user_id)
        amount = await self.pool.fetchval("SELECT amount FROM replenishment_operations WHERE id=$1", pay_id)
        new_balance = current_balance + amount
        await self.pool.execute("UPDATE users SET balance=$1 WHERE user_id=$2", new_balance, user_id)
        logging.info(f"Обновлён баланс пользователя {user_id}: {new_balance}")
        return new_balance

    async def create_replenishment_operations(self, user_id: int, amount: int) -> int:
        """
        Создаёт операцию пополнения баланса.
        :return: id операции.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                operation_id = await conn.fetchval(
                    """
                    INSERT INTO replenishment_operations (user_id, amount, datetime_create)
                    VALUES ($1, $2, $3)
                    RETURNING id;
                    """, 
                    user_id, amount, datetime.now()
                )

        logging.info(f"Создана операция пополнения для пользователя {user_id} с id {operation_id}.")
        return operation_id

    async def payment_replenishment_operations(self, pay_id: int, total_amount: int) -> None:
        """
        Обновляет статус операции пополнения, устанавливая статус "Оплачен".
        """
        date = datetime.now()
        amount = await self.pool.fetchval("SELECT amount FROM replenishment_operations WHERE id=$1", pay_id)
        tips = Decimal(str(total_amount // 100)) - amount

        await self.pool.execute(
            """
            UPDATE replenishment_operations 
            SET tips=$1, status='Оплачен', datetime_payment=$2
            WHERE id=$3;
            """, 
            tips, date, pay_id
        )

        await self.pool.execute(
            """
            UPDATE orders
            SET status='На модерации'
            WHERE id=$1;
            """, 
            pay_id
        )
        logging.info(f"Операция пополнения {pay_id} обновлена (статус: Оплачен).")

    async def check_payment(self, order_id: int) -> bool:
        """
        Проверяет, изменился ли статус заказа после платежа.
        """
        exists = await self.pool.fetchrow(
            "SELECT id FROM orders WHERE id=$1 AND status!='Ожидание оплаты';",
            order_id
        )
        logging.info(f"Проверка оплаты заказа {order_id}: {'найден' if exists else 'не найден'}.")
        return bool(exists)
