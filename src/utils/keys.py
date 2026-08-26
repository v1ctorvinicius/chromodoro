BLOCKED_TOKENS = (
    "entry",
    "textbox",
    "text",
    "combobox",
    "spinbox",
    "optionmenu",
    "button",
    "checkbox",
    "switch",
    "radiobutton",
    "slider",
)


def is_typing_widget(widget) -> bool:
    try:
        cls = widget.winfo_class()
    except Exception:
        return True
    names = f"{cls} {type(widget).__name__}".lower()
    return any(token in names for token in BLOCKED_TOKENS)
