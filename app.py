import tkinter as tk
from tkinter import ttk, messagebox

from datetime import datetime

from database import Database, STATUSES


# ============================================================
# Windows notifications
# ============================================================

try:
    from winotify import Notification, audio

    WINOTIFY_AVAILABLE = True

except ImportError:
    WINOTIFY_AVAILABLE = False


# ============================================================
# Application
# ============================================================

class ReminderApp:

    CHECK_INTERVAL = 1000  # проверка каждую секунду

    def __init__(self, root):

        self.root = root

        self.root.title("Напоминания")
        self.root.geometry("1100x650")
        self.root.minsize(900, 550)

        self.db = Database()

        self.setup_style()
        self.create_widgets()

        # Актуализируем просроченные.
        self.db.update_overdue()

        # Первоначальная загрузка.
        self.refresh_list()

        # Запускаем проверку напоминаний.
        self.check_reminders()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

    # ========================================================
    # STYLE
    # ========================================================

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

    # ========================================================
    # GUI
    # ========================================================

    def create_widgets(self):

        # ----------------------------------------------------
        # Заголовок
        # ----------------------------------------------------

        top_frame = ttk.Frame(
            self.root,
            padding=10
        )

        top_frame.pack(fill="x")

        ttk.Label(
            top_frame,
            text="Напоминания",
            font=(
                "Segoe UI",
                18,
                "bold"
            ),
        ).pack(side="left")

        ttk.Button(
            top_frame,
            text="Добавить",
            command=self.add_dialog,
        ).pack(
            side="right",
            padx=5
        )

        ttk.Button(
            top_frame,
            text="Изменить",
            command=self.edit_selected,
        ).pack(
            side="right",
            padx=5
        )

        ttk.Button(
            top_frame,
            text="Удалить",
            command=self.delete_selected,
        ).pack(
            side="right",
            padx=5
        )

        # ----------------------------------------------------
        # Фильтр
        # ----------------------------------------------------

        filter_frame = ttk.Frame(
            self.root,
            padding=(10, 0, 10, 10)
        )

        filter_frame.pack(fill="x")

        ttk.Label(
            filter_frame,
            text="Фильтр по статусу:"
        ).pack(
            side="left",
            padx=(0, 5)
        )

        self.filter_var = tk.StringVar(
            value="Все"
        )

        self.filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_var,
            values=("Все", *STATUSES),
            state="readonly",
            width=18,
        )

        self.filter_combo.pack(
            side="left"
        )

        self.filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self.refresh_list()
        )

        ttk.Button(
            filter_frame,
            text="Обновить",
            command=self.refresh_list,
        ).pack(
            side="left",
            padx=10
        )

        # ----------------------------------------------------
        # Таблица
        # ----------------------------------------------------

        table_frame = ttk.Frame(
            self.root,
            padding=(10, 0, 10, 10)
        )

        table_frame.pack(
            fill="both",
            expand=True
        )

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

        self.tree.heading(
            "id",
            text="ID"
        )

        self.tree.heading(
            "title",
            text="Заголовок"
        )

        self.tree.heading(
            "description",
            text="Описание"
        )

        self.tree.heading(
            "remind_at",
            text="Дата и время"
        )

        self.tree.heading(
            "status",
            text="Статус"
        )

        self.tree.column(
            "id",
            width=50,
            anchor="center"
        )

        self.tree.column(
            "title",
            width=210
        )

        self.tree.column(
            "description",
            width=380
        )

        self.tree.column(
            "remind_at",
            width=170
        )

        self.tree.column(
            "status",
            width=130,
            anchor="center"
        )

        # ----------------------------------------------------
        # Цвета статусов
        # ----------------------------------------------------

        self.tree.tag_configure(
            "overdue",
            background="#FDECEC"
        )

        self.tree.tag_configure(
            "done",
            background="#EAF7EA"
        )

        self.tree.tag_configure(
            "cancelled",
            background="#EEEEEE"
        )

        self.tree.tag_configure(
            "waiting",
            background="#FFFFFF"
        )

        # ----------------------------------------------------
        # Scrollbars
        # ----------------------------------------------------

        scrollbar_y = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )

        scrollbar_x = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scrollbar_y.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        scrollbar_x.grid(
            row=1,
            column=0,
            sticky="ew"
        )

        table_frame.rowconfigure(
            0,
            weight=1
        )

        table_frame.columnconfigure(
            0,
            weight=1
        )

        # Двойной клик — редактирование.
        self.tree.bind(
            "<Double-1>",
            self.on_double_click
        )

        # ----------------------------------------------------
        # Быстрые действия
        # ----------------------------------------------------

        quick_frame = ttk.LabelFrame(
            self.root,
            text="Быстрое напоминание",
            padding=8
        )

        quick_frame.pack(
            fill="x",
            padx=10,
            pady=(0, 10)
        )

        ttk.Label(
            quick_frame,
            text="Перенести выбранное напоминание:"
        ).pack(
            side="left",
            padx=(0, 10)
        )

        ttk.Button(
            quick_frame,
            text="+ 5 минут",
            command=lambda: self.postpone_selected(5),
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            quick_frame,
            text="+ 15 минут",
            command=lambda: self.postpone_selected(15),
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            quick_frame,
            text="+ 30 минут",
            command=lambda: self.postpone_selected(30),
        ).pack(
            side="left",
            padx=3
        )

        # ----------------------------------------------------
        # Статусы
        # ----------------------------------------------------

        bottom_frame = ttk.Frame(
            self.root,
            padding=(10, 0, 10, 10)
        )

        bottom_frame.pack(
            fill="x"
        )

        ttk.Button(
            bottom_frame,
            text="✓ Готово",
            command=lambda: self.change_status(
                "Готово"
            ),
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            bottom_frame,
            text="✕ Отменено",
            command=lambda: self.change_status(
                "Отменено"
            ),
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            bottom_frame,
            text="↻ Ожидает",
            command=lambda: self.change_status(
                "Ожидает"
            ),
        ).pack(
            side="left",
            padx=3
        )

        self.status_label = ttk.Label(
            bottom_frame,
            text=""
        )

        self.status_label.pack(
            side="right"
        )

    # ========================================================
    # REFRESH
    # ========================================================

    def refresh_list(self):

        self.db.update_overdue()

        selected_id = None

        selection = self.tree.selection()

        if selection:
            try:
                selected_id = int(
                    selection[0]
                )
            except ValueError:
                pass

        # Очищаем таблицу.
        for item in self.tree.get_children():
            self.tree.delete(item)

        status = self.filter_var.get()

        reminders = self.db.get_all(
            status
        )

        for reminder in reminders:

            reminder_status = (
                reminder["status"]
            )

            if reminder_status == "Просрочено":
                tag = "overdue"

            elif reminder_status == "Готово":
                tag = "done"

            elif reminder_status == "Отменено":
                tag = "cancelled"

            else:
                tag = "waiting"

            self.tree.insert(
                "",
                "end",
                iid=str(
                    reminder["id"]
                ),
                values=(
                    reminder["id"],
                    reminder["title"],
                    reminder["description"],
                    self.format_datetime(
                        reminder["remind_at"]
                    ),
                    reminder_status,
                ),
                tags=(tag,)
            )

        # Восстанавливаем выделение.
        if (
            selected_id is not None
            and self.tree.exists(
                str(selected_id)
            )
        ):
            self.tree.selection_set(
                str(selected_id)
            )

        self.status_label.config(
            text=f"Напоминаний: {len(reminders)}"
        )

    # ========================================================
    # REMINDER CHECK
    # ========================================================

    def check_reminders(self):

        try:

            # Просроченные.
            self.db.update_overdue()

            # Напоминания, которым пора сработать.
            due = self.db.get_due_reminders()

            for reminder in due:

                self.show_notification(
                    reminder
                )

                self.db.mark_notified(
                    reminder["id"]
                )

            # Обновляем интерфейс каждый цикл.
            # Это позволяет автоматически менять
            # статус "Ожидает" -> "Просрочено".
            self.refresh_list()

        except Exception as error:

            print(
                "Ошибка проверки:",
                repr(error)
            )

        # Следующая проверка через секунду.
        self.root.after(
            self.CHECK_INTERVAL,
            self.check_reminders
        )

    # ========================================================
    # QUICK POSTPONE
    # ========================================================

    def postpone_selected(self, minutes):

        reminder_id = (
            self.get_selected_id()
        )

        if reminder_id is None:
            return

        reminder = self.db.get_reminder(
            reminder_id
        )

        if reminder is None:
            return

        new_time = self.db.postpone_reminder(
            reminder_id,
            minutes
        )

        self.refresh_list()

        messagebox.showinfo(
            "Напоминание перенесено",
            (
                f"Новое время:\n\n"
                f"{new_time.strftime('%d.%m.%Y %H:%M')}"
            )
        )

    # ========================================================
    # ADD
    # ========================================================

    def add_dialog(self):

        dialog = tk.Toplevel(
            self.root
        )

        dialog.title(
            "Новое напоминание"
        )

        dialog.geometry(
            "520x430"
        )

        dialog.resizable(
            False,
            False
        )

        dialog.transient(
            self.root
        )

        dialog.grab_set()

        frame = ttk.Frame(
            dialog,
            padding=20
        )

        frame.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            frame,
            text="Заголовок:"
        ).pack(
            anchor="w"
        )

        title_var = tk.StringVar()

        title_entry = ttk.Entry(
            frame,
            textvariable=title_var
        )

        title_entry.pack(
            fill="x",
            pady=(5, 15)
        )

        ttk.Label(
            frame,
            text="Описание:"
        ).pack(
            anchor="w"
        )

        description_text = tk.Text(
            frame,
            height=7,
            font=("Segoe UI", 10)
        )

        description_text.pack(
            fill="x",
            pady=(5, 15)
        )

        ttk.Label(
            frame,
            text="Дата (ДД.ММ.ГГГГ):"
        ).pack(
            anchor="w"
        )

        date_var = tk.StringVar(
            value=datetime.now().strftime(
                "%d.%m.%Y"
            )
        )

        ttk.Entry(
            frame,
            textvariable=date_var
        ).pack(
            fill="x",
            pady=(5, 10)
        )

        ttk.Label(
            frame,
            text="Время (ЧЧ:ММ):"
        ).pack(
            anchor="w"
        )

        time_var = tk.StringVar(
            value=datetime.now().strftime(
                "%H:%M"
            )
        )

        ttk.Entry(
            frame,
            textvariable=time_var
        ).pack(
            fill="x",
            pady=(5, 15)
        )

        def save():

            title = (
                title_var.get().strip()
            )

            description = (
                description_text
                .get("1.0", "end")
                .strip()
            )

            if not title:

                messagebox.showerror(
                    "Ошибка",
                    "Введите заголовок.",
                    parent=dialog
                )

                return

            try:

                dt = datetime.strptime(
                    f"{date_var.get().strip()} "
                    f"{time_var.get().strip()}",
                    "%d.%m.%Y %H:%M"
                )

            except ValueError:

                messagebox.showerror(
                    "Ошибка",
                    "Неверный формат даты или времени.\n\n"
                    "Например:\n"
                    "12.09.2026\n"
                    "14:30",
                    parent=dialog
                )

                return

            if dt <= datetime.now():

                messagebox.showerror(
                    "Ошибка",
                    "Дата и время должны быть в будущем.",
                    parent=dialog
                )

                return

            self.db.add_reminder(
                title,
                description,
                dt.isoformat(
                    timespec="seconds"
                )
            )

            dialog.destroy()

            self.refresh_list()

        buttons = ttk.Frame(
            frame
        )

        buttons.pack(
            fill="x",
            pady=(10, 0)
        )

        ttk.Button(
            buttons,
            text="Сохранить",
            command=save
        ).pack(
            side="right",
            padx=5
        )

        ttk.Button(
            buttons,
            text="Отмена",
            command=dialog.destroy
        ).pack(
            side="right"
        )

        title_entry.focus_set()

    # ========================================================
    # EDIT
    # ========================================================

    def edit_selected(self):

        reminder_id = (
            self.get_selected_id()
        )

        if reminder_id is None:
            return

        reminder = self.db.get_reminder(
            reminder_id
        )

        if reminder is None:
            return

        self.edit_dialog(
            reminder
        )

    def edit_dialog(self, reminder):

        dialog = tk.Toplevel(
            self.root
        )

        dialog.title(
            "Изменить напоминание"
        )

        dialog.geometry(
            "520x430"
        )

        dialog.resizable(
            False,
            False
        )

        dialog.transient(
            self.root
        )

        dialog.grab_set()

        frame = ttk.Frame(
            dialog,
            padding=20
        )

        frame.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Заголовок:"
        ).pack(
            anchor="w"
        )

        title_var = tk.StringVar(
            value=reminder["title"]
        )

        title_entry = ttk.Entry(
            frame,
            textvariable=title_var
        )

        title_entry.pack(
            fill="x",
            pady=(5, 15)
        )

        # ----------------------------------------------------
        # Description
        # ----------------------------------------------------

        ttk.Label(
            frame,
            text="Описание:"
        ).pack(
            anchor="w"
        )

        description_text = tk.Text(
            frame,
            height=7,
            font=("Segoe UI", 10)
        )

        description_text.pack(
            fill="x",
            pady=(5, 15)
        )

        description_text.insert(
            "1.0",
            reminder["description"]
        )

        # ----------------------------------------------------
        # Existing date/time
        # ----------------------------------------------------

        try:

            old_datetime = datetime.fromisoformat(
                reminder["remind_at"]
            )

        except ValueError:

            old_datetime = datetime.now()

        ttk.Label(
            frame,
            text="Дата (ДД.ММ.ГГГГ):"
        ).pack(
            anchor="w"
        )

        date_var = tk.StringVar(
            value=old_datetime.strftime(
                "%d.%m.%Y"
            )
        )

        ttk.Entry(
            frame,
            textvariable=date_var
        ).pack(
            fill="x",
            pady=(5, 10)
        )

        ttk.Label(
            frame,
            text="Время (ЧЧ:ММ):"
        ).pack(
            anchor="w"
        )

        time_var = tk.StringVar(
            value=old_datetime.strftime(
                "%H:%M"
            )
        )

        ttk.Entry(
            frame,
            textvariable=time_var
        ).pack(
            fill="x",
            pady=(5, 15)
        )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        def save():

            title = (
                title_var.get().strip()
            )

            description = (
                description_text
                .get("1.0", "end")
                .strip()
            )

            if not title:

                messagebox.showerror(
                    "Ошибка",
                    "Введите заголовок.",
                    parent=dialog
                )

                return

            try:

                new_datetime = datetime.strptime(
                    f"{date_var.get().strip()} "
                    f"{time_var.get().strip()}",
                    "%d.%m.%Y %H:%M"
                )

            except ValueError:

                messagebox.showerror(
                    "Ошибка",
                    "Неверный формат даты или времени.\n\n"
                    "Например:\n"
                    "12.09.2026\n"
                    "14:30",
                    parent=dialog
                )

                return

            if new_datetime <= datetime.now():

                messagebox.showerror(
                    "Ошибка",
                    "Дата и время должны быть в будущем.",
                    parent=dialog
                )

                return

            self.db.update_reminder(
                reminder["id"],
                title,
                description,
                new_datetime.isoformat(
                    timespec="seconds"
                )
            )

            dialog.destroy()

            self.refresh_list()

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        buttons = ttk.Frame(
            frame
        )

        buttons.pack(
            fill="x",
            pady=(10, 0)
        )

        ttk.Button(
            buttons,
            text="Сохранить",
            command=save
        ).pack(
            side="right",
            padx=5
        )

        ttk.Button(
            buttons,
            text="Отмена",
            command=dialog.destroy
        ).pack(
            side="right"
        )

        title_entry.focus_set()

    # ========================================================
    # STATUS
    # ========================================================

    def get_selected_id(self):

        selection = self.tree.selection()

        if not selection:

            messagebox.showinfo(
                "Выбор",
                "Сначала выберите напоминание."
            )

            return None

        return int(
            selection[0]
        )

    def change_status(self, status):

        reminder_id = (
            self.get_selected_id()
        )

        if reminder_id is None:
            return

        self.db.set_status(
            reminder_id,
            status
        )

        self.refresh_list()

    # ========================================================
    # DELETE
    # ========================================================

    def delete_selected(self):

        reminder_id = (
            self.get_selected_id()
        )

        if reminder_id is None:
            return

        answer = messagebox.askyesno(
            "Удаление",
            "Удалить выбранное напоминание?"
        )

        if answer:

            self.db.delete_reminder(
                reminder_id
            )

            self.refresh_list()

    # ========================================================
    # DOUBLE CLICK
    # ========================================================

    def on_double_click(self, event):

        selection = self.tree.selection()

        if not selection:
            return

        reminder_id = int(
            selection[0]
        )

        reminder = self.db.get_reminder(
            reminder_id
        )

        if reminder:
            self.edit_dialog(
                reminder
            )

    # ========================================================
    # NOTIFICATION
    # ========================================================

    def show_notification(self, reminder):

        title = reminder["title"]

        description = (
            reminder["description"].strip()
        )

        if not description:

            description = (
                "Наступило время напоминания."
            )

        if len(description) > 500:

            description = (
                description[:497]
                + "..."
            )

        if WINOTIFY_AVAILABLE:

            try:

                notification = Notification(
                    app_id="Reminder App",
                    title=title,
                    msg=description,
                )

                notification.set_audio(
                    audio.Default,
                    loop=False
                )

                notification.show()

                print(
                    f"Уведомление: {title}"
                )

                return

            except Exception as error:

                print(
                    "Ошибка Windows notification:",
                    repr(error)
                )

        # Резервный popup.
        self.show_popup(
            title,
            description
        )

    # ========================================================
    # POPUP
    # ========================================================

    def show_popup(
        self,
        title,
        description
    ):

        popup = tk.Toplevel(
            self.root
        )

        popup.title(
            "Напоминание"
        )

        popup.geometry(
            "430x240"
        )

        popup.resizable(
            False,
            False
        )

        popup.attributes(
            "-topmost",
            True
        )

        popup.lift()
        popup.focus_force()

        popup.update_idletasks()

        screen_width = (
            popup.winfo_screenwidth()
        )

        screen_height = (
            popup.winfo_screenheight()
        )

        width = 430
        height = 240

        x = (
            screen_width
            - width
            - 30
        )

        y = (
            screen_height
            - height
            - 70
        )

        popup.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        frame = ttk.Frame(
            popup,
            padding=20
        )

        frame.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            frame,
            text=title,
            font=(
                "Segoe UI",
                15,
                "bold"
            ),
            wraplength=380,
        ).pack(
            anchor="w"
        )

        ttk.Label(
            frame,
            text=description,
            wraplength=380,
            justify="left",
        ).pack(
            anchor="w",
            pady=(15, 20)
        )

        ttk.Button(
            frame,
            text="Закрыть",
            command=popup.destroy
        ).pack(
            anchor="e"
        )

        popup.after(
            15000,
            lambda: (
                popup.destroy()
                if popup.winfo_exists()
                else None
            )
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def format_datetime(value):

        try:

            dt = datetime.fromisoformat(
                value
            )

            return dt.strftime(
                "%d.%m.%Y %H:%M"
            )

        except ValueError:

            return value

    # ========================================================
    # CLOSE
    # ========================================================

    def on_close(self):

        self.root.destroy()


# ============================================================
# ENTRY POINT
# ============================================================

def main():

    root = tk.Tk()

    ReminderApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()