from utils.keys import is_typing_widget


def make(cls: str, name: str):
    return type(name, (), {"winfo_class": lambda self: cls})()


def test_entry_like_widgets_block_shortcuts():
    assert is_typing_widget(make("Entry", "CTkEntry"))
    assert is_typing_widget(make("TEntry", "Anything"))
    assert is_typing_widget(make("Text", "CTkTextbox"))


def test_buttons_and_controls_block_space():
    assert is_typing_widget(make("TButton", "CTkButton"))
    assert is_typing_widget(make("TCheckbutton", "CTkCheckBox"))
    assert is_typing_widget(make("TTkSpinbox", "CTkSwitch"))


def test_plain_frames_allow_shortcuts():
    assert not is_typing_widget(make("Frame", "TimerView"))
    assert not is_typing_widget(make("CTkFrame", "Dashboard"))
    assert not is_typing_widget(make("Label", "CTkLabel"))


def test_broken_widget_fails_closed():
    class Broken:
        def winfo_class(self) -> str:
            raise RuntimeError("gone")

    assert is_typing_widget(Broken())
