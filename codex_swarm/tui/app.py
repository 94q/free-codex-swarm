from __future__ import annotations
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from typing import Callable
from rich.text import Text
from textual import on, events
from textual.app import App, ComposeResult
from textual.containers import (
    Horizontal,
    HorizontalScroll,
    VerticalScroll,
    ScrollableContainer,
)
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    OptionList,
    RichLog,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option
from codex_swarm.core.orchestrator import Orchestrator
from codex_swarm.core.security import safe_text, redact
from codex_swarm.integrations.codex_cli import CodexCLI, spawn_options, kill_tree
from codex_swarm.integrations.git_manager import project_path
from codex_swarm.persistence.config import (
    Config,
    THEMES,
    appearance,
    validate_appearance,
)
from codex_swarm.persistence.database import Database
from codex_swarm.tui.banner import banner, box, gradient, BUILTINS, art_size
from codex_swarm.tui.command import CommandInput

MENU = {
    "home": (
        "COMMAND CENTER",
        [
            ("Start New Task", "new"),
            ("Agent Configuration", "agent_config"),
            ("Account / Session Management", "accounts"),
            ("Projects", "projects"),
            ("Task History", "history"),
            ("Customize Interface", "theme"),
            ("Exit", "exit"),
        ],
    ),
    "theme": (
        "UI CUSTOMIZATION",
        [
            ("Change ASCII Art", "ascii"),
            ("Change Colors", "colors"),
            ("Change Gradient", "gradient"),
            ("Select Theme", "themes"),
            ("Preview Changes", "preview"),
            ("Reset to Default", "reset_theme"),
            ("Save Settings", "save"),
            ("Back (discard unsaved)", "back"),
        ],
    ),
    "ascii": (
        "ASCII ART SETTINGS",
        [
            ("Use Default ASCII Art", "default_art"),
            ("Select Built-in ASCII Art", "builtins"),
            ("Import ASCII Art From File", "import_art"),
            ("Paste Custom ASCII Art", "paste_art"),
            ("Edit Current ASCII Art", "edit_art"),
            ("Preview ASCII Art", "preview"),
            ("Remove ASCII Art", "remove_art"),
            ("Back", "theme"),
        ],
    ),
    "colors": (
        "COLORS",
        [
            ("Background Color", "color:background"),
            ("Main Text Color", "color:text"),
            ("Accent Color", "color:accent"),
            ("Secondary Accent", "color:secondary"),
            ("Border Color", "color:border"),
            ("Error Color", "color:error"),
            ("Warning Color", "color:warning"),
            ("Preview", "preview"),
            ("Back", "theme"),
        ],
    ),
    "accounts": (
        "ACCOUNT / SESSION MANAGER",
        [
            ("Add Account / Session", "add_session"),
            ("Remove Account / Session", "remove_session"),
            ("View Connected Sessions", "session_status"),
            ("Configure Active Session Count", "slots"),
            ("Assign Brain Session", "brain_session"),
            ("Configure Worker Sessions", "session_config"),
            ("Authentication Status / Login / Logout", "session_status"),
            ("Back", "home"),
        ],
    ),
    "projects": (
        "PROJECTS",
        [
            ("Select Project", "select_project"),
            ("Add Git Project", "add_project"),
            ("Remove Saved Project", "remove_project"),
            ("Back", "home"),
        ],
    ),
}


