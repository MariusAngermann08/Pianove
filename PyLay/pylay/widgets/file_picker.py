import subprocess
import sys
import threading
import queue
from typing import Callable, List, Optional

import pygame
from pylay.core.element import UIElement


def _parse_filters(filters: List[str]):
    result = []
    for f in filters:
        if "|" in f:
            label, exts = f.split("|", 1)
            result.append((label.strip(), exts.strip()))
        else:
            result.append((f.strip(), "*"))
    return result or [("All files", "*")]


def _pick_tkinter(title: str, filetypes) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    # On Windows, bring the dialog to the front.
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return path or ""


def _pick_zenity(title: str, filters: List[str]) -> Optional[str]:
    try:
        cmd = ["zenity", "--file-selection", f"--title={title}"]
        for f in filters:
            cmd += ["--file-filter", f]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    except Exception:
        return None


class FilePicker(UIElement):
    def __init__(self,
                 title: str = "Select file",
                 filters: Optional[List[str]] = None,
                 **kwargs):
        kwargs.setdefault("width", 0)
        kwargs.setdefault("height", 0)
        super().__init__(**kwargs)
        self.title   = title
        self.filters: List[str] = filters or []
        self._q: queue.SimpleQueue = queue.SimpleQueue()

    def pick(self, callback: Callable[[str], None]) -> None:
        title   = self.title
        filters = self.filters

        def _worker():
            path: str = ""
            try:
                filetypes = _parse_filters(filters)
                path = _pick_tkinter(title, filetypes)
            except Exception:
                # tkinter unavailable — try zenity (Linux)
                if sys.platform != "win32":
                    result = _pick_zenity(title, filters)
                    path = result if result is not None else ""
            self._q.put((callback, path))

        threading.Thread(target=_worker, daemon=True).start()

    def update(self, dt: float) -> None:
        # Drain all pending results (handles rapid successive picks correctly).
        while True:
            try:
                cb, path = self._q.get_nowait()
                if cb is not None:
                    cb(path)
            except queue.Empty:
                break
        super().update(dt)
