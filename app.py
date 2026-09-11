import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from datetime import datetime

from database import Database, STATUSES


# Пытаемся использовать нативные уведомления Windows.
try:
    from winotify import Notification, audio

    WINOTIFY_AVAILABLE = True
except ImportError:
    WINOTIFY_AVAILABLE = False


class ReminderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Напоминания")
        self.root.geometry("1000x600")
        self.root.minsize(850, 500)

        self.db = Database()

        self.stop_event = threading.Event()

        self.setup_style()
        self.create_widgets()

        # Первоначальная загрузка.
        self.db.update_overdue()
        self.refresh_list()

        # Запускаем фоновый мониторинг.
        self.monitor_thread = threading.Thread(
            target=self.notification_loop,
            daemon=True,
        )
        self.monitor_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------
    # GUI
    # ------------------------------------------------------------------

    def setup_style(self):
        style = ttk.Style()

        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        style.configure(
            "Treeview",
            rowheight=30,
            font=("Segoe UI", 10),
        )

        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
        )

        style.configure(
            "Title.TLabel",
            font=("Segoe UI", 18, "bold"),
        )

    def create_widgets(self):
        # --------------------------------------------------------------
        # Верхняя панель
        # --------------------------------------------------------------

        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill="x")

        title = ttk.Label(
            top_frame,
            text="Напоминания",
            style="Title.TLabel",
        )
        title.pack(side="left")

        ttk.Button(
            top_frame,
            text="Добавить",
            command=self.add_dialog,
        ).pack(side="right", padx=5)

        ttk.Button(
            top_frame,
            text="Удалить",
            command=self.delete_selected,
        ).pack(side="right", padx=5)

        # --------------------------------------------------------------
        # Фильтр
        # --------------------------------------------------------------

        filter_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        filter_frame.pack(fill="x")

        ttk.Label(
            filter_frame,
            text="Фильтр по статусу:",
        ).pack(side="left", padx=(0, 5))

        self.filter_var = tk.StringVar(value="Все")

        self.filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_var,
            values=("Все", *STATUSES),
            state="readonly",
            width=18,
        )
        self.filter_combo.pack(side="left")
        self.filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self.refresh_list(),
        )

        ttk.Button(
            filter_frame,
            text="Обновить",
            command=self.refresh_list,
        ).pack(side="left", padx=10)

        # --------------------------------------------------------------
        # Таблица
        # --------------------------------------------------------------

        table_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        table_frame.pack(fill="both", expand=True)

        columns = (
            "id",
            "title",
            "description",
            "remind_at",
            "status",
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self.tree.heading("id", text="ID")
        self.tree.heading("title", text="Заголовок")
        self.tree.heading("description", text="Описание")
        self.tree.heading("remind_at", text="Дата и время")
        self.tree.heading("status", text="Статус")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("title", width=200)
        self.tree.column("description", width=350)
        self.tree.column("remind_at", width=160)
        self.tree.column("status", width=130, anchor="center")

        scrollbar_y = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview,
        )

        scrollbar_x = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.bind(
            "<Double-1>",
            self.on_double_click,
        )

        # --------------------------------------------------------------
        # Нижняя панель
        # --------------------------------------------------------------

        bottom_frame = ttk.Frame(
            self.root,
            padding=(10, 0, 10, 10),
        )
        bottom_frame.pack(fill="x")

        ttk.Button(
            bottom_frame,
            text="✓ Готово",
            command=lambda: self.change_status("Готово"),
        ).pack(side="left", padx=3)

        ttk.Button(
            bottom_frame,
            text="✕ Отменено",
            command=lambda: self.change_status("Отменено"),
        ).pack(side="left", padx=3)

        ttk.Button(
            bottom_frame,
            text="↻ Ожидает",
            command=lambda: self.change_status("Ожидает"),
        ).pack(side="left", padx=3)

        self.status_label = ttk.Label(
            bottom_frame,
            text="",
        )
        self.status_label.pack(side="right")

    # ------------------------------------------------------------------
    # Работа со списком
    # ------------------------------------------------------------------

    def refresh_list(self):
        self.db.update_overdue()

        for item in self.tree.get_children():
            self.tree.delete(item)

        status = self.filter_var.get()

        reminders = self.db.get_all(status)

        for reminder in reminders:
            remind_at = self.format_datetime(reminder["remind_at"])

            self.tree.insert(
                "",
                "end",
                iid=str(reminder["id"]),
                values=(
                    reminder["id"],
                    reminder["title"],
                    reminder["description"],
                    remind_at,
                    reminder["status"],
                ),
            )

        self.status_label.config(
            text=f"Напоминаний: {len(reminders)}"
        )

    @staticmethod
    def format_datetime(value):
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return value

    def get_selected_id(self):
        selection = self.tree.selection()

        if not selection:
            messagebox.showinfo(
                "Выбор",
                "Сначала выберите напоминание.",
            )
            return None

        return int(selection[0])

    def delete_selected(self):
        reminder_id = self.get_selected_id()

        if reminder_id is None:
            return

        answer = messagebox.askyesno(
            "Удаление",
            "Удалить выбранное напоминание?",
        )

        if answer:
            self.db.delete_reminder(reminder_id)
            self.refresh_list()

    def change_status(self, status):
        reminder_id = self.get_selected_id()

        if reminder_id is None:
            return

        self.db.set_status(
            reminder_id,
            status,
        )

        self.refresh_list()

    def on_double_click(self, event):
        reminder_id = self.get_selected_id()

        if reminder_id is not None:
            self.show_reminder(reminder_id)

    # ------------------------------------------------------------------
    # Добавление
    # ------------------------------------------------------------------

    def add_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новое напоминание")
        dialog.geometry("520x430")
        dialog.resizable(False, False)

        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(
            dialog,
            padding=20,
        )
        frame.pack(fill="both", expand=True)

        # Заголовок
        ttk.Label(
            frame,
            text="Заголовок:",
        ).pack(anchor="w")

        title_var = tk.StringVar()

        title_entry = ttk.Entry(
            frame,
            textvariable=title_var,
        )
        title_entry.pack(
            fill="x",
            pady=(5, 15),
        )

        # Описание
        ttk.Label(
            frame,
            text="Описание:",
        ).pack(anchor="w")

        description_text = tk.Text(
            frame,
            height=7,
            font=("Segoe UI", 10),
        )
        description_text.pack(
            fill="x",
            pady=(5, 15),
        )

        # Дата
        ttk.Label(
            frame,
            text="Дата (ДД.ММ.ГГГГ):",
        ).pack(anchor="w")

        date_var = tk.StringVar(
            value=datetime.now().strftime("%d.%m.%Y")
        )

        ttk.Entry(
            frame,
            textvariable=date_var,
        ).pack(
            fill="x",
            pady=(5, 10),
        )

        # Время
        ttk.Label(
            frame,
            text="Время (ЧЧ:ММ):",
        ).pack(anchor="w")

        time_var = tk.StringVar(
            value=(datetime.now().replace(
                second=0,
                microsecond=0,
            )).strftime("%H:%M")
        )

        ttk.Entry(
            frame,
            textvariable=time_var,
        ).pack(
            fill="x",
            pady=(5, 15),
        )

        def save():
            title = title_var.get().strip()
            description = description_text.get(
                "1.0",
                "end",
            ).strip()

            if not title:
                messagebox.showerror(
                    "Ошибка",
                    "Введите заголовок.",
                    parent=dialog,
                )
                return

            try:
                dt = datetime.strptime(
                    f"{date_var.get().strip()} "
                    f"{time_var.get().strip()}",
                    "%d.%m.%Y %H:%M",
                )
            except ValueError:
                messagebox.showerror(
                    "Ошибка",
                    "Дата или время указаны неверно.\n\n"
                    "Пример:\n"
                    "12.09.2026\n"
                    "14:30",
                    parent=dialog,
                )
                return

            # Не позволяем создать уже просроченное
            # напоминание.
            if dt <= datetime.now():
                messagebox.showerror(
                    "Ошибка",
                    "Дата и время должны быть в будущем.",
                    parent=dialog,
                )
                return

            self.db.add_reminder(
                title=title,
                description=description,
                remind_at=dt.isoformat(timespec="seconds"),
            )

            dialog.destroy()
            self.refresh_list()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))

        ttk.Button(
            buttons,
            text="Сохранить",
            command=save,
        ).pack(side="right", padx=5)

        ttk.Button(
            buttons,
            text="Отмена",
            command=dialog.destroy,
        ).pack(side="right")

        title_entry.focus_set()

    # ------------------------------------------------------------------
    # Просмотр напоминания
    # ------------------------------------------------------------------

    def show_reminder(self, reminder_id):
        reminders = self.db.get_all()

        reminder = None

        for item in reminders:
            if item["id"] == reminder_id:
                reminder = item
                break

        if reminder is None:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(reminder["title"])
        dialog.geometry("500x350")
        dialog.resizable(False, False)

        dialog.transient(self.root)

        frame = ttk.Frame(
            dialog,
            padding=20,
        )
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=reminder["title"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text=(
                "Дата и время: "
                + self.format_datetime(reminder["remind_at"])
            ),
        ).pack(
            anchor="w",
            pady=(10, 5),
        )

        ttk.Label(
            frame,
            text=f"Статус: {reminder['status']}",
        ).pack(
            anchor="w",
            pady=(0, 15),
        )

        text = tk.Text(
            frame,
            height=8,
            wrap="word",
            font=("Segoe UI", 10),
        )
        text.pack(
            fill="both",
            expand=True,
        )

        text.insert(
            "1.0",
            reminder["description"],
        )

        text.configure(state="disabled")

        ttk.Button(
            frame,
            text="Закрыть",
            command=dialog.destroy,
        ).pack(
            anchor="e",
            pady=(10, 0),
        )

    # ------------------------------------------------------------------
    # Уведомления
    # ------------------------------------------------------------------

    def notification_loop(self):
        """
        Работает в отдельном потоке.
        Проверяет БД каждые 5 секунд.
        """

        while not self.stop_event.is_set():
            try:
                # Автоматически просрочиваем старые.
                self.db.update_overdue()

                # Находим напоминания, время которых наступило.
                due_reminders = self.db.get_due_reminders()

                for reminder in due_reminders:
                    self.show_notification(
                        title=reminder["title"],
                        description=reminder["description"],
                        reminder_id=reminder["id"],
                    )

                    # Важно: сразу помечаем уведомление как показанное,
                    # чтобы оно не появлялось каждые 5 секунд.
                    self.db.mark_notified(
                        reminder["id"]
                    )

                # Обновление таблицы выполняем через главный
                # tkinter-поток.
                if due_reminders:
                    self.root.after(
                        0,
                        self.refresh_list,
                    )

            except Exception as error:
                print(
                    "Ошибка мониторинга:",
                    error,
                )

            self.stop_event.wait(5)

    def show_notification(
        self,
        title,
        description,
        reminder_id,
    ):
        """
        Нативное уведомление Windows 10/11.
        Если winotify недоступен — используется popup Tkinter.
        """

        text = description.strip()

        if not text:
            text = "Наступило время напоминания."

        # Ограничиваем размер текста уведомления.
        if len(text) > 500:
            text = text[:497] + "..."

        if WINOTIFY_AVAILABLE:
            try:
                notification = Notification(
                    app_id="Reminder App",
                    title=title,
                    msg=text,
                )

                # Звук уведомления.
                notification.set_audio(
                    audio.Default,
                    loop=False,
                )

                notification.show()

                return

            except Exception as error:
                print(
                    "Не удалось показать Windows-уведомление:",
                    error,
                )

        # Fallback — popup поверх окон.
        self.root.after(
            0,
            lambda: self.show_popup(
                title,
                text,
            ),
        )

    # ------------------------------------------------------------------
    # Popup
    # ------------------------------------------------------------------

    def show_popup(self, title, description):
        popup = tk.Toplevel(self.root)

        popup.title("Напоминание")
        popup.geometry("420x230")
        popup.resizable(False, False)

        # Поверх всех окон.
        popup.attributes(
            "-topmost",
            True,
        )

        popup.transient(self.root)

        # Перемещаем в правый нижний угол.
        popup.update_idletasks()

        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()

        width = 420
        height = 230

        x = screen_width - width - 30
        y = screen_height - height - 70

        popup.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        frame = ttk.Frame(
            popup,
            padding=20,
        )
        frame.pack(
            fill="both",
            expand=True,
        )

        ttk.Label(
            frame,
            text=title,
            font=("Segoe UI", 15, "bold"),
        ).pack(
            anchor="w",
        )

        ttk.Label(
            frame,
            text=description,
            wraplength=370,
            justify="left",
        ).pack(
            anchor="w",
            pady=(15, 20),
        )

        ttk.Button(
            frame,
            text="Закрыть",
            command=popup.destroy,
        ).pack(
            anchor="e",
        )

        # Автоматически убрать popup через 15 секунд.
        popup.after(
            15000,
            lambda: (
                popup.destroy()
                if popup.winfo_exists()
                else None
            ),
        )

        popup.lift()
        popup.focus_force()

    # ------------------------------------------------------------------
    # Завершение программы
    # ------------------------------------------------------------------

    def on_close(self):
        self.stop_event.set()
        self.root.destroy()


def main():
    root = tk.Tk()

    app = ReminderApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()
    