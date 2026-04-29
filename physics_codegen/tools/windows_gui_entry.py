r"""Windows GUI entrypoint for PyInstaller --windowed builds.

When PyInstaller builds with --windowed (console=False), sys.stdout and
sys.stderr are None, and unhandled startup exceptions can disappear without
showing anything to the user. This wrapper:

1. Redirects stdout/stderr to a log file before the real GUI code runs.
2. Installs a sys.excepthook that logs the traceback and shows a message box.
3. Calls through to physics_codegen.gui.main() as before.

Log location: %LOCALAPPDATA%\AxionPhysicsCodegen\error.log
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import traceback
from pathlib import Path


APP_NAME = "AxionPhysicsCodegen"


def _portable_log_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    exe_dir = Path(sys.executable).resolve().parent
    target = exe_dir / "userdata"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return target
    except Exception:
        return None


def _log_dir() -> Path:
    portable = _portable_log_dir()
    if portable is not None:
        return portable
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    target = Path(base) / APP_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def _install_logging() -> Path:
    log_path = _log_dir() / "error.log"
    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)

    class _StreamToLog:
        def __init__(self, level: int) -> None:
            self._level = level
            self._buf = ""

        def write(self, data: str) -> int:
            if not data:
                return 0
            self._buf += data
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line:
                    logging.log(self._level, line)
            return len(data)

        def flush(self) -> None:
            if self._buf:
                logging.log(self._level, self._buf)
                self._buf = ""

    sys.stdout = _StreamToLog(logging.INFO)  # type: ignore[assignment]
    sys.stderr = _StreamToLog(logging.ERROR)  # type: ignore[assignment]
    return log_path


def _install_excepthook(log_path: Path) -> None:
    def hook(exc_type, exc_value, exc_tb) -> None:
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.critical("Unhandled exception:\n%s", tb)
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                f"{APP_NAME} - startup error",
                f"{exc_type.__name__}: {exc_value}\n\nFull traceback written to:\n{log_path}",
            )
            root.destroy()
        except Exception:
            pass

    sys.excepthook = hook


def _main() -> int:
    log_path = _install_logging()
    _install_excepthook(log_path)
    logging.info("%s starting, log=%s", APP_NAME, log_path)
    from physics_codegen.gui import main

    return main() or 0


if __name__ == "__main__":
    raise SystemExit(_main())
