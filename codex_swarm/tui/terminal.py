"""Best-effort startup sizing for a classic Windows console, not unrelated windows."""

from __future__ import annotations
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
import sys


class Coord(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class Rect(ctypes.Structure):
    _fields_ = [(name, ctypes.c_short) for name in ("Left", "Top", "Right", "Bottom")]


class BufferInfo(ctypes.Structure):
    _fields_ = [
        ("size", Coord),
        ("cursor", Coord),
        ("attributes", wintypes.WORD),
        ("window", Rect),
        ("maximum", Coord),
    ]


@dataclass
class ResizeResult:
    resized: bool = False
    size: tuple[int, int] | None = None
    notice: str = ""


class WindowsConsole:
    def __init__(self):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.GetStdHandle.argtypes = [wintypes.DWORD]
        self.api.GetStdHandle.restype = wintypes.HANDLE
        self.api.GetConsoleScreenBufferInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(BufferInfo),
        ]
        self.api.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
        self.api.GetLargestConsoleWindowSize.argtypes = [wintypes.HANDLE]
        self.api.GetLargestConsoleWindowSize.restype = Coord
        self.api.SetConsoleScreenBufferSize.argtypes = [wintypes.HANDLE, Coord]
        self.api.SetConsoleScreenBufferSize.restype = wintypes.BOOL
        self.api.SetConsoleWindowInfo.argtypes = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(Rect),
        ]
        self.api.SetConsoleWindowInfo.restype = wintypes.BOOL
        self.api.GetConsoleWindow.restype = wintypes.HWND
        self.handle = self.api.GetStdHandle(-11 & 0xFFFFFFFF)

    def visible(self) -> bool:
        # A pseudoconsole may expose a hidden message-only console handle;
        # changing its buffer does not resize the actual terminal application.
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        user.IsWindowVisible.restype = wintypes.BOOL
        return bool(user.IsWindowVisible(self.api.GetConsoleWindow()))

    def dimensions(self) -> tuple[int, int, int, int]:
        info = BufferInfo()
        if not self.api.GetConsoleScreenBufferInfo(self.handle, ctypes.byref(info)):
            raise OSError(ctypes.get_last_error(), "Console size unavailable")
        return (
            info.window.Right - info.window.Left + 1,
            info.window.Bottom - info.window.Top + 1,
            info.size.X,
            info.size.Y,
        )

    def largest(self) -> tuple[int, int]:
        size = self.api.GetLargestConsoleWindowSize(self.handle)
        return size.X, size.Y

    def set_buffer(self, width: int, height: int) -> bool:
        return bool(
            self.api.SetConsoleScreenBufferSize(self.handle, Coord(width, height))
        )

    def set_window(self, width: int, height: int) -> bool:
        rect = Rect(0, 0, width - 1, height - 1)
        return bool(
            self.api.SetConsoleWindowInfo(self.handle, True, ctypes.byref(rect))
        )


def resize_with_backend(console, requested: tuple[int, int]) -> ResizeResult:
    current_w, current_h, buffer_w, buffer_h = console.dimensions()
    max_w, max_h = console.largest()
    if min(max_w, max_h) <= 0:
        return ResizeResult(
            notice="Terminal sizing unavailable; artwork remains scrollable."
        )
    width = min(max(current_w, requested[0]), max_w)
    height = min(max(current_h, requested[1]), max_h)
    notice = ""
    if width < requested[0] or height < requested[1]:
        notice = "Artwork exceeds the display; scroll the artwork panel to see it all."
    if (width, height) == (current_w, current_h):
        return ResizeResult(size=(width, height), notice=notice)
    # Grow the buffer before the window; never shrink/discard existing contents.
    if width > buffer_w or height > buffer_h:
        if not console.set_buffer(max(width, buffer_w), max(height, buffer_h)):
            return ResizeResult(
                notice="Could not grow console buffer; artwork remains scrollable."
            )
    if not console.set_window(width, height):
        return ResizeResult(
            notice="Terminal refused resizing; artwork remains scrollable."
        )
    return ResizeResult(True, (width, height), notice)


def fit_terminal(requested: tuple[int, int]) -> ResizeResult:
    if os.name != "nt" or not sys.stdout.isatty() or os.environ.get("WT_SESSION"):
        return ResizeResult(
            notice=f"Recommended terminal: {requested[0]} columns × {requested[1]} rows; artwork is scrollable if needed."
        )
    try:
        console = WindowsConsole()
        if not console.visible():
            return ResizeResult(
                notice=f"This terminal controls its own size. Recommended: {requested[0]} × {requested[1]}; artwork stays scrollable."
            )
        return resize_with_backend(console, requested)
    except (OSError, AttributeError, ValueError):
        return ResizeResult(
            notice="Terminal sizing unavailable; artwork remains scrollable."
        )
