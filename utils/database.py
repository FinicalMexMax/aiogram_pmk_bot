from os import getenv
from datetime import datetime
from decimal import Decimal

import asyncpg
from asyncpg import Pool


class Database:
    pool: Pool
        
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=getenv('DB_HOST'),
            database=getenv('DB_DATABASE'),
            user=getenv('DB_USER'),
            password=getenv("DB_PASSWORD")
        )


    async def create_and_check_table(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS users (
            id SMALLSERIAL PRIMARY KEY,
            user_id BIGINT,
            user_name VARCHAR,
            user_nick VARCHAR,
            role VARCHAR DEFAULT 'заказчик',
            status VARCHAR DEFAULT 'active',
            balance NUMERIC DEFAULT 0,
            datetime_reg VARCHAR
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SMALLSERIAL PRIMARY KEY,
            title VARCHAR (50),
            type_work VARCHAR (25),
            about VARCHAR (4096),
            photo VARCHAR (1000),
            file VARCHAR (1000),
            price INTEGER,
            status VARCHAR DEFAULT 'На модерации',
            customer BIGINT,
            executor BIGINT DEFAULT 0,
            datetime_create VARCHAR
        );
        CREATE TABLE IF NOT EXISTS support_message (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            message VARCHAR (4096),
            photo VARCHAR (100),
            status VARCHAR DEFAULT 'ожидание ответа',
            send_datetime VARCHAR
        );
        CREATE TABLE IF NOT EXISTS replenishment_operations (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount NUMERIC,
            tips NUMERIC DEFAULT 0,
            status VARCHAR DEFAULT 'Ожидание оплаты',
            datetime_create VARCHAR,
            datetime_payment VARCHAR DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS ratings (
            id SERIAL PRIMARY KEY,
            customer BIGINT,
            executor BIGINT,
            rating INTEGER,
            order_id INTEGER,
            datetime_create VARCHAR
        );
        """

        await self.pool.execute(query)


    async def add_user(
        self,
        user_id: int,
        user_name: str
    ) -> None:
        request = await self.pool.fetchrow('SELECT user_id FROM users WHERE user_id=$1', user_id)
        if not request:
            date = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

            query = """
            INSERT INTO users (
                user_id,
                user_name,
                user_nick,
                datetime_reg
            ) VALUES ($1, $2, $2, $3);
            """
            
            await self.pool.fetchrow(query, user_id, user_name, date)


    async def add_order(
        self,
        data: dict
    ) -> str:
        if data.get('status'):
            print(111)
            query = """
            INSERT INTO orders (
                type_work,
                title,
                about,
                photo,
                file,
                price,
                customer,
                status,
                datetime_create
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
            """
        else:
            query = """
            INSERT INTO orders (
                type_work,
                title,
                about,
                photo,
                file,
                price,
                customer,
                datetime_create
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);
            """

        try:
            date = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

            data['photo'] = ','.join(data['photo'])
            data['file'] = ','.join(data['file'])
            data['date'] = date

            await self.pool.fetch(query, *data.values())
            order_id = await self.pool.fetchval(
                'SELECT id FROM orders WHERE customer=$1 AND datetime_create=$2',
                data['customer'], date
            )

            return dict(
                text='Готово. Заказ опубликуется после модерации.',
                order_id=order_id
            )
        except Exception as e:
            print(e)
            return dict(
                    text='Произошла ошибка, попробуйте позже.',
                    order_id=None
                )
        

    async def add_support_message(
        self,
        user_id: int,
        data: dict
    ) -> str:
        date = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

        query = """
        INSERT INTO support_message (
            user_id,
            message,
            photo,
            send_datetime
        ) VALUES ($1, $2, $3, $4);
        """

        try:
            photo = ','.join(data.get('photo'))
            await self.pool.fetchrow(query, user_id, data.get('message'), photo, date)
            return 'Отправил. Ожидайте ответа.'
        except Exception as e:
            print(e)
            return 'Произошла ошибка, попробуйте позже.'
        

    async def get_data(
        self,
        user_id: int
    ) -> dict:
        return await self.pool.fetch(
            'SELECT title, type_work, about, photo, file, status, price FROM orders WHERE customer=$1', 
            user_id
        )
    

    async def get_user_info(
        self,
        user_id: int
    ) -> dict:
        return await self.pool.fetch("SELECT COUNT(id) FROM orders WHERE customer=$1 AND status!='Закрыт';", user_id) + \
               await self.pool.fetch('SELECT user_nick, role, balance, datetime_reg FROM users WHERE user_id=$1;', user_id)
    

    async def get_count_suppoer_message(
        self,
    ) -> int:
        return await self.pool.fetchval(
            "SELECT COUNT(id) FROM support_message WHERE status!='закрыт'"
        )
    

    async def edit_nick(
        self,
        user_id: int,
        nick: str
    ) -> None:
        try:
            if await self.pool.fetchrow(
                "SELECT user_nick FROM users WHERE user_nick=$1", 
                nick
            ):
                return 'Этот ник уже занят.\nВведи другой'
            
            await self.pool.fetchrow(
                'UPDATE users SET user_nick=$1 WHERE user_id=$2', 
                nick, user_id
            )
            return 'Изменил.'
        except Exception as ex:
            return 'Ошибка. Попробуй ввести другой ник.'
    

    async def update_role(
        self,
        user_id: int,
        role: str
    ) -> None:
        await self.pool.fetch(
            'UPDATE users SET role=$1 WHERE user_id=$2', 
            role, user_id
        )


    async def get_balance(
        self,
        user_id: int
    ) -> int:
        return await self.pool.fetchval(
            "SELECT balance FROM users WHERE user_id=$1", 
            user_id
        )
    

    async def get_admin_ids(
        self
    ) -> list:
        return await self.pool.fetch(
            "SELECT user_id FROM users WHERE role='админ';"
        )
    

    async def update_balance(
        self,
        user_id: int,
        pay_id: int
    ) -> int:
        value = await self.get_balance(user_id)
        amount = await self.pool.fetchval(
            "SELECT amount FROM replenishment_operations WHERE id=$1", 
            pay_id
        )
        value = amount + value

        await self.pool.fetchrow(
            "UPDATE users SET balance=$1 WHERE user_id=$2", 
            value, user_id
        )
        return value
    

    async def create_replenishment_operations(
        self,
        user_id: int,
        amount: int,
    ) -> str:
        date = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        await self.pool.fetch(
            """
            INSERT INTO replenishment_operations (
                user_id,
                amount,
                datetime_create
            ) VALUES ($1,$2,$3);
            """, 
            user_id, amount, date
        )

        return await self.pool.fetchval(
            'SELECT id FROM replenishment_operations WHERE user_id=$1 AND datetime_create=$2',
            user_id, date
        )


    async def payment_replenishment_operations(
        self,
        pay_id: int,
        total_amount: int
    ) -> None:
        date = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

        amount = await self.pool.fetchval(
            "SELECT amount FROM replenishment_operations WHERE id=$1",
            pay_id
        )
        tips = Decimal(str(total_amount // 100)) - amount

        await self.pool.fetch(
            """
            UPDATE replenishment_operations 
            SET tips=$1, status='Счет оплачен', datetime_payment=$2
            WHERE id=$3;
            """, 
            tips, date, pay_id
        )

        await self.pool.fetch(
            """
            UPDATE orders
            SET status='На модерации'
            WHERE id=$1;
            """, 
            pay_id
        )


    async def check_payment(
        self,
        order_id: int
    ) -> bool:
        if await self.pool.fetchrow(
            "SELECT id FROM orders WHERE id=$1 AND status!='Ожидание оплаты';",
            order_id
        ):
            return True
        return False