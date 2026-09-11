import sqlite3
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "reminders.db"

STATUSES = (
    "Ожидает",
    "Готово",
    "Просрочено",
    "Отменено",
)


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Создание таблицы при первом запуске."""
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    remind_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Ожидает',
                    notified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def add_reminder(self, title, description, remind_at):
        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reminders
                (
                    title,
                    description,
                    remind_at,
                    status,
                    notified,
                    created_at
                )
                VALUES (?, ?, ?, 'Ожидает', 0, ?)
                """,
                (
                    title,
                    description,
                    remind_at,
                    created_at,
                ),
            )

            conn.commit()

            return cursor.lastrowid

    def update_reminder(
        self,
        reminder_id,
        title,
        description,
        remind_at,
    ):
        """
        Изменяет напоминание.

        После изменения времени уведомление считается
        не показанным и напоминание возвращается в статус
        'Ожидает'.
        """

        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET
                    title = ?,
                    description = ?,
                    remind_at = ?,
                    status = 'Ожидает',
                    notified = 0
                WHERE id = ?
                """,
                (
                    title,
                    description,
                    remind_at,
                    reminder_id,
                ),
            )

            conn.commit()

    def postpone_reminder(
        self,
        reminder_id,
        minutes,
    ):
        """
        Переносит напоминание на указанное количество минут
        от текущего момента.
        """

        new_time = datetime.now()

        from datetime import timedelta

        new_time += timedelta(
            minutes=minutes
        )

        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET
                    remind_at = ?,
                    status = 'Ожидает',
                    notified = 0
                WHERE id = ?
                """,
                (
                    new_time.isoformat(
                        timespec="seconds"
                    ),
                    reminder_id,
                ),
            )

            conn.commit()

        return new_time

    def delete_reminder(self, reminder_id):
        with self.get_connection() as conn:
            conn.execute(
                """
                DELETE FROM reminders
                WHERE id = ?
                """,
                (reminder_id,),
            )

            conn.commit()

    def set_status(self, reminder_id, status):
        if status not in STATUSES:
            raise ValueError(
                f"Недопустимый статус: {status}"
            )

        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET status = ?
                WHERE id = ?
                """,
                (
                    status,
                    reminder_id,
                ),
            )

            conn.commit()

    def mark_notified(self, reminder_id):
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET notified = 1
                WHERE id = ?
                """,
                (reminder_id,),
            )

            conn.commit()

    def get_reminder(self, reminder_id):
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT *
                FROM reminders
                WHERE id = ?
                """,
                (reminder_id,),
            )

            return cursor.fetchone()

    def get_all(self, status=None):
        with self.get_connection() as conn:

            if status and status != "Все":
                cursor = conn.execute(
                    """
                    SELECT *
                    FROM reminders
                    WHERE status = ?
                    ORDER BY remind_at ASC
                    """,
                    (status,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT *
                    FROM reminders
                    ORDER BY remind_at ASC
                    """
                )

            return cursor.fetchall()

    def update_overdue(self):
        """
        Переводит ожидающие напоминания,
        время которых уже прошло, в 'Просрочено'.
        """

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE reminders
                SET status = 'Просрочено'
                WHERE status = 'Ожидает'
                  AND remind_at < ?
                """,
                (now,),
            )

            conn.commit()

            return cursor.rowcount

    def get_due_reminders(self):
        """
        Возвращает напоминания, время которых наступило,
        но уведомление ещё не показывалось.
        """

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT *
                FROM reminders
                WHERE status = 'Ожидает'
                  AND remind_at <= ?
                  AND notified = 0
                ORDER BY remind_at ASC
                """,
                (now,),
            )

            return cursor.fetchall()