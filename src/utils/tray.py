import threading

from PIL import Image, ImageDraw

try:
    import pystray
except ImportError:
    pystray = None


def _icon_image(running: bool = False) -> Image.Image:
    color = (102, 187, 106, 255) if running else (255, 183, 77, 255)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=color)
    draw.rectangle((29, 14, 35, 34), fill=(255, 255, 255, 230))
    draw.polygon([(33, 32), (46, 39), (42, 45), (31, 36)], fill=(255, 255, 255, 230))
    return img


class TrayController:
    def __init__(self, title: str):
        self._title = title
        self._icon: object | None = None
        self.open_requested = threading.Event()
        self.quit_requested = threading.Event()
        self.mini_requested = threading.Event()
        self._last_tooltip: str | None = None

    @property
    def available(self) -> bool:
        return pystray is not None

    def start(self) -> bool:
        if not self.available or self._icon is not None:
            return self._icon is not None
        menu = pystray.Menu(  # type: ignore[union-attr]
            pystray.MenuItem("Open Chromodoro", self._on_open, default=True),
            pystray.MenuItem("Mini mode", self._on_mini),
            pystray.MenuItem("Quit Chromodoro", self._on_quit),
        )
        icon = pystray.Icon("Chromodoro", _icon_image(), self._title, menu)
        thread = threading.Thread(target=icon.run, daemon=True)
        thread.start()
        self._icon = icon
        return True

    def update_tooltip(self, text: str) -> None:
        if self._icon is None or text == self._last_tooltip:
            return
        try:
            self._icon.title = text  # type: ignore[attr-defined]
            self._last_tooltip = text
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()  # type: ignore[attr-defined]
        except Exception:
            pass
        self._icon = None
        self._last_tooltip = None

    def _on_open(self, *_args: object) -> None:
        self.open_requested.set()

    def _on_mini(self, *_args: object) -> None:
        self.mini_requested.set()

    def _on_quit(self, *_args: object) -> None:
        self.quit_requested.set()
