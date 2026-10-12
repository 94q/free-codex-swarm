import pytest
from unittest.mock import AsyncMock
from textual.widgets import Button, TextArea, Static
from codex_swarm.persistence.config import Config
from codex_swarm.persistence.database import Database
from codex_swarm.tui.app import MENU, SwarmApp
from codex_swarm.tui.command import CommandInput


async def test_confirmed_settings_reset_refreshes_ui(tmp_path):
    c = Config(tmp_path)
    c.value["appearance"]["ascii_enabled"] = False
    c.value["command_history"] = ["help", "theme"]
    c.value["engine"]["mode"] = "eco"
    c.save()
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test(size=(120, 44)) as pilot:
        await app.dispatch("reset_settings")
        assert app.page == "editor"
        with pytest.raises(ValueError, match="Type RESET"):
            app.confirm_reset_settings("no")
        assert c.value["engine"]["mode"] == "eco"
        app.query_one("#editor", TextArea).load_text("RESET")
        await app.action_apply_editor()
        await pilot.pause()
        assert app.page == "home"
        assert app.draft_appearance is None
        assert c.value["engine"]["mode"] == "auto"
        assert c.value["appearance"]["ascii_enabled"]
        assert app.query_one("#command", CommandInput).history == []
        assert "ctr" in str(app.query_one("#banner", Static).render())
        assert list(tmp_path.glob("settings.before-reset-*.json"))
    db.close()


@pytest.mark.parametrize("size", [(120, 44), (160, 70), (80, 24), (42, 18)])
async def test_full_art_and_centered_headings(tmp_path, size):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        rendered = app.query_one("#banner", Static).render()
        assert "ctr" in str(rendered)
        for page in ("home", "theme", "agent_config", "preview"):
            await app.dispatch(page)
            await pilot.pause()
            heading = app.query_one("#heading", Static)
            line = heading.render_lines(heading.region.size.region)[0].text
            assert line.strip()
            left = len(line) - len(line.lstrip())
            right = len(line) - len(line.rstrip())
            assert abs(left - right) <= 1
        app.set_art("\n".join(["X" * 180] * 30))
        await pilot.pause()
        widget = app.query_one("#banner", Static)
        assert widget.styles.height.value == 30
        assert widget.styles.width.value >= 180
        assert str(widget.render()).count("X") == 180 * 30
        assert app.query_one("#command").region.bottom <= size[1]
        await pilot.resize_terminal(188, 62)
        await pilot.pause()
        assert app.query_one("#art_view").region.height == 30
        assert app.query_one("#command").region.bottom <= 62
    db.close()


@pytest.mark.parametrize("theme", ["default", "ice_blue", "cyber_purple"])
async def test_buttons_use_font_safe_borders(tmp_path, theme):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test(size=(100, 38)) as pilot:
        if theme != "default":
            app.select_theme(theme)
        for page, selector in [
            ("agent_config", "#edit_controls Button"),
            ("preview", "#preview_controls Button"),
        ]:
            await app.dispatch(page)
            await pilot.pause()
            for button in app.query(selector).results(Button):
                for state in ("normal", "hover", "focus", "pressed", "disabled"):
                    button.mouse_hover = state == "hover"
                    button.set_class(state == "pressed", "-active")
                    button.disabled = state == "disabled"
                    if state == "focus":
                        button.focus()
                    else:
                        app.set_focus(None)
                    await pilot.pause()
                    assert button.styles.border_top[0] == "blank"
                    assert button.styles.border_bottom[0] == "blank"
                    lines = button.render_lines(button.region.size.region)
                    assert all(strip.text.isascii() for strip in lines)
                    assert str(button.label) in "".join(s.text for s in lines)
                button.disabled = False
    db.close()


@pytest.mark.parametrize("entry", ["menu_shortcut", "prompt_number"])
async def test_home_exit_is_seven_without_settings(tmp_path, monkeypatch, entry):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    safe_exit = AsyncMock()
    monkeypatch.setattr(app, "action_safe_exit", safe_exit)
    async with app.run_test() as pilot:
        assert len(MENU["home"][1]) == 7
        assert MENU["home"][1][-1] == ("Exit", "exit")
        assert "settings" not in app.actions
        if entry == "menu_shortcut":
            await pilot.press("7")
        else:
            app.query_one("#command", CommandInput).focus()
            await pilot.press("7", "enter")
        safe_exit.assert_awaited_once()
        # Prompt/session preferences remain accessible without a second menu entry.
        await app.dispatch("settings")
        assert app.editor_callback is not None
        assert '"prompt"' in app.query_one("#editor", TextArea).text
    db.close()


@pytest.mark.parametrize("size", [(120, 45), (80, 24), (42, 18)])
async def test_launch_navigation(tmp_path, size):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert app.page == "home"
        assert app.title == "Codex-Swarm"
        assert app.query_one("#command").region.bottom <= size[1]
        await app.dispatch("6")
        assert app.page == "theme"
        await app.dispatch("2")
        assert app.page == "colors"
        await app.dispatch("home")
        assert app.page == "home"
    db.close()


async def test_customization_roundtrip(tmp_path):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test(size=(100, 38)):
        await app.dispatch("theme")
        app.set_art("  ⣿  \n text  ")
        app.set_color("accent", "#AABBCC")
        assert Config(tmp_path).value["appearance"]["accent"] != "#AABBCC"
        await app.dispatch("save")
        assert Config(tmp_path).value["appearance"]["custom_art"] == "  ⣿  \n text  "
        assert Config(tmp_path).value["appearance"]["accent"] == "#AABBCC"
        app.set_color("accent", "#123456")
        await app.dispatch("back")
        assert app.appearance["accent"] == "#AABBCC"
    db.close()


async def test_prompt_history_and_complete(tmp_path):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test() as pilot:
        p = app.query_one("#command", CommandInput)
        p.focus()
        await pilot.press("h", "e", "l", "p", "enter")
        await pilot.pause()
        assert app.page == "info"
        await pilot.press("up")
        assert p.value == "help"
        await pilot.press("down")
        assert p.value == ""
        await pilot.press("h", "i", "s", "tab")
        assert p.value == "history"
        assert Config(tmp_path).value["command_history"] == ["help"]
    db.close()


async def test_menu_edit_controls(tmp_path):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test():
        await app.dispatch("agent_config")
        assert app.editor_callback
        editor = app.query_one("#editor", TextArea)
        editor.load_text(editor.text.replace('"auto"', '"eco"', 1))
        await app.action_apply_editor()
        assert c.value["engine"]["mode"] == "eco"
        await app.dispatch("accounts")
        await app.dispatch("add_session")
        assert c.value["sessions"]["configured_slots"] == 5
    db.close()


async def test_number_shortcuts_and_preview_buttons(tmp_path):
    c = Config(tmp_path)
    db = Database(tmp_path)
    app = SwarmApp(c, db)
    async with app.run_test(size=(100, 38)) as pilot:
        await pilot.press("6")
        assert app.page == "theme"
        app.set_color("accent", "#BBDDFF")
        app.preview()
        await pilot.pause()
        await pilot.click("#preview_cancel")
        assert app.page == "home"
        assert app.appearance["accent"] == "#98FB98"
        app.set_color("accent", "#BBDDFF")
        app.preview()
        await pilot.pause()
        await pilot.click("#preview_save")
        assert Config(tmp_path).value["appearance"]["accent"] == "#BBDDFF"
    db.close()
