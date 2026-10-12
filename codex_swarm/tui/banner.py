from __future__ import annotations
from rich.cells import cell_len
from rich.text import Text
from codex_swarm.core.security import safe_text

# User-supplied cat; preserve the original whitespace and artist signature.
ASCII_ART = r'''       :\     /;               _
      ;  \___/  ;             ; ;
     ,:-"'   `"-:.            / ;
_   /,---.   ,---.\   _     _; /
_:>((  |  ) (  |  ))<:_ ,-""_,"
    \`````   `````/""""",-""
     '-.._ v _..-'      )
       / ___   ____,..  \
      / /   | |   | ( \. \
ctr  / /    | |    | |  \ \
     `"     `"     `"    `"'''
BUILTINS = {
    "default": ASCII_ART,
    "compact": " /\\_/\\\n( o.o )\n > ^ <",
    "orbit": "     ╭───────────╮\n  ───┤  S W A R M ├───\n     ╰───────────╯",
}


def rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


def mix(start: str, end: str, ratio: float) -> str:
    a, b = rgb(start), rgb(end)
    return "#" + "".join(f"{int(x + (y - x) * ratio):02x}" for x, y in zip(a, b))


def gradient(text: str, appearance: dict, scope: str = "banner") -> Text:
    g = appearance["gradient"]
    text = safe_text(text)
    if not g["enabled"] or scope not in g["scope"]:
        return Text(
            text,
            style=appearance["text"] if scope == "banner" else appearance["accent"],
            justify="center" if scope == "headings" else "left",
        )
    lines = text.split("\n")
    result = Text(justify="center" if scope == "headings" else "left")
    vertical = g["direction"].startswith("vertical")
    reverse = g["direction"].endswith("reverse")
    for index, line in enumerate(lines):
        if index:
            result.append("\n")
        if vertical:
            ratio = index / max(1, len(lines) - 1)
            result.append(
                line, style=mix(g["start"], g["end"], 1 - ratio if reverse else ratio)
            )
        else:
            column, width = 0, max(1, cell_len(line) - 1)
            for char in line:
                ratio = min(1, column / width)
                result.append(
                    char,
                    style=mix(g["start"], g["end"], 1 - ratio if reverse else ratio),
                )
                column += cell_len(char)
    return result


def artwork(appearance: dict) -> str:
    if not appearance["ascii_enabled"]:
        return ""
    art = (
        appearance["custom_art"]
        if appearance["ascii_art"] == "custom"
        else BUILTINS.get(appearance["ascii_art"], ASCII_ART)
    )
    return safe_text(art).expandtabs(4)


def art_size(appearance: dict) -> tuple[int, int]:
    art = artwork(appearance)
    lines = art.split("\n") if art else []
    return max(map(cell_len, lines), default=0), len(lines)


def recommended_size(appearance: dict) -> tuple[int, int]:
    width, height = art_size(appearance)
    return max(120, width + 8), max(44, height + 32)


def banner(appearance: dict, width: int, height: int | None = None) -> Text:
    if not appearance["ascii_enabled"]:
        return Text("")
    art = artwork(appearance)
    lines = art.split("\n")
    if appearance["ascii_centered"]:
        # Center as a block, retaining the original whitespace and proportions.
        pad = " " * max(0, (width - max(map(cell_len, lines), default=0)) // 2)
        art = "\n".join(pad + line for line in lines)
    return gradient(art, appearance)


def box(lines: list[str], appearance: dict, width: int) -> Text:
    width = max(10, min(width, 70))
    inner = width - 4
    plain = ["╔" + "═" * (width - 2) + "╗"]
    for line in lines:
        t = Text(safe_text(line))
        t.truncate(inner, overflow="ellipsis")
        plain.append("║ " + t.plain + " " * (inner - cell_len(t.plain)) + " ║")
    plain.append("╚" + "═" * (width - 2) + "╝")
    return gradient("\n".join(plain), appearance, "borders")
