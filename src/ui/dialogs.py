from tkinter import messagebox

import customtkinter as ctk


def confirm(parent, title: str, message: str) -> bool:
    return bool(messagebox.askyesno(title, message, parent=parent))


def make_modal(dialog: ctk.CTkToplevel, parent) -> None:
    dialog.transient(parent)
    dialog.after(80, dialog.grab_set)
    dialog.after(80, dialog.focus_force)


class ProjectFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        title: str,
        name: str = "",
        description: str = "",
        daily_goal_minutes: float = 0.0,
        weekly_goal_minutes: float = 0.0,
        monthly_goal_minutes: float = 0.0,
        goal_days_of_week: list[int] | None = None,
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("520x620")
        self.resizable(False, False)
        self.result: tuple[str, str, float, float, float, list[int] | None] | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Name", anchor="w").grid(row=0, column=0, padx=24, pady=(20, 4), sticky="ew")
        self._name_entry = ctk.CTkEntry(self, height=34, font=ctk.CTkFont(size=14))
        self._name_entry.insert(0, name)
        self._name_entry.grid(row=1, column=0, padx=24, pady=(0, 12), sticky="ew")

        description_label = ctk.CTkLabel(self, text="Description", anchor="w")
        description_label.grid(row=2, column=0, padx=24, pady=(0, 4), sticky="ew")
        self._description_box = ctk.CTkTextbox(self, height=80, font=ctk.CTkFont(size=13))
        if description:
            self._description_box.insert("1.0", description)
        self._description_box.grid(row=3, column=0, padx=24, pady=(0, 6), sticky="nsew")

        # Goals row
        ctk.CTkLabel(self, text="Goals (minutes, empty = none)", anchor="w").grid(
            row=4, column=0, padx=24, pady=(6, 4), sticky="ew"
        )
        goals_frame = ctk.CTkFrame(self, fg_color="transparent")
        goals_frame.grid(row=5, column=0, padx=24, sticky="ew")
        goals_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(goals_frame, text="Daily", anchor="w", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkLabel(goals_frame, text="Weekly", anchor="w", font=ctk.CTkFont(size=12)).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ctk.CTkLabel(goals_frame, text="Monthly", anchor="w", font=ctk.CTkFont(size=12)).grid(
            row=0, column=2, sticky="ew", padx=(6, 0)
        )
        self._daily_entry = ctk.CTkEntry(goals_frame, height=32)
        if daily_goal_minutes:
            self._daily_entry.insert(0, str(int(daily_goal_minutes)))
        self._daily_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        self._weekly_entry = ctk.CTkEntry(goals_frame, height=32)
        if weekly_goal_minutes:
            self._weekly_entry.insert(0, str(int(weekly_goal_minutes)))
        self._weekly_entry.grid(row=1, column=1, sticky="ew", padx=6)
        self._monthly_entry = ctk.CTkEntry(goals_frame, height=32)
        if monthly_goal_minutes:
            self._monthly_entry.insert(0, str(int(monthly_goal_minutes)))
        self._monthly_entry.grid(row=1, column=2, sticky="ew", padx=(6, 0))

        # Days of week - por projeto: vazio = sem dias fixos (flexível)
        ctk.CTkLabel(self, text="Dias fixos (vazio = sem dias fixos)", anchor="w").grid(
            row=6, column=0, padx=24, pady=(12, 4), sticky="ew"
        )
        days_frame = ctk.CTkFrame(self, fg_color="transparent")
        days_frame.grid(row=7, column=0, padx=24, sticky="ew")
        self._day_vars: list[ctk.BooleanVar] = []
        day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, lbl in enumerate(day_labels):
            var = ctk.BooleanVar(value=(i in goal_days_of_week) if goal_days_of_week else False)
            chk = ctk.CTkCheckBox(days_frame, text=lbl, variable=var, width=60)
            chk.grid(row=0, column=i, padx=2)
            self._day_vars.append(var)

        self._error_label = ctk.CTkLabel(self, text="", text_color="#ef5350", anchor="w", height=18)
        self._error_label.grid(row=8, column=0, padx=24, sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=9, column=0, padx=24, pady=(8, 20), sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
            fg_color="transparent",
            border_width=1,
            command=self.destroy,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", width=120, command=self._save).grid(row=0, column=2)

        self.bind("<Escape>", lambda _e: self.destroy())
        self._name_entry.focus_set()
        make_modal(self, parent)

    def _parse_goal(self, raw: str, label: str) -> float | None:
        raw = raw.strip()
        if not raw:
            return 0.0
        try:
            v = float(raw)
        except ValueError:
            self._error_label.configure(text=f"{label} must be a number.")
            return None
        if not 0 < v <= 10080:
            self._error_label.configure(text=f"{label} must be between 1 and 10080.")
            return None
        return v

    def _save(self) -> None:
        name = self._name_entry.get().strip()
        if not name:
            self._error_label.configure(text="Name is required.")
            return
        daily = self._parse_goal(self._daily_entry.get(), "Daily goal")
        if daily is None:
            return
        weekly = self._parse_goal(self._weekly_entry.get(), "Weekly goal")
        if weekly is None:
            return
        monthly = self._parse_goal(self._monthly_entry.get(), "Monthly goal")
        if monthly is None:
            return
        # vazio = sem dias fixos (None); 1..7 = dias específicos
        selected = [i for i, var in enumerate(self._day_vars) if var.get()]
        days: list[int] | None = selected if selected else None
        description = self._description_box.get("1.0", "end").strip()
        self.result = (name, description, float(daily), float(weekly), float(monthly), days)
        self.destroy()

    def show(self) -> tuple[str, str, float, float, float, list[int] | None] | None:
        self.wait_window()
        return self.result


class TextPromptDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        title: str,
        initial: str = "",
        label: str = "Text",
        ok_text: str = "Save",
        empty_message: str = "Text is required.",
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("460x190")
        self.resizable(False, False)
        self.result: str | None = None
        self._empty_message = empty_message

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=label, anchor="w").grid(row=0, column=0, padx=24, pady=(20, 4), sticky="ew")
        self._entry = ctk.CTkEntry(self, height=34, font=ctk.CTkFont(size=14))
        self._entry.insert(0, initial)
        self._entry.grid(row=1, column=0, padx=24, pady=(0, 6), sticky="ew")

        self._error_label = ctk.CTkLabel(self, text="", text_color="#ef5350", anchor="w", height=18)
        self._error_label.grid(row=2, column=0, padx=24, sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=24, pady=(6, 18), sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
            fg_color="transparent",
            border_width=1,
            command=self.destroy,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(buttons, text=ok_text, width=120, command=self._save).grid(row=0, column=2)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._save())
        self._entry.focus_set()
        self._entry.icursor("end")
        make_modal(self, parent)

    def _save(self) -> None:
        text = self._entry.get().strip()
        if not text:
            self._error_label.configure(text=self._empty_message)
            return
        self.result = text
        self.destroy()

    def show(self) -> str | None:
        self.wait_window()
        return self.result


class InterruptDialog(ctk.CTkToplevel):
    def __init__(self, parent, elapsed_text: str):
        super().__init__(parent)
        self.title("Session interrupted")
        self.geometry("420x240")
        self.resizable(False, False)
        self.choice: str | None = None

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Session interrupted", font=ctk.CTkFont(size=19, weight="bold")).grid(
            row=0, column=0, pady=(26, 4)
        )
        ctk.CTkLabel(self, text=f"Time focused so far: {elapsed_text}", text_color="gray70").grid(
            row=1, column=0
        )
        ctk.CTkLabel(self, text="What do you want to do with this time?").grid(row=2, column=0, pady=(10, 16))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, pady=(0, 24))
        register_button = ctk.CTkButton(
            actions,
            text=f"Register {elapsed_text}",
            width=160,
            command=lambda: self._choose("register"),
        )
        register_button.pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Discard",
            width=90,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._choose("discard"),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Keep going",
            width=110,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._choose("continue"),
        ).pack(side="left", padx=6)

        self.bind("<Escape>", lambda _e: self._choose("continue"))
        make_modal(self, parent)

    def _choose(self, choice: str) -> None:
        self.choice = choice
        self.destroy()

    def show(self) -> str | None:
        self.wait_window()
        return self.choice or "continue"


