import logging
from decimal import Decimal
from asyncpg import Pool


ORDER_STATUS_MODERATION = "На модерации"
ORDER_STATUS_WAIT_PAYMENT = "Ожидание оплаты"
ORDER_STATUS_COMPLETED = "Завершён"
PAYMENT_STATUS_PAID = "Оплачен"


class PaymentService:
    def __init__(self, pool: Pool):
        self.pool = pool

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
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        "SELECT user_id, amount FROM replenishment_operations WHERE id=$1", pay_id
                    )
                    if row is None:
                        raise ValueError(f"Пополнение {pay_id} не существует.")

                    user_id, amount = row["user_id"], row["amount"]
                    if total_amount < amount:
                        raise ValueError("Сумма платежа меньше требуемой.")

                    tips = total_amount - amount

                    await conn.execute(
                        """
                        UPDATE replenishment_operations 
                        SET tips=$1, status=$2, datetime_payment=NOW()
                        WHERE id=$3;
                        """,
                        tips, PAYMENT_STATUS_PAID, pay_id
                    )

                    await self.update_balance(user_id, amount)
                    await self.log_transaction(conn, user_id, amount, "replenishment")
        except Exception as e:
            logging.error(f"Ошибка при обработке оплаты {pay_id}: {e}")
            raise

    async def update_balance(self, user_id: int, amount: Decimal) -> None:
        """
        Обновляет баланс пользователя.
        """
        await self.pool.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2;", amount, user_id
        )

    async def reserve_funds(self, user_id: int, order_id: int, amount: Decimal) -> bool:
        """
        Резервирует средства для заказа.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                result = await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $1, reserved_balance = reserved_balance + $1
                    WHERE user_id = $2 AND balance >= $1;
                    """,
                    amount, user_id
                )
                if result == "UPDATE 0":
                    return False
                
                await conn.execute("UPDATE orders SET reserved = TRUE WHERE id = $1;", order_id)
                await self.log_transaction(conn, user_id, amount, "reserve", order_id)
                return True

    async def release_funds(self, user_id: int, order_id: int, amount: Decimal) -> None:
        """
        Освобождает зарезервированные средства при отмене заказа.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance + $1, reserved_balance = reserved_balance - $1
                    WHERE user_id = $2;
                    """,
                    amount, user_id
                )
                await conn.execute("UPDATE orders SET reserved = FALSE WHERE id = $1;", order_id)
                await self.log_transaction(conn, user_id, amount, "release", order_id)

    async def complete_payment(self, customer_id: int, executor_id: int, order_id: int, amount: Decimal) -> None:
        """
        Переводит средства исполнителю при завершении заказа.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE users
                    SET reserved_balance = reserved_balance - $1
                    WHERE user_id = $2;
                    """,
                    amount, customer_id
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + $1 WHERE user_id = $2;",
                    amount, executor_id
                )
                await conn.execute(
                    "UPDATE orders SET status = $1, reserved = FALSE, executor = $2 WHERE id = $3;",
                    ORDER_STATUS_COMPLETED, executor_id, order_id
                )
                await self.log_transaction(conn, customer_id, -amount, "payment", order_id, executor_id)
                await self.log_transaction(conn, executor_id, amount, "income", order_id, customer_id)

    async def log_transaction(self, conn, user_id: int, amount: Decimal, type_: str, order_id: int = None, related_user: int = None):
        """
        Логирование транзакций в базу данных.
        """
        await conn.execute(
            """
            INSERT INTO transactions (user_id, amount, type, order_id, related_user, datetime)
            VALUES ($1, $2, $3, $4, $5, NOW());
            """,
            user_id, amount, type_, order_id, related_user
        )
