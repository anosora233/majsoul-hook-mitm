from rich.console import RenderableType
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import (
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Pretty,
    RichLog,
)

MAX_MESSAGES = 40
# NOTE: The max size of Messages' ListView


class PrettyScreen(ModalScreen):
    BINDINGS = [("q,escape", "app.pop_screen", "Pop screen")]

    def __init__(self, object) -> None:
        super().__init__()
        self.object = object

    def compose(self) -> ComposeResult:
        yield Pretty(self.object)


class MessageItem(ListItem):
    def __init__(self, text: str, data: dict) -> None:
        super().__init__(Label(text))
        self.data = data


class Tui(App):
    BINDINGS = [("f1", "app.toggle_class('RichLog', '-hidden')", "Notes")]

    DEFAULT_CSS = """
    RichLog {
        background: $surface;
        color: $text;
        height: 35vh;
        dock: bottom;
        layer: notes;
        border-top: hkey $primary;
        offset-y: 0;
        transition: offset 200ms in_out_cubic;
        padding: 0 1 1 1;
    }

    RichLog.-hidden {
        offset-y: 100%;
    }

    ListView {
        padding: 0 1 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield RichLog(highlight=True, markup=True)
            yield ListView()
        yield Footer()

    @on(ListView.Selected)
    def show_data(self, event: ListView.Selected):
        data = event.item.data
        self.push_screen(PrettyScreen(data))

    def add_note(self, content: RenderableType) -> None:
        self.query_one(RichLog).write(content)

    def add_message(self, text: str, data: dict) -> None:
        view = self.query_one(ListView)
        view.append(MessageItem(text, data))
        view.scroll_end(duration=0.1)

        if len(view) > MAX_MESSAGES:
            messages = self.query(MessageItem)
            messages.first().remove()

    def on_mount(self) -> None:
        from .__main__ import main

        main()


app: Tui = Tui().app
if __name__ == "__main__":
    app.run()