class SwarmApp(App):
    TITLE = "Codex-Swarm"
    CSS = """
    Screen { background: #0B0B0B; color: #FFFFFF; layout: vertical; }
    #art_view { height: auto; margin: 0 1; scrollbar-size: 1 1; }
    #banner { height: auto; }
    #heading { width: 100%; height: 2; text-align: center; content-align: center top; text-style: bold; }
    #body { height: 1fr; margin: 0 2; border: double #98FB98; padding: 0 1; }
    #menu { height: auto; max-height: 20; border: none; background: transparent; }
    #details { height: auto; padding: 1 1; }
    #agents { height: auto; max-height: 12; margin-bottom: 1; }
    #editor { height: 1fr; min-height: 8; border: round #789487; }
    #edit_controls, #preview_controls { height: 3; }
    #preview_controls Button { min-width: 8; }
    /* Textual's tall borders use glyphs missing from common Windows fonts.
       Blank borders keep the button height and theme without those glyphs,
       including when the built-in hover/pressed styles are applied. */
    Button { margin-right: 1; min-width: 10; border: blank transparent !important; }
    #logs { height: 1fr; min-height: 5; border-top: solid #789487; }
    #statusbar { height: 1; margin: 0 2; color: #789487; }
    #shell { height: 3; dock: bottom; padding: 0 2; }
    #identity { width: auto; max-width: 45%; height: 3; content-align: left middle; color: #98FB98; }
    #command { width: 1fr; border: none; background: transparent; padding: 1 0; }
    #hint { height: 1; dock: bottom; text-align: center; color: #789487; }
    .hidden { display: none; }
    """
    BINDINGS = [
        ("ctrl+c", "safe_exit", "Exit"),
        ("ctrl+n", "new_task", "New task"),
        ("ctrl+l", "command", "Command"),
        ("escape", "home", "Home"),
        ("ctrl+enter", "apply_editor", "Apply"),
    ]

    def __init__(self, config: Config | None = None, db: Database | None = None):
        super().__init__()
        self.config = config or Config()
        self.db = db or Database(self.config.root)
        self.engine: Orchestrator | None = None
        self.page = "home"
        self.actions: list[str] = []
        self.draft_appearance: dict | None = None
        self.editor_callback: Callable | None = None
        self.edit_return = "home"
        self.runner: asyncio.Task | None = None
        self.auth_process = None
        self.current_agent = ""
        self.current_history = ""
        self.last_events: list[tuple[str, dict]] = []
        self.startup_notice = ""

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="art_view"):
            yield Static(id="banner", markup=False)
        yield Static("Codex-Swarm", id="heading", markup=False)
        with VerticalScroll(id="body"):
            yield OptionList(id="menu")
            yield Static(id="details", markup=False)
            yield DataTable(id="agents", cursor_type="row", classes="hidden")
            yield TextArea(id="editor", classes="hidden", show_line_numbers=True)
            with Horizontal(id="edit_controls", classes="hidden"):
                yield Button("Apply", id="apply", variant="success")
                yield Button("Cancel", id="discard")
            with HorizontalScroll(id="preview_controls", classes="hidden"):
                yield Button("Apply", id="preview_apply")
                yield Button("Save", id="preview_save", variant="success")
                yield Button("Cancel", id="preview_cancel")
                yield Button("Reset", id="preview_reset")
            yield RichLog(
                id="logs",
                markup=False,
                highlight=False,
                max_lines=1500,
                wrap=True,
                classes="hidden",
            )
        yield Static(
            "Ready · No API key required · No account pooling",
            id="statusbar",
            markup=False,
        )
        with Horizontal(id="shell"):
            yield Label(id="identity", markup=False)
            yield CommandInput(self.config.value["command_history"], id="command")
        yield Static(
            "↑↓ navigate / history   Enter select   Ctrl+L command   Ctrl+N task   Esc home",
            id="hint",
        )

    def on_mount(self) -> None:
        self.db.recover()
        self.apply_theme()
        self.show_menu("home")
        self.query_one("#agents", DataTable).add_columns(
            "Agent", "State", "Model / effort", "Elapsed"
        )
        self.set_interval(0.5, self.refresh_dashboard)
        if self.config.warning:
            self.notify(self.config.warning, severity="warning", timeout=12)
        if self.startup_notice:
            self.query_one("#statusbar", Static).update(self.startup_notice)

    @property
    def appearance(self) -> dict:
        return (
            self.draft_appearance
            if self.draft_appearance is not None
            else self.config.value["appearance"]
        )

    def appearance_draft(self) -> dict:
        if self.draft_appearance is None:
            self.draft_appearance = copy.deepcopy(self.config.value["appearance"])
        return self.draft_appearance

    def apply_theme(self) -> None:
        a = self.appearance
        self.screen.styles.background = a["background"]
        self.screen.styles.color = a["text"]
        self.query_one("#body").styles.border = ("double", a["border"])
        for selector in ("#identity", "#command", "#heading"):
            self.query_one(selector).styles.color = a["accent"]
        self.query_one("#statusbar").styles.color = a["secondary"]
        self.query_one("#identity", Label).update(
            f"{self.config.value['prompt']['username']}@{self.config.value['prompt']['ip']}:~$ "
        )
        # Register an actual Textual theme so focus, buttons, selections, scrollbars and inputs match.
        from textual.theme import Theme

        theme_name = (
            "codex-swarm-"
            + hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest()[:12]
        )
        self.register_theme(
            Theme(
                name=theme_name,
                primary=a["accent"],
                secondary=a["secondary"],
                accent=a["accent"],
                foreground=a["text"],
                background=a["background"],
                surface=a["background"],
                panel=a["background"],
                error=a["error"],
                warning=a["warning"],
                success=a["accent"],
                dark=True,
            )
        )
        self.theme = theme_name
        self.refresh_banner()
        if self.page in MENU:
            self.query_one("#heading", Static).update(
                gradient("Codex-Swarm  /  " + MENU[self.page][0], a, "headings")
            )

    def refresh_banner(
        self, width: int | None = None, height: int | None = None
    ) -> None:
        width = self.size.width if width is None else width
        height = self.size.height if height is None else height
        art_width, art_height = art_size(self.appearance)
        view = self.query_one("#art_view", ScrollableContainer)
        # On constrained displays keep the complete art scrollable, never swap
        # it for a compact logo. Reserve room for the menu and permanent prompt.
        view.styles.height = min(art_height, max(1, height - 24))
        rendered_width = max(art_width, width - 4)
        widget = self.query_one("#banner", Static)
        widget.styles.width = rendered_width
        widget.styles.height = art_height
        widget.update(banner(self.appearance, rendered_width))

    def on_resize(self, event: events.Resize) -> None:
        if self.is_mounted:
            self.refresh_banner(event.size.width, event.size.height)

    def hide_views(self) -> None:
        for id in (
            "agents",
            "editor",
            "edit_controls",
            "preview_controls",
            "logs",
            "menu",
            "details",
        ):
            self.query_one("#" + id).add_class("hidden")

    def show_menu(self, page: str, details: str = "") -> None:
        self.page = page
        self.editor_callback = None
        self.hide_views()
        title, entries = MENU[page]
        self.actions = [action for label, action in entries]
        menu = self.query_one("#menu", OptionList)
        menu.clear_options()
        menu.add_options(
            [
                Option(Text(f"  {i}.  {label}"), id=str(i))
                for i, (label, _) in enumerate(entries, 1)
            ]
        )
        menu.remove_class("hidden")
        menu.highlighted = 0
        self.query_one("#heading", Static).update(
            gradient("Codex-Swarm  /  " + title, self.appearance, "headings")
        )
        if page == "home":
            details = f"Project: {self.config.value['selected_project'] or 'None selected'}\nMode: {self.config.value['engine']['mode'].upper()} · Permission: {self.config.value['engine']['permission']}\nType help for commands. Original project stays unchanged until explicit promotion."
        if page == "projects":
            details = (
                "\n".join(
                    f"{i + 1}. {p}" for i, p in enumerate(self.config.value["projects"])
                )
                or "No projects added. Add a clean Git repository to get started."
            )
        if page == "accounts":
            details = self.session_summary()
        if details:
            self.query_one("#details", Static).update(Text(details))
            self.query_one("#details").remove_class("hidden")
        menu.focus()

    def display(self, title: str, text: str | Text, page: str = "info") -> None:
        self.page = page
        self.actions = []
        self.editor_callback = None
        self.hide_views()
        self.query_one("#heading", Static).update(
            gradient(title, self.appearance, "headings")
        )
        self.query_one("#details", Static).update(
            text if isinstance(text, Text) else Text(safe_text(text))
        )
        self.query_one("#details").remove_class("hidden")
        self.query_one("#command").focus()

    def edit(
        self,
        title: str,
        value: str,
        callback: Callable,
        help: str = "",
        back: str = "home",
    ) -> None:
        self.display(title, help, "editor")
        self.editor_callback, self.edit_return = callback, back
        self.query_one("#editor", TextArea).load_text(value)
        self.query_one("#editor").remove_class("hidden")
        self.query_one("#edit_controls").remove_class("hidden")
        self.query_one("#editor").focus()

    def edit_json(
        self,
        title: str,
        value: dict,
        callback: Callable,
        help: str = "",
        back: str = "home",
    ) -> None:
        self.edit(
            title,
            json.dumps(value, indent=2, ensure_ascii=False),
            lambda s: callback(json.loads(s)),
            help,
            back,
        )

    async def action_apply_editor(self) -> None:
        if not self.editor_callback:
            return
        try:
            callback, back = self.editor_callback, self.edit_return
            result = callback(self.query_one("#editor", TextArea).text)
            if asyncio.iscoroutine(result):
                await result
            # A callback may deliberately navigate to another editor/dashboard.
            if self.editor_callback is callback:
                self.show_menu(back)
        except Exception as exc:
            self.notify(redact(str(exc)), severity="error", timeout=10)

    @on(Button.Pressed, "#apply")
    async def apply_button(self) -> None:
        await self.action_apply_editor()

    @on(Button.Pressed, "#discard")
    def discard_button(self) -> None:
        self.show_menu(self.edit_return)

    @on(Button.Pressed, "#preview_apply")
    def preview_apply(self) -> None:
        self.apply_theme()
        self.show_menu("theme")
        self.notify("Preview applied for this session; Save persists, Back cancels")

    @on(Button.Pressed, "#preview_save")
    def preview_save(self) -> None:
        self.save_appearance()

    @on(Button.Pressed, "#preview_cancel")
    async def preview_cancel(self) -> None:
        await self.dispatch("back")

    @on(Button.Pressed, "#preview_reset")
    async def preview_reset(self) -> None:
        await self.dispatch("reset_theme")

    async def on_key(self, event: events.Key) -> None:
        if (
            isinstance(self.focused, OptionList)
            and event.character
            and event.character.isdigit()
        ):
            event.stop()
            await self.dispatch(event.character)

    @on(OptionList.OptionSelected, "#menu")
    async def menu_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_index < len(self.actions):
            await self.dispatch(self.actions[event.option_index])

    @on(Input.Submitted, "#command")
    async def command_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        prompt = self.query_one("#command", CommandInput)
        prompt.remember(value)
        prompt.value = ""
        self.config.value["command_history"] = prompt.history
        self.config.save()
        await self.dispatch(value)

    def get_engine(self) -> Orchestrator:
        if self.engine is None:
            self.engine = Orchestrator(self.config, self.db, listener=self.agent_event)
        return self.engine

    def require_idle(self) -> None:
        if (self.engine and self.engine.active) or (
            self.runner and not self.runner.done()
        ):
            raise ValueError(
                "Task is running; wait or cancel before changing execution/session settings"
            )

    def session_summary(self) -> str:
        rows = [
            "Slots are process configurations, NOT pooled accounts.",
            "Blank codex_home shares the existing CLI login. No tokens are read/copied.",
        ]
        for p in self.config.value["sessions"]["profiles"]:
            rows.append(
                f"{p['id']} · {p['display_name']} · {p['role']} · {'enabled' if p['enabled'] else 'disabled'} · {p['preferred_model']} / {p['reasoning']} · {p['codex_home'] or 'default CLI home'}"
            )
        rows.append("Commands: login <session_id>, logout <session_id>, slots <count>")
        return "\n".join(rows)

    async def dispatch(self, command: str) -> None:
        try:
            cmd, _, rest = command.partition(" ")
            cmd = cmd.lower()
            if cmd.isdigit():
                n = int(cmd) - 1
                if not 0 <= n < len(self.actions):
                    raise ValueError("No such menu number on this screen")
                await self.dispatch(self.actions[n])
                return
            if cmd in MENU:
                if cmd in {"theme", "ascii", "colors"}:
                    self.appearance_draft()
                self.show_menu(cmd)
                return
            if cmd == "back":
                self.draft_appearance = None
                self.apply_theme()
                self.show_menu("home")
            elif cmd == "help":
                self.display("COMMAND REFERENCE", HELP)
            elif cmd == "new":
                self.new_task()
            elif cmd in {"agent_config", "settings", "session_config"}:
                self.configure(cmd)
            elif cmd == "reset_settings":
                if (self.runner and not self.runner.done()) or self.auth_process:
                    raise ValueError(
                        "Finish or cancel active work/login before resetting settings"
                    )
                self.edit(
                    "RESET ALL SETTINGS",
                    "",
                    self.confirm_reset_settings,
                    "Type RESET then Apply. Backs up preferences; clears saved projects, custom themes, and command history. Task records and official Codex login are preserved.",
                )
            elif cmd == "mode":
                if not rest:
                    self.edit(
                        "OPERATING MODE",
                        self.config.value["engine"]["mode"],
                        lambda s: self.set_engine("mode", s.strip()),
                        "auto / eco / performance / manual",
                    )
                else:
                    self.set_engine("mode", rest.strip())
                    self.notify("Mode saved")
            elif cmd == "models":
                self.run_worker(self.show_models(), exclusive=True, group="metadata")
            elif cmd == "session_status":
                self.run_worker(self.show_sessions(), exclusive=True, group="metadata")
            elif cmd == "add_session":
                self.require_idle()
                self.config.resize(
                    self.config.value["sessions"]["configured_slots"] + 1
                )
                self.show_menu("accounts")
            elif cmd == "remove_session":
                self.edit(
                    "REMOVE SESSION",
                    "",
                    self.remove_session,
                    "Enter a session ID. Minimum two slots; coordinator cannot be removed.",
                    "accounts",
                )
            elif cmd == "slots":
                if rest:
                    self.require_idle()
                    self.config.resize(int(rest))
                    self.show_menu("accounts")
                else:
                    self.edit(
                        "SESSION COUNT",
                        str(self.config.value["sessions"]["configured_slots"]),
                        self.resize_slots,
                        "Minimum 2; configure the maximum with the settings command. Slots do not increase account allowance.",
                        "accounts",
                    )
            elif cmd == "brain_session":
                self.edit(
                    "ASSIGN BRAIN",
                    "",
                    self.assign_brain,
                    "Enter an enabled session ID.",
                    "accounts",
                )
            elif cmd in {"login", "logout"}:
                if not rest:
                    raise ValueError(f"Use {cmd} <session_id>")
                self.require_idle()
                self.run_worker(
                    self.authenticate(rest.strip(), cmd),
                    group="auth",
                    exclusive=True,
                    exit_on_error=False,
                )
            elif cmd == "add_project":
                self.edit(
                    "ADD PROJECT",
                    "",
                    self.add_project,
                    "Absolute Git root with an initial commit. Nothing is changed or auto-initialized.",
                    "projects",
                )
            elif cmd == "select_project":
                self.edit(
                    "SELECT PROJECT",
                    self.config.value["selected_project"],
                    self.select_project,
                    "Enter saved project number or full path.",
                    "projects",
                )
            elif cmd == "remove_project":
                self.edit(
                    "REMOVE PROJECT REFERENCE",
                    "",
                    self.remove_project,
                    "Enter saved project number. Files are never deleted.",
                    "projects",
                )
            elif cmd == "history":
                self.show_history()
            elif cmd.startswith("history:"):
                self.show_record(cmd.split(":", 1)[1])
            elif cmd in {"status", "agents"}:
                self.dashboard()
            elif cmd == "logs":
                self.show_logs(rest.strip())
            elif cmd in {"resume", "retry", "review"}:
                import re

                if cmd == "retry" and re.fullmatch(r"w[0-9]{1,3}", rest.strip()):
                    self.require_idle()
                    id = self.current_history or (
                        self.engine.task["id"]
                        if self.engine and self.engine.task
                        else ""
                    )
                    if not id:
                        raise ValueError("Select a task first")
                    self.get_engine().retry_agent(id, rest.strip())
                    await self.resume_task(id)
                else:
                    await self.resume_task(rest.strip(), review_only=cmd == "review")
            elif cmd == "stop":
                if not rest or not self.engine or not self.engine.active:
                    raise ValueError("Use stop <running-agent-id>")
                if rest.strip() not in self.engine.cli.processes:
                    raise ValueError("Agent has no running process")
                await self.engine.cancel(rest.strip())
                self.notify("Agent stop requested. Resume task to retry.")
            elif cmd == "cancel":
                if self.auth_process:
                    await kill_tree(self.auth_process)
                    self.auth_process = None
                elif self.engine and self.engine.active:
                    self.edit(
                        "CANCEL TASK",
                        "",
                        self.confirm_cancel,
                        "Type CANCEL then Apply. Worktrees/checkpoints will be preserved.",
                    )
                else:
                    self.notify("No active task")
            elif cmd == "promote":
                id = (
                    rest.strip()
                    or self.current_history
                    or (
                        self.engine.task["id"]
                        if self.engine and self.engine.task
                        else ""
                    )
                )
                if not id:
                    raise ValueError("Use promote <task-id>")
                self.edit(
                    "PROMOTE VALIDATED CHANGES",
                    "",
                    lambda text: self.confirm_promote(text, id),
                    "Type PROMOTE to fast-forward the original checkout. Refuses dirty/moved HEAD or unvalidated results.",
                )
            elif cmd == "clear":
                self.query_one("#logs", RichLog).clear()
                self.last_events.clear()
                self.notify("Display cleared; stored events retained")
            elif cmd == "themes":
                self.show_themes()
            elif cmd.startswith("theme:"):
                self.select_theme(command.split(":", 1)[1])
            elif cmd == "save_theme":
                self.edit(
                    "SAVE NAMED CUSTOM THEME",
                    "",
                    self.save_named_theme,
                    "Save current draft under a new name.",
                    "theme",
                )
            elif cmd == "gradient":
                self.edit_json(
                    "GRADIENT",
                    self.appearance_draft()["gradient"],
                    self.set_gradient,
                    "direction: vertical, vertical_reverse, horizontal, horizontal_reverse\nscope: list of banner, headings, borders. Changes are draft until saved.",
                    "theme",
                )
            elif cmd.startswith("color:"):
                key = cmd.split(":", 1)[1]
                self.edit(
                    "COLOR / " + key,
                    self.appearance_draft()[key],
                    lambda s: self.set_color(key, s.strip()),
                    "Use #RRGGBB. Apply previews; Save Settings persists.",
                    "colors",
                )
            elif cmd == "default_art":
                self.appearance_draft().update(ascii_art="default", ascii_enabled=True)
                self.apply_theme()
                self.show_menu("ascii")
            elif cmd == "builtins":
                self.show_builtins()
            elif cmd.startswith("art:"):
                self.appearance_draft().update(
                    ascii_art=cmd.split(":", 1)[1], ascii_enabled=True
                )
                self.apply_theme()
                self.show_menu("ascii")
            elif cmd in {"paste_art", "edit_art"}:
                a = self.appearance_draft()
                current = (
                    a["custom_art"]
                    if a["ascii_art"] == "custom"
                    else BUILTINS.get(a["ascii_art"], "")
                )
                self.edit(
                    "UNICODE ART EDITOR",
                    current if cmd == "edit_art" else "",
                    self.set_art,
                    "Whitespace preserved. ANSI controls stripped. Ctrl+Enter applies to draft.",
                    "ascii",
                )
            elif cmd == "import_art":
                self.edit(
                    "IMPORT .TXT / .ANS",
                    "",
                    self.import_art,
                    "Absolute UTF-8 file path. Legacy ANSI art can use CP437; unsafe control sequences are removed.",
                    "ascii",
                )
            elif cmd == "remove_art":
                self.appearance_draft()["ascii_enabled"] = False
                self.apply_theme()
                self.show_menu("ascii")
            elif cmd == "preview":
                self.preview()
            elif cmd == "reset_theme":
                self.draft_appearance = appearance()
                self.apply_theme()
                self.preview()
            elif cmd == "save":
                self.save_appearance()
            elif cmd == "exit":
                await self.action_safe_exit()
            else:
                raise ValueError(
                    f"Unknown command '{cmd}'. Type help. This prompt never executes OS commands."
                )
        except Exception as exc:
            self.notify(redact(str(exc)), severity="error", timeout=10)

    def set_engine(self, key: str, value) -> None:
        self.require_idle()
        c = copy.deepcopy(self.config.value)
        c["engine"][key] = value
        self.config.save(c)
        self.engine = None

    def configure(self, kind: str) -> None:
        self.require_idle()
        key = (
            "sessions"
            if kind == "session_config"
            else "engine"
            if kind == "agent_config"
            else None
        )
        value = (
            self.config.value[key]
            if key
            else {k: self.config.value[k] for k in ("engine", "sessions", "prompt")}
        )

        def save(data):
            self.require_idle()
            c = copy.deepcopy(self.config.value)
            if key:
                c[key] = data
            else:
                c.update(data)
            self.config.save(c)
            self.engine = None
            self.apply_theme()

        self.edit_json(
            kind.replace("_", " ").upper(),
            value,
            save,
            "Editable validated preferences; Apply saves. Never enter credentials.\n"
            "Modes: auto/eco/performance/manual. Permissions: read-only/workspace-write.\n"
            "Windows sandbox: elevated (default) or unelevated (restricted-token fallback with weaker network isolation); never switches automatically.\n"
            "Models: auto or exact discovered ID (models command). Blank codex_home shares existing CLI authentication.\n"
            "To isolate login, enter a new absolute CODEX_HOME directory, then login <session_id>. "
            "Manual mode uses each worker profile's preferred_model and reasoning. Slot count and profiles must match.",
            "accounts" if key == "sessions" else "home",
        )

    def resize_slots(self, text: str) -> None:
        self.require_idle()
        self.config.resize(int(text.strip()))

    def remove_session(self, id: str) -> None:
        self.require_idle()
        c = copy.deepcopy(self.config.value)
        profiles = c["sessions"]["profiles"]
        p = next((p for p in profiles if p["id"] == id.strip()), None)
        if p is None:
            raise ValueError("Unknown session")
        if p["role"] == "coordinator":
            raise ValueError("Assign another coordinator first")
        profiles.remove(p)
        c["sessions"]["configured_slots"] = len(profiles)
        self.config.save(c)

    def assign_brain(self, id: str) -> None:
        self.require_idle()
        c = copy.deepcopy(self.config.value)
        chosen = next(
            (
                p
                for p in c["sessions"]["profiles"]
                if p["id"] == id.strip() and p["enabled"]
            ),
            None,
        )
        if not chosen:
            raise ValueError("Choose an enabled session")
        for p in c["sessions"]["profiles"]:
            if p["role"] == "coordinator":
                p["role"] = "worker"
        chosen["role"] = "coordinator"
        self.config.save(c)

    async def show_sessions(self) -> None:
        try:
            self.display("SESSION STATUS", "Checking official CLI authentication…")
            cli = CodexCLI(self.config.value["engine"]["codex_binary"])
            cache = {}
            lines = [self.session_summary(), "\nObserved authentication:"]
            for p in self.config.value["sessions"]["profiles"]:
                home = p["codex_home"]
                if home not in cache:
                    cache[home] = await cli.auth_status(home)
                lines.append(
                    f"{p['id']}: {cache[home]} (shared-home slots share this login)"
                )
                if self.engine and self.engine.task:
                    assigned = [
                        (id, a)
                        for id, a in self.engine.task["agents"].items()
                        if a.get("session") == p["id"]
                    ]
                    for id, a in assigned:
                        lines.append(
                            f"  {id}: {a['status']} · {a.get('model')} / {a.get('effort')} · error: {a.get('error', 'none')}"
                        )
            self.display("SESSION STATUS", "\n".join(lines))
        except Exception as exc:
            self.display("SESSION STATUS FAILED", redact(str(exc)))

    async def show_models(self) -> None:
        self.display(
            "MODEL CATALOG",
            "Discovering models and supported reasoning via official app-server…",
        )
        try:
            p = next(
                p
                for p in self.config.value["sessions"]["profiles"]
                if p["enabled"] and p["role"] == "coordinator"
            )
            data = await CodexCLI(self.config.value["engine"]["codex_binary"]).metadata(
                p["codex_home"]
            )
            lines = [data["catalog_note"], ""]
            for m in data["models"]:
                lines.append(
                    f"{m['model']} — {', '.join(e['reasoningEffort'] for e in m['supportedReasoningEfforts'])}"
                )
            limits = data.get("limits", {})
            windows = limits.get("rateLimitsByLimitId") or {
                "default": limits.get("rateLimits")
            }
            lines.append("\nObserved account usage (not a per-task allowance):")
            for name, bucket in windows.items():
                if not bucket:
                    continue
                for w in ("primary", "secondary"):
                    val = bucket.get(w)
                    if val:
                        lines.append(
                            f"{name}/{w}: {val.get('usedPercent', 'unavailable')}% used; window {val.get('windowDurationMins', '?')} min; reset Unix UTC {val.get('resetsAt', 'unavailable')}"
                        )
            if limits.get("unavailable"):
                lines.append("Telemetry unavailable: " + str(limits["unavailable"]))
            self.display("DISCOVERED MODELS / USAGE", "\n".join(lines))
        except Exception as exc:
            self.display("MODEL DISCOVERY FAILED", redact(str(exc)))

    async def authenticate(self, id: str, action: str) -> None:
        self.require_idle()
        p = next(
            (p for p in self.config.value["sessions"]["profiles"] if p["id"] == id),
            None,
        )
        if not p:
            raise ValueError("Unknown session ID")
        if action == "logout":
            self.edit(
                "SIGN OUT",
                "",
                lambda text: self.confirm_logout(text, p),
                "Type LOGOUT. Every slot using the same CODEX_HOME will be signed out.",
                "accounts",
            )
            return
        from codex_swarm.core.security import child_env

        if p["codex_home"]:
            Path(p["codex_home"]).mkdir(parents=True, exist_ok=True)
        self.display(
            "OFFICIAL CODEX LOGIN",
            "Follow the browser sign-in opened by Codex. No password/token is collected by Codex-Swarm.\nType cancel to stop waiting.",
        )
        cli = CodexCLI(self.config.value["engine"]["codex_binary"])
        self.auth_process = await asyncio.create_subprocess_exec(
            cli.binary,
            "login",
            env=child_env(p["codex_home"]),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            **spawn_options(),
        )
        proc = self.auth_process
        try:
            await asyncio.wait_for(proc.wait(), 300)
            state = await cli.auth_status(p["codex_home"])
            self.display(
                "LOGIN RESULT",
                state
                + "\nIf the browser did not open, run codex login in your terminal with this session's CODEX_HOME. No auth output is logged.",
            )
        except asyncio.CancelledError:
            await kill_tree(proc)
            raise
        except TimeoutError:
            await kill_tree(proc)
            self.display(
                "LOGIN TIMED OUT",
                "Run official codex login interactively; no credentials were copied.",
            )
        finally:
            self.auth_process = None

    async def confirm_logout(self, text: str, p: dict) -> None:
        if text.strip() != "LOGOUT":
            raise ValueError("Type LOGOUT to confirm")
        from codex_swarm.core.security import child_env

        cli = CodexCLI(self.config.value["engine"]["codex_binary"])
        proc = await asyncio.create_subprocess_exec(
            cli.binary,
            "logout",
            env=child_env(p["codex_home"]),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            **spawn_options(),
        )
        try:
            await asyncio.wait_for(proc.wait(), 20)
        finally:
            await kill_tree(proc)
        self.notify("Sign-out finished; refresh Authentication Status")

    def add_project(self, text: str) -> None:
        path = str(project_path(text.strip().strip('"')))
        if path not in self.config.value["projects"]:
            self.config.value["projects"].append(path)
        self.config.value["selected_project"] = path
        self.config.save()

    def select_project(self, text: str) -> None:
        text = text.strip().strip('"')
        if text.isdigit():
            text = self.config.value["projects"][int(text) - 1]
        self.add_project(text)

    def remove_project(self, text: str) -> None:
        p = self.config.value["projects"].pop(int(text.strip()) - 1)
        if self.config.value["selected_project"] == p:
            self.config.value["selected_project"] = ""
        self.config.save()

    def new_task(self) -> None:
        self.require_idle()
        p = self.config.value["selected_project"]
        if not p:
            self.show_menu("projects", "Add/select a project first.")
            return
        self.edit(
            "NEW TASK / ONE SHARED OBJECTIVE",
            "",
            self.submit_task,
            f"Project: {p}\nMode: {self.config.value['engine']['mode']} · Permission: {self.config.value['engine']['permission']}\n"
            "Apply authorizes bounded Codex runs using your ChatGPT allowance. Editing, when enabled, is sandboxed in isolated worktrees.\nOriginal checkout is not promoted automatically. Multiline input supported.",
        )

    async def submit_task(self, prompt: str) -> None:
        if not prompt.strip():
            raise ValueError("Enter an objective")
        engine = self.get_engine()
        self.dashboard()
        self.runner = asyncio.create_task(
            self.execute(engine, self.config.value["selected_project"], prompt)
        )

    async def execute(
        self, engine: Orchestrator, project: str, prompt: str, resume: str = ""
    ) -> None:
        try:
            result = await engine.run(project, prompt, resume=resume)
            self.notify(
                f"Task {result['id']}: {result['status']}",
                severity="error" if result["status"] == "failed" else "information",
                timeout=10,
            )
        except Exception as exc:
            self.notify(redact(str(exc)), severity="error", timeout=12)
        self.refresh_dashboard()

    async def resume_task(self, id: str, review_only: bool = False) -> None:
        self.require_idle()
        id = (
            id
            or self.current_history
            or (self.engine.task["id"] if self.engine and self.engine.task else "")
        )
        if not id:
            raise ValueError("Use resume <task-id> (or select a history item)")
        record = self.db.get(id)
        if review_only:
            if record["status"] not in {"ready", "needs_review"}:
                raise ValueError("Complete workers first; use resume")
            record["status"] = "needs_review"
            self.db.save(record)
        engine = self.get_engine()
        self.dashboard()
        self.runner = asyncio.create_task(
            self.execute(engine, record["project"], record["prompt"], id)
        )

    async def confirm_cancel(self, text: str) -> None:
        if text.strip() != "CANCEL":
            raise ValueError("Type CANCEL to confirm")
        await self.engine.cancel()
        self.dashboard()

    async def confirm_promote(self, text: str, id: str) -> None:
        if text.strip() != "PROMOTE":
            raise ValueError("Type PROMOTE to confirm")
        tip = await self.get_engine().promote(id)
        self.notify("Promoted " + tip[:12])
        self.show_record(id)

    def dashboard(self) -> None:
        self.current_history = ""
        self.display("LIVE AGENT DASHBOARD", "No task started yet.", "dashboard")
        self.query_one("#agents").remove_class("hidden")
        self.query_one("#logs").remove_class("hidden")
        self.refresh_dashboard()

    def refresh_dashboard(self) -> None:
        if not self.engine or not self.engine.task:
            return
        t = self.engine.task
        self.query_one("#statusbar", Static).update(
            Text(
                f"{t['id']} · {t['status'].upper()} · {t['invocations']} invocations · {len(self.engine.cli.processes)} active processes"
            )
        )
        if self.page != "dashboard":
            return
        done = sum(
            a["status"] == "completed"
            for k, a in t["agents"].items()
            if k.startswith("w")
        )
        total = len(t["plan"]["workers"]) if t.get("plan") else "?"
        self.query_one("#details", Static).update(
            Text(
                f"PROJECT: {t['project']}\nMODE: {t['mode'].upper()}    TASK: {t['prompt'][:500]}\nSTATE: {t['status']} · Workers completed: {done}/{total}\n"
                f"{t.get('error', '')}\nSelect an agent row for detail. Commands: stop <agent>, logs <agent>, cancel, history, promote."
            )
        )
        table = self.query_one("#agents", DataTable)
        cursor = table.cursor_row
        table.clear()
        from datetime import datetime, timezone

        for id, a in t["agents"].items():
            elapsed = (
                (
                    datetime.now(timezone.utc) - datetime.fromisoformat(a["started"])
                ).total_seconds()
                if a["status"] == "running"
                else a.get("elapsed", 0)
            )
            table.add_row(
                id,
                a["status"],
                f"{a.get('model', '?')} / {a.get('effort', '?')}",
                f"{elapsed:.1f}s",
                key=id,
            )
        if table.row_count:
            table.move_cursor(row=min(cursor, table.row_count - 1))

    def agent_event(self, agent: str, event: dict) -> None:
        self.last_events.append((agent, event))
        self.last_events = self.last_events[-500:]
        item = event.get("item", {})
        msg = (
            item.get("command")
            or item.get("text")
            or event.get("message")
            or event.get("status")
            or ""
        )
        line = f"{agent:>8}  {event['type']}  {str(msg)[:1800]}"
        self.query_one("#logs", RichLog).write(
            Text(
                safe_text(line),
                style=self.appearance["error"]
                if event["type"] == "error"
                else self.appearance["text"],
            )
        )

    @on(DataTable.RowSelected, "#agents")
    def agent_selected(self, event: DataTable.RowSelected) -> None:
        id = str(event.row_key.value)
        a = self.engine.task["agents"][id]
        self.current_agent = id
        self.display(
            "AGENT / " + id,
            json.dumps(a, indent=2, ensure_ascii=False)
            + f"\n\nCommands: logs {id}, stop {id}, retry {id}, resume {self.engine.task['id']}, review {self.engine.task['id']}",
        )

    def show_logs(self, agent: str = "") -> None:
        t = (
            self.db.get(self.current_history)
            if self.current_history
            else self.engine.task
            if self.engine
            else None
        )
        if not t:
            raise ValueError("Select a task from history or start one")
        self.display(
            "PERSISTED EVENTS / " + (agent or "ALL"),
            "Events are real, redacted CLI/process events. Token counts come from turn.completed, not estimates.",
        )
        self.query_one("#logs").remove_class("hidden")
        logs = self.query_one("#logs", RichLog)
        logs.clear()
        for e in self.db.events(t["id"], agent):
            logs.write(Text(json.dumps(e, ensure_ascii=False)))

    def show_history(self) -> None:
        self.display(
            "TASK HISTORY",
            "Select a record; resume reuses completed checkpoints and retains failed worktrees.",
        )
        records = self.db.history()
        self.actions = ["history:" + r["id"] for r in records] + ["home"]
        menu = self.query_one("#menu", OptionList)
        menu.clear_options()
        menu.add_options(
            [
                Option(Text(f"{i + 1}. {r['id']}  {r['status']}  {r['prompt'][:65]}"))
                for i, r in enumerate(records)
            ]
            + [Option("Back")]
        )
        menu.remove_class("hidden")
        menu.focus()

    def show_record(self, id: str) -> None:
        self.current_history = id
        t = self.db.get(id)
        self.display(
            "TASK / " + id,
            json.dumps(t, indent=2, ensure_ascii=False)
            + f"\n\nCommands: resume {id}, review {id}, promote {id}, logs",
        )

    def show_themes(self) -> None:
        self.display(
            "SELECT THEME",
            "Built-in themes and named custom themes. Apply previews; save persists.",
        )
        names = list(THEMES) + list(self.config.value["custom_themes"])
        self.actions = ["theme:" + n for n in names] + ["save_theme", "theme"]
        menu = self.query_one("#menu", OptionList)
        menu.clear_options()
        menu.add_options(
            [
                Option(Text(f"{i + 1}. {n.replace('_', ' ').title()}"))
                for i, n in enumerate(names)
            ]
            + [Option("Save named custom theme"), Option("Back")]
        )
        menu.remove_class("hidden")
        menu.focus()

    def select_theme(self, name: str) -> None:
        a = self.appearance_draft()
        if name in THEMES:
            a.update(THEMES[name])
            a["theme"] = name
            a["gradient"]["end"] = a["accent"]
        elif name in self.config.value["custom_themes"]:
            self.draft_appearance = copy.deepcopy(
                self.config.value["custom_themes"][name]
            )
        else:
            raise ValueError("Unknown theme")
        self.apply_theme()
        self.preview()

    def save_named_theme(self, name: str) -> None:
        name = safe_text(name.strip())
        if not name or len(name) > 40 or name in THEMES:
            raise ValueError("Choose a unique name (1-40 characters)")
        self.config.value["custom_themes"][name] = copy.deepcopy(
            self.appearance_draft()
        )
        self.config.save()

    def set_gradient(self, g: dict) -> None:
        a = copy.deepcopy(self.appearance_draft())
        a["gradient"] = g
        validate_appearance(a)
        self.draft_appearance = a
        self.apply_theme()

    def set_color(self, key: str, color: str) -> None:
        a = copy.deepcopy(self.appearance_draft())
        a[key] = color
        validate_appearance(a)
        self.draft_appearance = a
        self.apply_theme()

    def confirm_reset_settings(self, text: str) -> None:
        if text.strip() != "RESET":
            raise ValueError("Type RESET to confirm")
        if (self.runner and not self.runner.done()) or self.auth_process:
            raise ValueError("Cannot reset settings during active work/login")
        self.config.reset()
        self.engine = None
        self.draft_appearance = None
        command = self.query_one("#command", CommandInput)
        command.history = []
        command.history_index = 0
        command.draft = command.value = ""
        self.apply_theme()
        self.show_menu("home")
        self.notify(
            "All preferences reset. Previous settings backed up; task data preserved."
        )

    def set_art(self, text: str) -> None:
        a = copy.deepcopy(self.appearance_draft())
        a.update(custom_art=safe_text(text), ascii_art="custom", ascii_enabled=True)
        validate_appearance(a)
        self.draft_appearance = a
        self.apply_theme()

    def import_art(self, path: str) -> None:
        p = Path(path.strip().strip('"')).expanduser()
        if p.suffix.lower() not in {".txt", ".ans"}:
            raise ValueError("Choose .txt or .ans artwork")
        if p.stat().st_size > 200_000:
            raise ValueError("Artwork file too large")
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp437")
        self.set_art(text)

    def show_builtins(self) -> None:
        self.display(
            "BUILT-IN ARTWORK",
            "Select a banner; missing reference artwork can be imported.",
        )
        self.actions = ["art:" + n for n in BUILTINS] + ["ascii"]
        menu = self.query_one("#menu", OptionList)
        menu.clear_options()
        menu.add_options(
            [Option(Text(f"{i + 1}. {name}")) for i, name in enumerate(BUILTINS)]
            + [Option("Back")]
        )
        menu.remove_class("hidden")
        menu.focus()

    def preview(self) -> None:
        a = self.appearance_draft()
        t = box(
            [
                "Codex-Swarm — APPEARANCE PREVIEW",
                "1. Start New Task",
                "2. Agent Configuration",
                "BRAIN    [sample: coordinating]",
                "WORKER   [sample: investigating]",
                "LOG: sample validation completed",
                "NOTICE: preview only — not a real agent run",
            ],
            a,
            self.size.width - 12,
        )
        t.append("\n\nSample warning", style=a["warning"])
        t.append("   Sample error", style=a["error"])
        t.append(
            "\nApplied to this preview. Commands: save (persist), back (cancel), reset_theme (reset), theme (edit)."
        )
        self.display("LIVE APPEARANCE PREVIEW", t)
        self.query_one("#preview_controls").remove_class("hidden")

    def save_appearance(self) -> None:
        if self.draft_appearance is not None:
            self.config.value["appearance"] = copy.deepcopy(self.draft_appearance)
            self.config.save()
            self.draft_appearance = None
        self.apply_theme()
        self.notify("Appearance saved")
        self.show_menu("home")

    async def action_safe_exit(self) -> None:
        if self.engine and self.engine.active:
            self.edit(
                "EXIT AND CANCEL",
                "",
                self.confirm_exit,
                "Type EXIT to cancel active processes and preserve checkpoints before closing.",
            )
            return
        if self.auth_process:
            await kill_tree(self.auth_process)
        self.exit()

    async def confirm_exit(self, text: str) -> None:
        if text.strip() != "EXIT":
            raise ValueError("Type EXIT to confirm")
        await self.engine.cancel()
        if self.runner:
            await self.runner
        self.exit()

    def action_command(self) -> None:
        self.query_one("#command").focus()

    def action_home(self) -> None:
        self.draft_appearance = None
        self.apply_theme()
        self.show_menu("home")

    def action_new_task(self) -> None:
        try:
            self.new_task()
        except Exception as exc:
            self.notify(str(exc), severity="error")