class RecoveryDialog(ctk.CTkToplevel):
    def __init__(self, parent, project_name: str, started_text: str, elapsed_text: str):
        super().__init__(parent)
        self.title("Unfinished session")
        self.geometry("430x270")
        self.resizable(False, False)
        self.choice: str | None = None

        self.grid_columnconfigure(0, weight=1)

        heading = ctk.CTkLabel(
            self, text="You had a session in progress", font=ctk.CTkFont(size=19, weight="bold")
        )
        heading.grid(row=0, column=0, pady=(26, 10))
        ctk.CTkLabel(self, text=project_name, font=ctk.CTkFont(size=15)).grid(row=1, column=0, pady=2)
        ctk.CTkLabel(self, text=f"Started at {started_text}", text_color="gray70").grid(
            row=2, column=0, pady=2
        )
        ctk.CTkLabel(self, text=f"{elapsed_text} focused until now", text_color="gray70").grid(
            row=3, column=0, pady=2
        )

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=4, column=0, pady=(22, 24))
        ctk.CTkButton(actions, text="Resume session", width=140, command=lambda: self._choose("resume")).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            actions,
            text="Log & end",
            width=110,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._choose("finish"),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Discard",
            width=90,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._choose("discard"),
        ).pack(side="left", padx=6)

        self.bind("<Escape>", lambda _e: self._choose("resume"))
        make_modal(self, parent)

    def _choose(self, choice: str) -> None:
        self.choice = choice
        self.destroy()

    def show(self) -> str | None:
        self.wait_window()
        return self.choice or "resume"


class SwitchProjectDialog(ctk.CTkToplevel):
    def __init__(self, parent, targets: list[tuple[int, str]]):
        super().__init__(parent)
        self.title("Switch project")
        self.result: int | None = None
        self.geometry("320x260")
        self.resizable(False, False)

        ctk.CTkLabel(self, text="Switch to:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            padx=20, pady=(16, 8), anchor="w"
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=180)
        scroll.pack(fill="x", padx=20)

        for pid, label in targets:
            ctk.CTkButton(
                scroll,
                text=label,
                anchor="w",
                height=32,
                fg_color="transparent",
                border_width=1,
                border_color=("gray70", "gray30"),
                command=lambda p=pid: self._pick(p),
            ).pack(fill="x", pady=2)

        self.bind("<Escape>", lambda _: self.destroy())
        make_modal(self, parent)

    def _pick(self, project_id: int) -> None:
        self.result = project_id
        self.destroy()

    def show(self) -> int | None:
        self.wait_window()
        return self.result
