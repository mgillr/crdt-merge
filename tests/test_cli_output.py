# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for crdt_merge.cli._output — OutputFormatter."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile

import pytest

from crdt_merge.cli._output import OutputFormatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_ROWS = [
    {"id": 1, "name": "alice", "score": 99},
    {"id": 2, "name": "bob", "score": 42},
    {"id": 3, "name": "carol", "score": 7},
]

SAMPLE_HEADERS = ["id", "name", "score"]


def make_formatter(format: str | None = None, **kwargs) -> tuple[OutputFormatter, io.StringIO]:
    """Return an OutputFormatter writing to a StringIO buffer."""
    buf = io.StringIO()
    fmt = OutputFormatter(format=format, color=False, stream=buf, **kwargs)
    return fmt, buf


# ---------------------------------------------------------------------------
# json() method
# ---------------------------------------------------------------------------

class TestJsonMethod:
    def test_json_writes_valid_json(self):
        fmt, buf = make_formatter("json")
        fmt.json(SAMPLE_ROWS)
        parsed = json.loads(buf.getvalue())
        assert parsed == SAMPLE_ROWS

    def test_json_writes_newline_at_end(self):
        fmt, buf = make_formatter("json")
        fmt.json({"key": "value"})
        assert buf.getvalue().endswith("\n")

    def test_json_pretty_printed_with_default_indent(self):
        fmt, buf = make_formatter("json")
        fmt.json({"a": 1})
        text = buf.getvalue()
        # Pretty-printed JSON has newlines inside the object
        assert "\n" in text.strip()

    def test_json_accepts_plain_dict(self):
        fmt, buf = make_formatter("json")
        fmt.json({"x": 42})
        assert json.loads(buf.getvalue()) == {"x": 42}

    def test_json_accepts_list(self):
        fmt, buf = make_formatter("json")
        fmt.json([1, 2, 3])
        assert json.loads(buf.getvalue()) == [1, 2, 3]


# ---------------------------------------------------------------------------
# csv() method
# ---------------------------------------------------------------------------

class TestCsvMethod:
    def test_csv_writes_header_row(self):
        fmt, buf = make_formatter("csv")
        fmt.csv(SAMPLE_ROWS)
        first_line = buf.getvalue().splitlines()[0]
        assert "id" in first_line
        assert "name" in first_line
        assert "score" in first_line

    def test_csv_writes_all_data_rows(self):
        fmt, buf = make_formatter("csv")
        fmt.csv(SAMPLE_ROWS)
        lines = buf.getvalue().splitlines()
        # One header + three data rows
        assert len(lines) == 4

    def test_csv_respects_explicit_columns(self):
        fmt, buf = make_formatter("csv")
        fmt.csv(SAMPLE_ROWS, columns=["name", "score"])
        first_line = buf.getvalue().splitlines()[0]
        assert "name" in first_line
        assert "score" in first_line
        assert "id" not in first_line

    def test_csv_empty_rows_writes_nothing(self):
        fmt, buf = make_formatter("csv")
        fmt.csv([])
        assert buf.getvalue() == ""

    def test_csv_values_present_in_output(self):
        fmt, buf = make_formatter("csv")
        fmt.csv(SAMPLE_ROWS)
        text = buf.getvalue()
        assert "alice" in text
        assert "bob" in text
        assert "carol" in text


# ---------------------------------------------------------------------------
# jsonl() method
# ---------------------------------------------------------------------------

class TestJsonlMethod:
    def test_jsonl_writes_one_line_per_row(self):
        fmt, buf = make_formatter("jsonl")
        fmt.jsonl(SAMPLE_ROWS)
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        assert len(lines) == len(SAMPLE_ROWS)

    def test_jsonl_each_line_is_valid_json(self):
        fmt, buf = make_formatter("jsonl")
        fmt.jsonl(SAMPLE_ROWS)
        for line in buf.getvalue().splitlines():
            obj = json.loads(line)
            assert isinstance(obj, dict)

    def test_jsonl_preserves_row_data(self):
        fmt, buf = make_formatter("jsonl")
        fmt.jsonl(SAMPLE_ROWS)
        parsed = [json.loads(l) for l in buf.getvalue().splitlines()]
        assert parsed == SAMPLE_ROWS

    def test_jsonl_empty_list_writes_nothing(self):
        fmt, buf = make_formatter("jsonl")
        fmt.jsonl([])
        assert buf.getvalue() == ""


