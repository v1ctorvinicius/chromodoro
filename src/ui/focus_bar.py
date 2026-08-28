import tkinter as tk
import tkinter.font as tkfont

from utils.formatting import format_clock

_RUN_BG = "#12351a"
_PAUSE_BG = "#3a2c0e"
_RUN_DOT = "#66bb6a"
_PAUSE_DOT = "#ffb74d"
_TEXT = "#DCE4EE"
_MUTED = "#9aa4b2"


class FocusBar(tk.Frame):
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
        super().__init__(master, bg=_RUN_BG, bd=0, highlightthickness=0)
        self._clock_fn = clock_fn
        self._running_fn = running_fn
        self._on_toggle = on_toggle
        self._on_open = on_open
        self._tick_ms = tick_ms
        self._job: str | None = None
        self._project_name = project_name

        self.columnconfigure(1, weight=1)

        bold = tkfont.Font(size=13, weight="bold")
        small = tkfont.Font(size=12)

        self._dot = tk.Label(self, text="\u25CF", fg=_RUN_DOT, bg=_RUN_BG, font=("Segoe UI", 13))
        self._dot.grid(row=0, column=0, padx=(14, 8), pady=8)
        self._info = tk.Label(self, text="", font=bold, fg=_TEXT, bg=_RUN_BG, anchor="w")
        self._info.grid(row=0, column=1, sticky="w")

        self._toggle_btn = tk.Button(
            self,
            text="\u23F8",
            width=3,
            bg=_RUN_BG,
            fg=_TEXT,
            activebackground=_RUN_BG,
            activeforeground=_TEXT,
            relief="flat",
            borderwidth=1,
            highlightbackground=_MUTED,
            highlightcolor=_MUTED,
            highlightthickness=1,
            cursor="hand2",
            command=self._toggle,
        )
        self._toggle_btn.grid(row=0, column=2, padx=(6, 4), pady=4)

        self._open_label = tk.Label(
            self, text="Open focus \u25B8", fg=_MUTED, bg=_RUN_BG, font=small, cursor="hand2"
        )
        self._open_label.grid(row=0, column=3, padx=(2, 14))

        def click(_event) -> str:
            on_open()
            return "break"

        for target in (self, self._dot, self._info, self._open_label):
            target.bind("<Button-1>", click)
            target.configure(cursor="hand2")

        self._refresh()
        self._schedule()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _toggle(self) -> None:
        self._on_toggle()
        self._refresh()

    def _refresh(self) -> None:
        running = bool(self._running_fn())
        bg = _RUN_BG if running else _PAUSE_BG
        dot = _RUN_DOT if running else _PAUSE_DOT
        text = f"{format_clock(self._clock_fn())}  ·  {self._project_name}"
        text += "  ·  RUNNING" if running else "  ·  PAUSED"
        self._info.configure(text=text, bg=bg)
        self._dot.configure(fg=dot, bg=bg)
        self._open_label.configure(bg=bg)
        self.configure(bg=bg)
        self._toggle_btn.configure(
            text="\u23F8" if running else "\u25B6",
            bg=bg,
            activebackground=bg,
            fg=_TEXT,
            activeforeground=_TEXT,
        )

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
