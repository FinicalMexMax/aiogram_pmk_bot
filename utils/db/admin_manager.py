import json
import logging
from typing import Any, Dict, List


class AdminManager:
    def __init__(self, pool):
        self.pool = pool

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
        
    async def get_count_support_message(self) -> int:
        """
        Возвращает количество незакрытых сообщений поддержки.
        """
        count = await self.pool.fetchval(
            "SELECT COUNT(id) FROM support_message WHERE status!='закрыт'"
        )
        logging.info(f"Количество незакрытых сообщений поддержки: {count}")
        return count