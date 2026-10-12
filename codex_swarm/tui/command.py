from __future__ import annotations
from textual.widgets import Input
from textual import events
from textual.suggester import SuggestFromList

COMMANDS = [
    "help",
    "new",
    "agents",
    "accounts",
    "status",
    "logs",
    "projects",
    "models",
    "mode",
    "theme",
    "ascii",
    "colors",
    "history",
    "clear",
    "settings",
    "reset_settings",
    "cancel",
    "exit",
    "home",
    "stop",
    "retry",
    "resume",
    "review",
    "promote",
    "login",
    "logout",
    "slots",
    "save",
    "back",
]


class CommandInput(Input):
    def __init__(self, history: list[str], **kwargs):
        super().__init__(
            placeholder="help · type a command or menu number",
            suggester=SuggestFromList(COMMANDS, case_sensitive=False),
            **kwargs,
        )
        self.history = list(history)
        self.history_index = len(history)
        self.draft = ""

    async def _on_key(self, event: events.Key) -> None:
        if event.key in {"up", "down"}:
            event.stop()
            event.prevent_default()
            if self.history_index == len(self.history):
                self.draft = self.value
            self.history_index = max(
                0,
                min(
                    len(self.history),
                    self.history_index + (-1 if event.key == "up" else 1),
                ),
            )
            self.value = (
                self.history[self.history_index]
                if self.history_index < len(self.history)
                else self.draft
            )
            self.cursor_position = len(self.value)
        elif event.key == "tab" and self.value:
            matches = [c for c in COMMANDS if c.startswith(self.value)]
            if matches:
                event.stop()
                event.prevent_default()
                self.value = matches[0]
                self.cursor_position = len(self.value)
        else:
            await super()._on_key(event)

    def remember(self, command: str) -> None:
        if not self.history or self.history[-1] != command:
            self.history.append(command)
        self.history = self.history[-200:]
        self.history_index = len(self.history)
