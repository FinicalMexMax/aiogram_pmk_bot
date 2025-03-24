import logging

from decimal import Decimal

from asyncpg import Pool
from async_lru import alru_cache

from typing import Optional, List


class UserService:
    def __init__(self, pool: Pool):
        self.pool = pool

    async def add_user(self, user_id: int, user_name: str, group_name: str) -> None:
        """
        Добавляет нового пользователя в базу данных, если он ещё не существует.
        """
        exists = await self.user_exists(user_id)
        if not exists:
            query = """
            INSERT INTO users (user_id, user_name, group_name)
            VALUES ($1, $2, $3);
            """
            await self.pool.execute(query, user_id, user_name, group_name)
            logging.info(f"Пользователь {user_id} добавлен.")
            await self.clear_cache(user_id)
        else:
            logging.info(f"Пользователь {user_id} уже существует.")

    @alru_cache(maxsize=128)
    async def user_exists(self, user_id: int) -> bool:
        """
        Проверяет существование пользователя в базе данных.
        """
        return await self.pool.fetchval('SELECT 1 FROM users WHERE user_id=$1', user_id) is not None

    async def update_role(self, user_id: int, new_role: str) -> bool:
        """
        Обновляет роль пользователя в базе данных.
        """
        try:
            query = "UPDATE users SET role = $1 WHERE user_id = $2"
            result = await self.pool.execute(query, new_role, user_id)

            if result == "UPDATE 1":
                logging.info(f"[{user_id}] Роль обновлена на '{new_role}'")
                await self.clear_cache(user_id)
                return True
            else:
                logging.warning(f"[{user_id}] Не удалось обновить роль: пользователь не найден")
                return False

        except Exception as e:
            logging.error(f"[{user_id}] Ошибка при обновлении роли: {e}")
            return False

    async def update_group(self, user_id: int, group: str) -> None:
        """
        Обновляет группу пользователя в базе данных.
        """
        await self.pool.execute('UPDATE users SET group_name=$1 WHERE user_id=$2', group, user_id)
        logging.info(f"Изменена группа пользователя {user_id} на {group}.")
        await self.clear_cache(user_id)

    async def update_nick(self, user_id: int, user_name: str) -> str:
        """
        Обновляет ник пользователя.
        """
        existing_nick = await self.pool.fetchval("SELECT 1 FROM users WHERE user_name=$1", user_name)
        if existing_nick:
            logging.warning(f"Ник {user_name} уже занят.")
            return 'Этот ник уже занят.\nВведи другой'

        await self.pool.execute('UPDATE users SET user_name=$1 WHERE user_id=$2', user_name, user_id)
        logging.info(f"Пользователь {user_id} изменил ник на {user_name}.")
        await self.clear_cache(user_id)
        return 'Изменил.'

    @alru_cache(maxsize=128)
    async def get_group(self, user_id: int) -> str:
        """
        Получает название группы пользователя.
        """
        logging.info("Получение названия группы пользователя.")
        return await self.pool.fetchval("SELECT group_name FROM users WHERE user_id=$1;", user_id)

    @alru_cache(maxsize=128)
    async def get_user_info(self, user_id: int) -> dict:
        """
        Получает информацию о пользователе.
        """
        query = "SELECT * FROM users WHERE user_id = $1;"
        return await self.pool.fetchrow(query, user_id)

    async def clear_cache(self, user_id: int) -> None:
        """
        Очистка кэша для конкретного пользователя.
        """
        self.get_user_info.cache_invalidate(user_id)
        self.get_group.cache_invalidate(user_id)
        self.user_exists.cache_invalidate(user_id)
        logging.info(f"Кэш для пользователя {user_id} очищен.")
