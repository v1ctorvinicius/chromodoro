import customtkinter as ctk

from utils.formatting import format_clock


class FocusBar(ctk.CTkFrame):
    def __init__(
        self,
        master,
        project_name: str,
        clock_fn,
        running_fn,
        on_toggle,
        on_open,
        tick_ms: int = 1000,
    ):
        super().__init__(master, corner_radius=10, fg_color=("#d7f2da", "#12351a"))
        self._clock_fn = clock_fn
        self._running_fn = running_fn
        self._on_toggle = on_toggle
        self._on_open = on_open
        self._tick_ms = tick_ms
        self._job = None
        self._project_name = project_name

        self.grid_columnconfigure(1, weight=1)

        self._dot = ctk.CTkLabel(self, text="\u25CF", text_color="#66bb6a", font=ctk.CTkFont(size=13))
        self._dot.grid(row=0, column=0, padx=(14, 8), pady=8)
        self._info = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        self._info.grid(row=0, column=1, sticky="w")
        self._toggle_btn = ctk.CTkButton(
            self, text="\u23F8", width=34, height=26, fg_color="transparent",
            border_width=1, border_color=("gray55", "gray40"),
            command=self._toggle,
        )
        self._toggle_btn.grid(row=0, column=2, padx=(6, 4))
        ctk.CTkLabel(self, text="Open focus \u25B8", text_color="gray40", font=ctk.CTkFont(size=12)).grid(
            row=0, column=3, padx=(2, 14)
        )

        def click(_event) -> str:
            on_open()
            return "break"

        for target in (self, self._dot, self._info):
            target.bind("<Button-1>", click)
            target.configure(cursor="hand2")

        self.bind("<Destroy>", self._on_destroy, add="+")
        self._refresh()
        self._schedule()

    def _toggle(self) -> None:
        self._on_toggle()
        self._refresh()

    def _refresh(self) -> None:
        running = bool(self._running_fn())
        text = f"{format_clock(self._clock_fn())}  ·  {self._project_name}"
        text += "  ·  RUNNING" if running else "  ·  PAUSED"
        self._info.configure(text=text)
        self._dot.configure(text_color="#66bb6a" if running else "#ffb74d")
        self.configure(fg_color=("#d7f2da", "#12351a") if running else ("#fdeeca", "#3a2c0e"))
        self._toggle_btn.configure(text="\u23F8" if running else "\u25B6")

    def _schedule(self) -> None:
        self._job = self.after(self._tick_ms, self._tick)

    def _tick(self) -> None:
        if not self.winfo_exists():
            self._job = None
            return
        self._refresh()
        self._schedule()

    def _on_destroy(self, _event) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
