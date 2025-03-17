import logging
from decimal import Decimal
from asyncpg import Pool
from typing import Optional, List


class UserService:
    def __init__(self, pool: Pool):
        self.pool = pool

    async def add_user(self, user_id: int, user_name: str, group_name: str) -> None:
        """
        Добавляет нового пользователя в базу данных, если он ещё не существует.

        :param user_id: ID пользователя
        :param user_name: Имя пользователя
        :param group_name: Название группы пользователя
        """
        exists = await self.pool.fetchval('SELECT 1 FROM users WHERE user_id=$1', user_id)
        if not exists:
            query = """
            INSERT INTO users (user_id, user_name, group_name)
            VALUES ($1, $2, $3);
            """
            await self.pool.execute(query, user_id, user_name, group_name)
            logging.info(f"Пользователь {user_id} добавлен.")
        else:
            logging.info(f"Пользователь {user_id} уже существует.")

    async def user_exists(self, user_id: int) -> bool:
        """
        Проверяет существование пользователя в базе данных.

        :param user_id: ID пользователя
        :return: True, если пользователь существует, иначе False
        """

        return await self.pool.fetchval('SELECT 1 FROM users WHERE user_id=$1', user_id) is not None
    
    async def update_role(self, user_id: int, new_role: str) -> bool:
        """
        Обновляет роль пользователя в базе данных.

        :param user_id: ID пользователя
        :param new_role: Новая роль ("исполнитель" или "заказчик")
        :return: True, если обновление успешно, иначе False
        """
        try:
            query = "UPDATE users SET role = $1 WHERE user_id = $2"
            result = await self.pool.execute(query, new_role, user_id)

            if result == "UPDATE 1":
                logging.info(f"[{user_id}] Роль обновлена на '{new_role}'")
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

        :param user_id: ID пользователя
        :param group: Новое название группы
        """
        await self.pool.execute('UPDATE users SET group_name=$1 WHERE user_id=$2', group, user_id)
        logging.info(f"Изменена группа пользователя {user_id} на {group}.")

    async def update_nick(self, user_id: int, user_name: str) -> str:
        """
        Обновляет ник пользователя.

        :param user_id: ID пользователя
        :param nick: Новый ник пользователя
        :return: Сообщение об успехе или ошибке
        """
        existing_nick = await self.pool.fetchval("SELECT 1 FROM users WHERE user_name=$1", user_name)
        if existing_nick:
            logging.warning(f"Ник {user_name} уже занят.")
            return 'Этот ник уже занят.\nВведи другой'

        await self.pool.execute('UPDATE users SET user_name=$1 WHERE user_id=$2', user_name, user_id)
        logging.info(f"Пользователь {user_id} изменил ник на {user_name}.")
        return 'Изменил.'

    async def get_group(self, user_id: int) -> str:
        """
        Получает название группы пользователя.

        :return: Название группы
        """
        logging.info("Получение названия группы пользователя.")
        return await self.pool.fetchval(
            "SELECT group_name FROM users WHERE user_id=$1;", user_id
        )

    async def get_user_info(self, user_id: int) -> dict:
        """
        Получает доуступные даты
        """
        query = """
        SELECT * 
        FROM users 
        WHERE user_id = $1;
        """
        return await self.pool.fetchrow(query, user_id)