# ---------------------------------------------------------------------------
# table() method
# ---------------------------------------------------------------------------

class TestTableMethod:
    def test_table_includes_column_headers(self):
        fmt, buf = make_formatter("table")
        fmt.table(SAMPLE_ROWS)
        text = buf.getvalue()
        assert "id" in text
        assert "name" in text
        assert "score" in text

    def test_table_includes_data_values(self):
        fmt, buf = make_formatter("table")
        fmt.table(SAMPLE_ROWS)
        text = buf.getvalue()
        assert "alice" in text
        assert "bob" in text

    def test_table_empty_rows_writes_nothing(self):
        fmt, buf = make_formatter("table")
        fmt.table([])
        assert buf.getvalue() == ""

    def test_table_respects_columns_subset(self):
        fmt, buf = make_formatter("table")
        fmt.table(SAMPLE_ROWS, columns=["name"])
        text = buf.getvalue()
        assert "name" in text
        # "id" column header should not appear when restricted
        lines = text.splitlines()
        assert "id" not in lines[0]

    def test_table_includes_separator_line(self):
        fmt, buf = make_formatter("table")
        fmt.table(SAMPLE_ROWS)
        text = buf.getvalue()
        # Separator row consists of dashes
        assert "---" in text

    def test_table_title_appears_in_output(self):
        fmt, buf = make_formatter("table")
        fmt.table(SAMPLE_ROWS, title="My Results")
        assert "My Results" in buf.getvalue()


# ---------------------------------------------------------------------------
# message(), success(), error(), warning()
# ---------------------------------------------------------------------------

