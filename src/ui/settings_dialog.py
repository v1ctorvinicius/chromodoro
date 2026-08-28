import customtkinter as ctk

try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]

from config import ALERT_OPENING_TONES
from domain.settings import MAX_CYCLES, MAX_MINUTES, MIN_CYCLES, MIN_MINUTES, AppSettings
from ui.dialogs import make_modal

FIELDS = (
    ("work_minutes", "Focus length (minutes)", MIN_MINUTES, MAX_MINUTES),
    ("break_minutes", "Short break (minutes)", MIN_MINUTES, MAX_MINUTES),
    ("long_break_minutes", "Long break (minutes)", MIN_MINUTES, MAX_MINUTES),
    ("cycles_before_long_break", "Long break every N focus rounds", MIN_CYCLES, MAX_CYCLES),
)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, settings: AppSettings):
        super().__init__(parent)
        self.title("Timer settings")
        self.geometry("440x640")
        self.minsize(440, 640)
        self.resizable(True, True)
        self.result: AppSettings | None = None
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._sound_var = ctk.BooleanVar(master=self, value=settings.sound_alerts)
        self._auto_var = ctk.BooleanVar(master=self, value=settings.auto_start_after_break)
        self._tray_var = ctk.BooleanVar(master=self, value=settings.close_to_tray)
        self._start_tray_var = ctk.BooleanVar(master=self, value=settings.start_in_tray)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="Timer settings", font=ctk.CTkFont(size=19, weight="bold")).grid(
            row=0, column=0, pady=(22, 2)
        )
        ctk.CTkLabel(self, text="Changes apply from the next session on.", text_color="gray60").grid(
            row=1, column=0, pady=(0, 10)
        )

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=2, column=0, padx=28, sticky="nsew")
        form.grid_columnconfigure(0, weight=1)

        for index, (key, label_text, _low, _high) in enumerate(FIELDS):
            ctk.CTkLabel(form, text=label_text, anchor="w").grid(
                row=index * 2, column=0, sticky="ew", pady=(8, 2)
            )
            entry = ctk.CTkEntry(form, height=32)
            entry.insert(0, str(getattr(settings, key)))
            entry.grid(row=index * 2 + 1, column=0, sticky="ew")
            self._entries[key] = entry

        ctk.CTkCheckBox(
            form,
            text="Play sound alerts when a timer ends",
            variable=self._sound_var,
            checkbox_width=20,
            checkbox_height=20,
        ).grid(row=len(FIELDS) * 2, column=0, sticky="w", pady=(14, 0))
        ctk.CTkCheckBox(
            form,
            text="Auto-start focus when a break ends",
            variable=self._auto_var,
            checkbox_width=20,
            checkbox_height=20,
        ).grid(row=len(FIELDS) * 2 + 1, column=0, sticky="w", pady=(10, 0))
        ctk.CTkCheckBox(
            form,
            text="Close button minimizes to tray",
            variable=self._tray_var,
            checkbox_width=20,
            checkbox_height=20,
        ).grid(row=len(FIELDS) * 2 + 2, column=0, sticky="w", pady=(10, 0))
        ctk.CTkCheckBox(
            form,
            text="Start minimized to tray on launch",
            variable=self._start_tray_var,
            checkbox_width=20,
            checkbox_height=20,
        ).grid(row=len(FIELDS) * 2 + 3, column=0, sticky="w", pady=(10, 0))
        ctk.CTkButton(
            form,
            text="\u266A  Test sound",
            width=110,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=("gray60", "gray35"),
            command=self._test_sound,
        ).grid(row=len(FIELDS) * 2 + 4, column=0, sticky="w", pady=(8, 0))

        self._error_label = ctk.CTkLabel(self, text="", text_color="#ef5350", anchor="w", height=18)
        self._error_label.grid(row=3, column=0, padx=28, sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=4, column=0, padx=28, pady=(8, 20), sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            buttons, text="Cancel", width=100, fg_color="transparent", border_width=1,
            command=self.destroy,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", width=120, command=self._save).grid(row=0, column=2)

        self.bind("<Escape>", lambda _e: self.destroy())
        self._entries["work_minutes"].focus_set()
        make_modal(self, parent)

    def _save(self) -> None:
        values: dict[str, int] = {}
        for key, label_text, low, high in FIELDS:
            raw = self._entries[key].get().strip()
            try:
                parsed = int(raw)
            except ValueError:
                self._error_label.configure(text=f"{label_text}: enter a whole number.")
                return
            if not low <= parsed <= high:
                self._error_label.configure(text=f"{label_text}: must be between {low} and {high}.")
                return
            values[key] = parsed
        self.result = AppSettings(
            **values,
            sound_alerts=bool(self._sound_var.get()),
            auto_start_after_break=bool(self._auto_var.get()),
            close_to_tray=bool(self._tray_var.get()),
            start_in_tray=bool(self._start_tray_var.get()),
        )
        self.destroy()

    def _test_sound(self) -> None:
        def play(index: int = 0) -> None:
            if index >= len(ALERT_OPENING_TONES):
                return
            frequency, duration = ALERT_OPENING_TONES[index]
            try:
                if winsound is not None:
                    winsound.Beep(frequency, duration)
                else:
                    self.bell()
            except Exception:
                pass
            self.after(60, lambda n=index + 1: play(n))

        play()

    def show(self) -> AppSettings | None:
        self.wait_window()
        return self.result
