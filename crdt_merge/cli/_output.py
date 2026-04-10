# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI output formatting with optional rich support.

Provides :class:`OutputFormatter` which handles table, JSON, CSV, JSONL,
and Parquet output.  When ``rich`` is installed and colour is enabled the
formatter uses rich tables and styled messages; otherwise it falls back to
clean, aligned stdlib output.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, TextIO

__all__ = ["OutputFormatter"]

# ---------------------------------------------------------------------------
# Optional rich imports
# ---------------------------------------------------------------------------

_rich_available = False
try:
    from rich.console import Console as _RichConsole
    from rich.table import Table as _RichTable
    _rich_available = True
except ImportError:  # pragma: no cover
    _RichConsole = None  # type: ignore[assignment,misc]
    _RichTable = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Supported output formats
# ---------------------------------------------------------------------------

_FORMATS = frozenset({"table", "json", "csv", "jsonl", "parquet"})


class OutputFormatter:
    """Unified formatter for all CLI output.

    Parameters
    ----------
    format:
        One of ``"table"``, ``"json"``, ``"csv"``, ``"jsonl"``, or
        ``"parquet"``.  When *None* and stdout is not a TTY the default
        is ``"json"``; otherwise ``"table"``.
    color:
        Enable coloured/styled output.  Requires ``rich`` to be installed.
    stream:
        Writable text stream for primary output (default ``sys.stdout``).
    output_path:
        If set, :meth:`write_output` writes to this file path instead of
        *stream*.  The file extension determines the serialisation format.
    """

    def __init__(
        self,
        format: str | None = None,
        color: bool = True,
        stream: TextIO | None = None,
        output_path: str | None = None,
    ) -> None:
        self._stream: TextIO = stream or sys.stdout
        self._output_path = output_path
        self._color = color and _rich_available

        # When piped (not a TTY) and no explicit format, default to json.
        if format is None:
            try:
                is_tty = self._stream.isatty()
            except AttributeError:
                is_tty = False
            self._format = "table" if is_tty else "json"
        else:
            if format not in _FORMATS:
                raise ValueError(
                    f"Unsupported format {format!r}. "
                    f"Choose from: {', '.join(sorted(_FORMATS))}"
                )
            self._format = format

        # Rich console for coloured stderr messages.
        self._console: Any = None
        if self._color and _RichConsole is not None:
            self._console = _RichConsole(stderr=True)

    # ------------------------------------------------------------------
    # Public data-rendering methods
    # ------------------------------------------------------------------

    def table(
        self,
        rows: list[dict],
        columns: list[str] | None = None,
        title: str = "",
    ) -> None:
        """Render *rows* as a table to :attr:`_stream`.

        With ``rich`` available and colour enabled, uses a rich table.
        Otherwise prints cleanly aligned columns with header underlines.
        """
        if not rows:
            return

        cols = columns or list(rows[0].keys())

        if self._color and _RichTable is not None and _RichConsole is not None:
            self._table_rich(rows, cols, title)
        else:
            self._table_plain(rows, cols, title)

    def json(self, data: Any, indent: int = 2) -> None:
        """Write *data* as pretty-printed JSON to :attr:`_stream`."""
        self._stream.write(json.dumps(data, indent=indent, default=str))
        self._stream.write("\n")
        self._stream.flush()

    def csv(
        self,
        rows: list[dict],
        columns: list[str] | None = None,
    ) -> None:
        """Write *rows* as CSV to :attr:`_stream`."""
        if not rows:
            return
        cols = columns or list(rows[0].keys())
        writer = csv.DictWriter(
            self._stream, fieldnames=cols, extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
        self._stream.flush()

    def jsonl(self, rows: list[dict]) -> None:
        """Write one JSON object per line to :attr:`_stream`."""
        for row in rows:
            self._stream.write(json.dumps(row, default=str))
            self._stream.write("\n")
        self._stream.flush()

    def parquet(self, rows: list[dict], path: str) -> None:
        """Write *rows* to a Parquet file at *path*.

        Tries ``polars`` first, then ``pandas`` + ``pyarrow``.  Raises
        :class:`ImportError` with a helpful message when neither is
        available.
        """
        # Try polars first.
        try:
            import polars as pl  # type: ignore[import-untyped]
            df = pl.DataFrame(rows)
            df.write_parquet(path)
            return
        except ImportError:
            pass  # nosec B110

        # Try pandas + pyarrow.
        try:
            import pandas as pd  # type: ignore[import-untyped]
            df = pd.DataFrame(rows)
            df.to_parquet(path, engine="pyarrow", index=False)
            return
        except ImportError:
            pass  # nosec B110

        raise ImportError(
            "Parquet output requires either 'polars' or 'pandas' with "
            "'pyarrow' installed.  Install one of:\n"
            "  pip install polars\n"
            "  pip install pandas pyarrow"
        )

    def auto(
        self,
        data: Any,
        columns: list[str] | None = None,
        title: str = "",
    ) -> None:
        """Dispatch to the method matching the configured format.

        *data* should be a ``list[dict]`` for table/csv/jsonl/parquet
        formats.  For ``"json"`` any JSON-serialisable object is accepted.
        """
        fmt = self._format

        if fmt == "table":
            self.table(data, columns=columns, title=title)
        elif fmt == "json":
            self.json(data)
        elif fmt == "csv":
            self.csv(data, columns=columns)
        elif fmt == "jsonl":
            self.jsonl(data)
        elif fmt == "parquet":
            if not self._output_path:
                raise ValueError(
                    "Parquet format requires an output file path "
                    "(use --output / -o)."
                )
            self.parquet(data, self._output_path)
        else:
            raise ValueError(f"Unknown format: {fmt!r}")

    # ------------------------------------------------------------------
    # Status / messaging helpers (always go to stderr)
    # ------------------------------------------------------------------

    def message(self, text: str) -> None:
        """Print an informational message to stderr."""
        sys.stderr.write(text + "\n")
        sys.stderr.flush()

    def success(self, text: str) -> None:
        """Print a success message (green when colour is available)."""
        if self._console is not None:
            self._console.print(f"[green]{text}[/green]")
        else:
            sys.stderr.write(text + "\n")
            sys.stderr.flush()

    def error(self, text: str) -> None:
        """Print an error message (red when colour is available)."""
        if self._console is not None:
            self._console.print(f"[bold red]{text}[/bold red]")
        else:
            sys.stderr.write(f"Error: {text}\n")
            sys.stderr.flush()

    def warning(self, text: str) -> None:
        """Print a warning message (yellow when colour is available)."""
        if self._console is not None:
            self._console.print(f"[yellow]{text}[/yellow]")
        else:
            sys.stderr.write(f"Warning: {text}\n")
            sys.stderr.flush()

    # ------------------------------------------------------------------
    # File output
    # ------------------------------------------------------------------

    def write_output(
        self,
        data: list[dict],
        columns: list[str] | None = None,
    ) -> None:
        """Write *data* to :attr:`_output_path` or fall back to :meth:`auto`.

        When an output path is configured the file extension determines the
        serialisation format:

        - ``.json`` -- pretty-printed JSON
        - ``.csv``  -- CSV with headers
        - ``.jsonl`` -- JSON Lines
        - ``.parquet`` -- Parquet (requires polars or pandas+pyarrow)
        - anything else -- JSON
        """
        if not self._output_path:
            self.auto(data, columns=columns)
            return

        ext = os.path.splitext(self._output_path)[1].lower()

        if ext == ".parquet":
            self.parquet(data, self._output_path)
            self.success(f"Wrote {len(data)} rows to {self._output_path}")
            return

        with open(self._output_path, "w", encoding="utf-8") as fh:
            if ext == ".csv":
                cols = columns or (list(data[0].keys()) if data else [])
                writer = csv.DictWriter(
                    fh, fieldnames=cols, extrasaction="ignore",
                )
                writer.writeheader()
                writer.writerows(data)
            elif ext == ".jsonl":
                for row in data:
                    fh.write(json.dumps(row, default=str))
                    fh.write("\n")
            else:
                # Default to JSON for .json and unknown extensions.
                fh.write(json.dumps(data, indent=2, default=str))
                fh.write("\n")

        self.success(f"Wrote {len(data)} rows to {self._output_path}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _table_rich(
        self,
        rows: list[dict],
        columns: list[str],
        title: str,
    ) -> None:
        """Render a table using rich."""
        assert _RichTable is not None and _RichConsole is not None
        rt = _RichTable(title=title or None)
        for col in columns:
            rt.add_column(col, style="cyan", no_wrap=False)
        for row in rows:
            rt.add_row(*(str(row.get(c, "")) for c in columns))
        console = _RichConsole(file=self._stream)
        console.print(rt)

    def _table_plain(
        self,
        rows: list[dict],
        columns: list[str],
        title: str,
    ) -> None:
        """Render a table using stdlib with aligned columns."""
        # Convert all values to strings.
        str_rows: list[list[str]] = [
            [str(row.get(c, "")) for c in columns] for row in rows
        ]

        # Compute column widths (minimum width = header length).
        widths = [len(c) for c in columns]
        for sr in str_rows:
            for i, val in enumerate(sr):
                if len(val) > widths[i]:
                    widths[i] = len(val)

        # Build format pieces.
        write = self._stream.write

        if title:
            write(f"  {title}\n")
            write("\n")

        # Header row.
        header = "  ".join(
            columns[i].ljust(widths[i]) for i in range(len(columns))
        )
        write(header.rstrip() + "\n")

        # Separator row.
        separator = "  ".join("-" * widths[i] for i in range(len(columns)))
        write(separator.rstrip() + "\n")

        # Data rows.
        for sr in str_rows:
            line = "  ".join(
                sr[i].ljust(widths[i]) for i in range(len(columns))
            )
            write(line.rstrip() + "\n")

        self._stream.flush()
