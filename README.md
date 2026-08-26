# Chromodoro

A desktop Pomodoro work tracker that turns focused time into visible project progress.

Built with Python, CustomTkinter, and SQLite. Single executable, no server, data stays local.

![Version](https://img.shields.io/badge/version-1.7.0-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## Features

- **Pomodoro timer** with 25/5 min cycles, long breaks, and session tracking
- **Projects** with daily goals, time invested, and session history
- **Contributions** — log what you accomplished after each focus session
- **Notes** — quick thoughts and ideas, separate from timed contributions
- **Mini mode** — compact always-on-top widget with clock, pause/resume, and quick project switch
- **System tray** — minimize to tray, auto-start after break, live tooltip with remaining time
- **Keyboard shortcuts** — Space to pause/resume, Esc to go back
- **Quick switch** — pause current session and resume another without losing time
- **Exports** — CSV sessions and contributions, SQLite database backup
- **Portable data** — database lives next to the executable, works from a USB drive

## How to use

### First launch

1. Open Chromodoro from the Start menu or double-click `chromodoro.exe`
2. Click **+ New project** to create your first project
3. Click **Focus** on the project card to start a 25-minute session

### During a session

- The timer counts down from 25:00
- **Space** pauses/resumes the timer
- **Pause** button pauses, **End session** stops early
- After 25 minutes, a notification plays and you can log what you accomplished

### Logging contributions

When a session ends, choose:
- **Log & end** — type what you did, it gets saved as a contribution with the session time
- **Skip** — just move on, the session time is still recorded

### Notes

Click **+ Note** in the Notes section of a project to jot down quick thoughts without starting a timer.

### Mini mode

Click **Widget** in the timer nav bar or dashboard footer to open a compact floating window:
- Shows clock, project name, and pause/resume button
- **Drag** anywhere to move it
- **Switch** button to quickly change projects
- **Close** to return to the full window
- When a session ends in mini mode, **Log** or **Skip** directly from the widget

### System tray

Close the window (X button) to minimize to tray. Right-click the tray icon:
- **Open** — restore the main window
- **Mini mode** — open the floating widget
- **Quit** — exit the application

### Settings

Click the gear icon in the header to access:
- Sound alerts (with test button)
- Auto-start focus after break
- Close button minimizes to tray

### Project management

- **Edit** (pencil icon) — change project name, description, or daily goal
- **Archive** (box icon) — hide a project without deleting its data
- Projects with parked sessions show remaining time on the card

## Build from source

### Prerequisites

- Windows 10/11
- Python 3.11+
- Git

### Setup

```bash
git clone https://github.com/your-username/chromodoro.git
cd chromodoro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Run in development

```bash
set PYTHONPATH=src
set PYTHONIOENCODING=utf-8
python src\main.py
```

### Run tests

```bash
set PYTHONPATH=src
set PYTHONIOENCODING=utf-8
python -m pytest -q
python -m ruff check src tests
python -m mypy
```

### Build the executable

```bash
python -m PyInstaller chromodoro.spec --noconfirm --distpath dist --workpath build
```

The executable will be at `dist\chromodoro.exe`.

### Portable mode

Place `chromodoro.exe` in any folder. The database (`chromodoro.db`) is created next to the executable on first launch. Copy the folder to another machine or USB drive and everything works.

## Project structure

```
chromodoro/
├── src/
│   ├── config.py          # App constants and version
│   ├── main.py            # Entry point
│   ├── domain/            # Data models (Project, Session, Contribution)
│   ├── services/          # Business logic (TimerService, SessionService, ProjectService)
│   ├── storage/           # SQLite database layer
│   ├── ui/                # CustomTkinter interface
│   │   ├── app.py         # Main application window
│   │   ├── dashboard.py   # Project cards and overview
│   │   ├── timer_view.py  # Focus/break/paused screens
│   │   ├── project_view.py # Project details and history
│   │   ├── mini_view.py   # Always-on-top mini widget
│   │   ├── focus_bar.py   # Live status bar
│   │   ├── dialogs.py     # Modal dialogs
│   │   └── settings_dialog.py
│   └── utils/             # Formatting, tray, keyboard helpers
├── tests/                 # pytest test suite
├── chromodoro.spec        # PyInstaller build config
├── requirements.txt       # Runtime dependencies
└── requirements-dev.txt   # Development dependencies
```

## License

MIT
