import customtkinter as ctk


class MiniView(ctk.CTkToplevel):
    def __init__(self, master, on_toggle, on_close, on_switch=None, on_refresh=None, saved_position=None):
        super().__init__(master)
        self._on_toggle = on_toggle
        self._on_close = on_close
        self._on_switch = on_switch
        self._on_refresh = on_refresh

        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        if saved_position:
            self.geometry(f"310x72+{saved_position}")
        else:
            self.geometry("310x72")
            self._center_top()
        self.configure(fg_color=("#d7f2da", "#12351a"))

        self._drag_x = 0
        self._drag_y = 0
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._do_drag)
        self.bind("<Escape>", lambda _: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.grid_columnconfigure(1, weight=1)

        self._dot = ctk.CTkLabel(self, text="\u25cf", text_color="#66bb6a", font=ctk.CTkFont(size=13))
        self._dot.grid(row=0, column=0, padx=(12, 4), pady=(14, 0))

        self._clock_label = ctk.CTkLabel(
            self, text="00:00", font=ctk.CTkFont(size=26, weight="bold"), anchor="w"
        )
        self._clock_label.grid(row=0, column=1, sticky="w", pady=(14, 0))

        self._name_label = ctk.CTkLabel(
            self, text="", text_color="gray55", font=ctk.CTkFont(size=11), anchor="w"
        )
        self._name_label.grid(row=1, column=1, sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=(14, 0))

        self._toggle_btn = ctk.CTkButton(
            btn_frame,
            text="\u23f8",
            width=36,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=("gray55", "gray40"),
            command=self._toggle_clicked,
        )
        self._toggle_btn.pack(side="left", padx=2)

        if self._on_switch is not None:
            ctk.CTkButton(
                btn_frame,
                text="\u21c4",
                width=28,
                height=28,
                fg_color="transparent",
                border_width=1,
                border_color=("gray55", "gray40"),
                command=self._on_switch,
            ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame,
            text="\u2715",
            width=28,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=("gray55", "gray40"),
            text_color="#ef9a9a",
            hover_color=("gray88", "gray22"),
            command=self._on_close,
        ).pack(side="left", padx=2)

        self._normal_widgets = [self._dot, self._clock_label, self._name_label, btn_frame]

        self._completion_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._completion_label = ctk.CTkLabel(
            self._completion_frame,
            text="Session done!",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self._completion_label.pack(side="left", padx=(12, 8))
        self._log_btn = ctk.CTkButton(
            self._completion_frame,
            text="Log",
            width=50,
            height=28,
            command=lambda: None,
        )
        self._log_btn.pack(side="left", padx=2)
        self._skip_btn = ctk.CTkButton(
            self._completion_frame,
            text="Skip",
            width=50,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=("gray60", "gray35"),
            command=lambda: None,
        )
        self._skip_btn.pack(side="left", padx=(2, 10))

    def _center_top(self):
        self.update_idletasks()
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = (sw - 310) // 2
            y = int(sh * 0.25)
            self.geometry(f"+{x}+{y}")
        except Exception:
            self.geometry("+800+500")

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event):
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _toggle_clicked(self):
        self._on_toggle()
        if self._on_refresh is not None:
            self._on_refresh()

    def update_info(self, clock_text: str, running: bool, project_name: str):
        self._clock_label.configure(text=clock_text)
        self._name_label.configure(text=project_name)
        self._toggle_btn.configure(text="\u23f8" if running else "\u25b6")
        self._dot.configure(text_color="#66bb6a" if running else "#ffb74d")
        bg = ("#d7f2da", "#12351a") if running else ("#fdeeca", "#3a2c0e")
        self.configure(fg_color=bg)

    def show_completion(self, elapsed_text: str, on_log, on_skip):
        for w in self._normal_widgets:
            w.grid_forget()
        self._completion_label.configure(text=f"Session done!  +{elapsed_text}")
        self._log_btn.configure(command=on_log)
        self._skip_btn.configure(command=on_skip)
        self._completion_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        self.configure(fg_color=("#e3f2fd", "#0d1b2a"))

    def show_break(self, break_text: str, on_start):
        for w in self._normal_widgets:
            w.grid_forget()
        self._completion_label.configure(text=f"Break done!  {break_text}")
        self._log_btn.configure(text="Start", command=on_start)
        self._skip_btn.configure(text="Skip", command=on_start)
        self._completion_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        self.configure(fg_color=("#fff3e0", "#2c1a00"))

    def show_normal(self):
        self._completion_frame.grid_forget()
        self._dot.grid(row=0, column=0, padx=(12, 4), pady=(14, 0))
        self._clock_label.grid(row=0, column=1, sticky="w", pady=(14, 0))
        self._name_label.grid(row=1, column=1, sticky="w")
        btn_frame = self._normal_widgets[3]
        btn_frame.grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=(14, 0))
        self.configure(fg_color=("#d7f2da", "#12351a"))