HELP = """Codex-Swarm commands (not an OS shell)
help         this reference          new          multiline objective
agents       live dashboard          status       current task
logs [agent] persisted event logs    history      saved tasks/reports
projects     select/add Git root     accounts     independent session slots
models       discover models/usage   mode [name]  auto/eco/performance/manual
settings     engine/session/prompt   agent_config model/effort/budgets/permissions
theme        customization           ascii        import/paste/edit Unicode art
colors       change palette          save         persist appearance draft
back         discard preview         clear        clear visible logs, not history
slots <n>    change slot count       login <id>   official browser authentication
logout <id>  confirmed sign-out      stop <agent> stop one real process tree
cancel       confirmed cancellation  resume <id>  rerun unfinished checkpoints
retry <id>   retry task or worker    review <id>  re-run final review (uses budget)
promote <id> confirmed fast-forward  exit         safe exit
home         main menu               reset_settings confirmed preference reset

Menu numbers work in this prompt. Arrow keys navigate the focused menu;
Up/Down in the prompt recall persisted command history; Tab autocompletes.
Ctrl+L focuses prompt. Ctrl+Enter applies editor. Esc returns home.

Execution requires a clean Git repository with at least one commit.
Set workspace-write in Agent Configuration to authorize sandboxed edits.
An isolated integration branch is retained. Promotion is never automatic.
Read-only is the default; no authentication bypass or paid API fallback.
Resume never increases budgets or changes account identity automatically.
Independent CODEX_HOME logins are optional; slots sharing a home share one account.
"""