class TestStatusMessages:
    """All status helpers write to stderr (not the stream buffer)."""

    def test_message_writes_to_stderr(self, capsys):
        fmt, buf = make_formatter("json")
        fmt.message("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.err
        assert buf.getvalue() == ""

    def test_success_writes_to_stderr(self, capsys):
        fmt, buf = make_formatter("json")
        fmt.success("all good")
        captured = capsys.readouterr()
        assert "all good" in captured.err

    def test_error_writes_to_stderr(self, capsys):
        fmt, buf = make_formatter("json")
        fmt.error("something broke")
        captured = capsys.readouterr()
        assert "something broke" in captured.err

    def test_warning_writes_to_stderr(self, capsys):
        fmt, buf = make_formatter("json")
        fmt.warning("be careful")
        captured = capsys.readouterr()
        assert "be careful" in captured.err

    def test_error_prefixes_text_without_rich(self, capsys):
        # With color=False (no rich console) error should include "Error:"
        fmt, buf = make_formatter("json")
        fmt.error("disk full")
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_warning_prefixes_text_without_rich(self, capsys):
        fmt, buf = make_formatter("json")
        fmt.warning("low memory")
        captured = capsys.readouterr()
        assert "Warning:" in captured.err


# ---------------------------------------------------------------------------
# auto() dispatch
# ---------------------------------------------------------------------------

class TestAutoMethod:
    def test_auto_json_format_writes_json(self):
        fmt, buf = make_formatter("json")
        fmt.auto(SAMPLE_ROWS)
        parsed = json.loads(buf.getvalue())
        assert parsed == SAMPLE_ROWS

    def test_auto_csv_format_writes_csv(self):
        fmt, buf = make_formatter("csv")
        fmt.auto(SAMPLE_ROWS)
        lines = buf.getvalue().splitlines()
        assert len(lines) == 4  # header + 3 rows

    def test_auto_jsonl_format_writes_jsonl(self):
        fmt, buf = make_formatter("jsonl")
        fmt.auto(SAMPLE_ROWS)
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        assert len(lines) == 3

    def test_auto_table_format_writes_table(self):
        fmt, buf = make_formatter("table")
        fmt.auto(SAMPLE_ROWS)
        text = buf.getvalue()
        assert "id" in text
        assert "alice" in text

    def test_auto_parquet_without_path_raises(self):
        fmt, buf = make_formatter("parquet")
        with pytest.raises(ValueError, match="output file path"):
            fmt.auto(SAMPLE_ROWS)


# ---------------------------------------------------------------------------
# Format detection: TTY vs piped stream
# ---------------------------------------------------------------------------

class TestFormatDetection:
    def test_non_tty_stream_defaults_to_json(self):
        # A plain StringIO is not a TTY → should default to json
        buf = io.StringIO()
        fmt = OutputFormatter(format=None, color=False, stream=buf)
        assert fmt._format == "json"

    def test_explicit_format_overrides_detection(self):
        buf = io.StringIO()
        fmt = OutputFormatter(format="csv", color=False, stream=buf)
        assert fmt._format == "csv"

    def test_invalid_format_raises_value_error(self):
        buf = io.StringIO()
        with pytest.raises(ValueError, match="Unsupported format"):
            OutputFormatter(format="xml", color=False, stream=buf)

    def test_invalid_format_message_lists_valid_formats(self):
        buf = io.StringIO()
        with pytest.raises(ValueError) as exc_info:
            OutputFormatter(format="toml", color=False, stream=buf)
        msg = str(exc_info.value)
        assert "csv" in msg
        assert "json" in msg


# ---------------------------------------------------------------------------
# write_output() — file-path routing
# ---------------------------------------------------------------------------

class TestWriteOutput:
    def test_write_output_json_extension(self, tmp_path):
        out_file = str(tmp_path / "result.json")
        fmt = OutputFormatter(format="json", color=False, output_path=out_file)
        fmt.write_output(SAMPLE_ROWS)
        with open(out_file, encoding="utf-8") as fh:
            parsed = json.load(fh)
        assert parsed == SAMPLE_ROWS

    def test_write_output_csv_extension(self, tmp_path):
        out_file = str(tmp_path / "result.csv")
        fmt = OutputFormatter(format="csv", color=False, output_path=out_file)
        fmt.write_output(SAMPLE_ROWS)
        with open(out_file, encoding="utf-8") as fh:
            content = fh.read()
        assert "name" in content
        assert "alice" in content

    def test_write_output_jsonl_extension(self, tmp_path):
        out_file = str(tmp_path / "result.jsonl")
        fmt = OutputFormatter(format="jsonl", color=False, output_path=out_file)
        fmt.write_output(SAMPLE_ROWS)
        with open(out_file, encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
        assert len(lines) == 3
        assert json.loads(lines[0])["name"] == "alice"

    def test_write_output_unknown_extension_defaults_to_json(self, tmp_path):
        out_file = str(tmp_path / "result.dat")
        fmt = OutputFormatter(format="json", color=False, output_path=out_file)
        fmt.write_output(SAMPLE_ROWS)
        with open(out_file, encoding="utf-8") as fh:
            parsed = json.load(fh)
        assert parsed == SAMPLE_ROWS

    def test_write_output_no_path_falls_back_to_auto(self):
        buf = io.StringIO()
        fmt = OutputFormatter(format="json", color=False, stream=buf)
        fmt.write_output(SAMPLE_ROWS)
        parsed = json.loads(buf.getvalue())
        assert parsed == SAMPLE_ROWS

    def test_write_output_creates_file_on_disk(self, tmp_path):
        out_file = str(tmp_path / "out.json")
        fmt = OutputFormatter(format="json", color=False, output_path=out_file)
        fmt.write_output(SAMPLE_ROWS)
        assert os.path.exists(out_file)

    def test_write_output_success_message_on_stderr(self, tmp_path, capsys):
        out_file = str(tmp_path / "out.json")
        fmt = OutputFormatter(format="json", color=False, output_path=out_file)
        fmt.write_output(SAMPLE_ROWS)
        captured = capsys.readouterr()
        assert str(out_file) in captured.err

    def test_write_output_json_with_explicit_columns(self, tmp_path):
        out_file = str(tmp_path / "result.csv")
        fmt = OutputFormatter(format="csv", color=False, output_path=out_file)
        fmt.write_output(SAMPLE_ROWS, columns=["id", "name"])
        with open(out_file, encoding="utf-8") as fh:
            first_line = fh.readline()
        assert "id" in first_line
        assert "name" in first_line
        assert "score" not in first_line
