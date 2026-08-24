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
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("460x470")
        self.resizable(False, False)
        self.result: tuple[str, str, float] | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Name", anchor="w").grid(row=0, column=0, padx=24, pady=(20, 4), sticky="ew")
        self._name_entry = ctk.CTkEntry(self, height=34, font=ctk.CTkFont(size=14))
        self._name_entry.insert(0, name)
        self._name_entry.grid(row=1, column=0, padx=24, pady=(0, 12), sticky="ew")

        description_label = ctk.CTkLabel(self, text="Description", anchor="w")
        description_label.grid(row=2, column=0, padx=24, pady=(0, 4), sticky="ew")
        self._description_box = ctk.CTkTextbox(self, height=100, font=ctk.CTkFont(size=13))
        if description:
            self._description_box.insert("1.0", description)
        self._description_box.grid(row=3, column=0, padx=24, pady=(0, 6), sticky="nsew")

        ctk.CTkLabel(
            self, text="Daily goal (minutes per day, empty = none)", anchor="w"
        ).grid(row=4, column=0, padx=24, pady=(6, 4), sticky="ew")
        self._goal_entry = ctk.CTkEntry(self, height=34)
        if daily_goal_minutes:
            self._goal_entry.insert(0, str(int(daily_goal_minutes)))
        self._goal_entry.grid(row=5, column=0, padx=24, sticky="ew")

        self._error_label = ctk.CTkLabel(self, text="", text_color="#ef5350", anchor="w", height=18)
        self._error_label.grid(row=6, column=0, padx=24, sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=7, column=0, padx=24, pady=(8, 20), sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            buttons, text="Cancel", width=100, fg_color="transparent", border_width=1,
            command=self.destroy,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", width=120, command=self._save).grid(row=0, column=2)

        self.bind("<Escape>", lambda _e: self.destroy())
        self._name_entry.focus_set()
        make_modal(self, parent)

    def _save(self) -> None:
        name = self._name_entry.get().strip()
        if not name:
            self._error_label.configure(text="Name is required.")
            return
        raw_goal = self._goal_entry.get().strip()
        goal = 0.0
        if raw_goal:
            try:
                goal = float(raw_goal)
            except ValueError:
                self._error_label.configure(text="Daily goal must be a number of minutes.")
                return
            if not 0 < goal <= 1440:
                self._error_label.configure(text="Daily goal must be between 1 and 1440 minutes.")
                return
        description = self._description_box.get("1.0", "end").strip()
        self.result = (name, description, goal)
        self.destroy()

    def show(self) -> tuple[str, str, float] | None:
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
            actions, text=f"Register {elapsed_text}", width=160,
            command=lambda: self._choose("register"),
        )
        register_button.pack(side="left", padx=6)
        ctk.CTkButton(
            actions, text="Discard", width=90, fg_color="transparent", border_width=1,
            command=lambda: self._choose("discard"),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions, text="Keep going", width=110, fg_color="transparent", border_width=1,
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
        ctk.CTkLabel(
            self, text=f"{elapsed_text} focused until now", text_color="gray70"
        ).grid(row=3, column=0, pady=2)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=4, column=0, pady=(22, 24))
        ctk.CTkButton(actions, text="Resume session", width=140, command=lambda: self._choose("resume")).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            actions, text="Log & end", width=110, fg_color="transparent", border_width=1,
            command=lambda: self._choose("finish"),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions, text="Discard", width=90, fg_color="transparent", border_width=1,
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
