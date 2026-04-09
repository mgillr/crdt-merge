# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Progress bar and spinner system for the crdt-merge CLI.

Uses ``rich`` when available and running on an interactive terminal,
otherwise falls back to plain ``\\r``-overwritten lines (TTY) or
periodic status messages (piped).
"""

from __future__ import annotations

import sys
import time
from typing import Any

# ---------------------------------------------------------------------------
# Optional rich detection
# ---------------------------------------------------------------------------

_rich_progress: Any = None
_rich_spinner_col: Any = None
_rich_bar_col: Any = None
_rich_text_col: Any = None
_rich_time_col: Any = None

try:
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    _rich_progress = Progress
    _rich_spinner_col = SpinnerColumn
    _rich_bar_col = BarColumn
    _rich_text_col = TextColumn
    _rich_time_col = TimeRemainingColumn
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BAR_WIDTH = 30
_FILLED = "\u2588"  # █
_EMPTY = "\u2591"   # ░
_PIPE_INTERVAL = 5.0  # seconds between status lines when piped


def _format_time(seconds: float) -> str:
    """Return a compact human-readable duration string."""
    if seconds < 0:
        return "??s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _pct(current: int, total: int | None) -> int:
    if total is None or total <= 0:
        return 0
    return min(int(current * 100 / total), 100)


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------


class ProgressBar:
    """Adaptive progress bar with rich / TTY / pipe backends."""

    def __init__(
        self,
        total: int | None = None,
        desc: str = "",
        stream: Any = sys.stderr,
    ) -> None:
        self.total = total
        self.desc = desc
        self.stream = stream
        self._current = 0
        self._start_time = time.monotonic()
        self._last_pipe_time = self._start_time
        self._finished = False

        try:
            self._is_tty = hasattr(stream, "isatty") and stream.isatty()
        except (ValueError, OSError):
            # Stream is closed (e.g. pytest capture redirect) -- treat as non-TTY
            self._is_tty = False
        self._use_rich = False
        self._rich_ctx: Any = None
        self._rich_task: Any = None

        # Try to set up rich if on a TTY.
        if self._is_tty and _rich_progress is not None:
            try:
                columns = [
                    _rich_text_col("[progress.description]{task.description}"),
                    _rich_bar_col(bar_width=_BAR_WIDTH),
                    _rich_text_col("[progress.percentage]{task.percentage:>3.0f}%"),
                    _rich_time_col(),
                ]
                self._rich_ctx = _rich_progress(*columns, console=None)
                self._rich_ctx.start()
                self._rich_task = self._rich_ctx.add_task(
                    desc, total=total if total is not None else None
                )
                self._use_rich = True
            except Exception:
                self._use_rich = False

    # -- Core API -----------------------------------------------------------

    def update(self, n: int = 1) -> None:
        """Advance the progress bar by *n* steps."""
        if self._finished:
            return
        self._current += n

        if self._use_rich:
            self._rich_ctx.update(self._rich_task, advance=n)
            return

        if self._is_tty:
            self._render_tty()
        else:
            self._render_pipe()

    def finish(self) -> None:
        """Complete the bar and print final stats."""
        if self._finished:
            return
        self._finished = True
        elapsed = time.monotonic() - self._start_time

        if self._use_rich:
            try:
                if self.total is not None:
                    self._rich_ctx.update(
                        self._rich_task, completed=self.total
                    )
                self._rich_ctx.stop()
            except Exception:
                pass
            return

        if self._is_tty:
            # Draw a complete bar.
            bar = _FILLED * _BAR_WIDTH
            prefix = f"[{self.desc}] " if self.desc else ""
            count = f"{self._current}"
            if self.total is not None:
                count = f"{self._current}/{self.total}"
            line = f"\r{prefix}{bar} 100% ({count}) {_format_time(elapsed)}"
            self.stream.write(line)
            self.stream.write("\n")
            self.stream.flush()
        else:
            count = f"{self._current}"
            if self.total is not None:
                count = f"{self._current}/{self.total}"
            pct = _pct(self._current, self.total)
            self.stream.write(
                f"[progress] {count} rows ({pct}%) done in {_format_time(elapsed)}\n"
            )
            self.stream.flush()

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> "ProgressBar":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.finish()

    # -- Private renderers --------------------------------------------------

    def _render_tty(self) -> None:
        pct = _pct(self._current, self.total)
        filled_len = int(_BAR_WIDTH * pct / 100) if self.total else 0
        bar = _FILLED * filled_len + _EMPTY * (_BAR_WIDTH - filled_len)

        prefix = f"[{self.desc}] " if self.desc else ""
        count = f"{self._current}"
        if self.total is not None:
            count = f"{self._current}/{self.total}"

        eta_str = ""
        elapsed = time.monotonic() - self._start_time
        if self.total and self._current > 0:
            remaining = elapsed * (self.total - self._current) / self._current
            eta_str = f" ETA: {_format_time(remaining)}"

        line = f"\r{prefix}{bar} {pct}% ({count}){eta_str}"
        self.stream.write(line)
        self.stream.flush()

    def _render_pipe(self) -> None:
        now = time.monotonic()
        if now - self._last_pipe_time < _PIPE_INTERVAL:
            return
        self._last_pipe_time = now

        count = f"{self._current}"
        if self.total is not None:
            count = f"{self._current}/{self.total}"
        pct = _pct(self._current, self.total)
        self.stream.write(f"[progress] {count} rows ({pct}%)\n")
        self.stream.flush()


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

_SPINNER_FRAMES = "|/-\\"


class Spinner:
    """Indeterminate-progress spinner with rich / TTY fallback."""

    def __init__(
        self,
        desc: str = "",
        stream: Any = sys.stderr,
    ) -> None:
        self.desc = desc
        self.stream = stream
        self._finished = False
        self._frame = 0
        self._start_time = time.monotonic()

        try:
            self._is_tty = hasattr(stream, "isatty") and stream.isatty()
        except (ValueError, OSError):
            # Stream is closed (e.g. pytest capture redirect) -- treat as non-TTY
            self._is_tty = False
        self._use_rich = False
        self._rich_ctx: Any = None
        self._rich_task: Any = None

        if self._is_tty and _rich_progress is not None:
            try:
                columns = [
                    _rich_spinner_col(),
                    _rich_text_col("[progress.description]{task.description}"),
                ]
                self._rich_ctx = _rich_progress(*columns)
                self._rich_ctx.start()
                self._rich_task = self._rich_ctx.add_task(desc, total=None)
                self._use_rich = True
            except Exception:
                self._use_rich = False

    # -- Core API -----------------------------------------------------------

    def update(self, desc: str | None = None) -> None:
        """Update the spinner, optionally changing the description."""
        if self._finished:
            return

        if desc is not None:
            self.desc = desc

        if self._use_rich:
            if desc is not None:
                self._rich_ctx.update(self._rich_task, description=desc)
            return

        if self._is_tty:
            ch = _SPINNER_FRAMES[self._frame % len(_SPINNER_FRAMES)]
            self._frame += 1
            text = f" {self.desc}" if self.desc else ""
            self.stream.write(f"\r{ch}{text}")
            self.stream.flush()

    def finish(self, message: str = "done") -> None:
        """Stop the spinner and print a final message."""
        if self._finished:
            return
        self._finished = True
        elapsed = time.monotonic() - self._start_time

        if self._use_rich:
            try:
                self._rich_ctx.stop()
            except Exception:
                pass
            # Print final message below the spinner.
            try:
                self.stream.write(f"{message} ({_format_time(elapsed)})\n")
                self.stream.flush()
            except (ValueError, OSError):
                pass
            return

        try:
            if self._is_tty:
                text = f" {self.desc}" if self.desc else ""
                self.stream.write(f"\r\u2714{text} {message} ({_format_time(elapsed)})\n")
                self.stream.flush()
            else:
                self.stream.write(f"[spinner] {message} ({_format_time(elapsed)})\n")
                self.stream.flush()
        except (ValueError, OSError):
            pass

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> "Spinner":
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self._finished:
            self.finish()


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def progress_bar(total: int | None = None, desc: str = "") -> ProgressBar:
    """Create and return a :class:`ProgressBar`."""
    return ProgressBar(total=total, desc=desc)


def spinner(desc: str = "") -> Spinner:
    """Create and return a :class:`Spinner`."""
    return Spinner(desc=desc)
