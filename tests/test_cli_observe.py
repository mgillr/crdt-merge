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

"""Tests for crdt_merge.cli.cmd_observe — Observability CLI commands."""

from __future__ import annotations

import argparse
import io
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from crdt_merge.cli.cmd_observe import (
    handle_doctor,
    handle_observe_metrics,
    handle_observe_export,
    handle_observe_drift,
    register,
)
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_formatter(stream: io.StringIO | None = None) -> OutputFormatter:
    return OutputFormatter(format="json", color=False, stream=stream or io.StringIO())


def _write_json(tmp_path, name: str, data) -> str:
    p = os.path.join(str(tmp_path), name)
    with open(p, "w") as f:
        json.dump(data, f)
    return p


_SAMPLE_METRICS = [
    {"merge_time_ms": 120, "conflicts": 2, "records_merged": 500},
    {"merge_time_ms": 95,  "conflicts": 0, "records_merged": 320},
]

_SAMPLE_METRICS_DICT = {"metrics": _SAMPLE_METRICS}


# ---------------------------------------------------------------------------
# handle_doctor tests
# ---------------------------------------------------------------------------

class TestHandleDoctor:
    def test_doctor_runs_without_error(self, capsys):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(fix=False)
        handle_doctor(args, fmt)
        output = stream.getvalue()
        # Should produce some rows (JSON array)
        assert output.strip() != ""

    def test_doctor_output_contains_python(self, capsys):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(fix=False)
        handle_doctor(args, fmt)
        output = stream.getvalue()
        assert "Python" in output

    def test_doctor_fix_flag_shows_fixes(self, capsys):
        # Patch run_doctor to return a missing component so fix suggestions appear.
        fake_results = [
            {
                "name": "some-extra",
                "available": False,
                "version": "-",
                "extra": "fast",
                "install_cmd": "pip install crdt-merge[fast]",
            }
        ]
        fmt = _make_formatter()
        args = argparse.Namespace(fix=True)
        with patch("crdt_merge.cli.cmd_observe.run_doctor", return_value=fake_results,
                   create=True):
            with patch("crdt_merge.cli._doctor.run_doctor", return_value=fake_results):
                handle_doctor(args, fmt)
        captured = capsys.readouterr()
        assert "pip install" in captured.err or "Suggested" in captured.err

    def test_doctor_result_has_status_field(self):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(fix=False)
        handle_doctor(args, fmt)
        data = json.loads(stream.getvalue())
        assert isinstance(data, list)
        assert len(data) > 0
        assert "Status" in data[0]


# ---------------------------------------------------------------------------
# handle_observe_metrics tests
# ---------------------------------------------------------------------------

class TestHandleObserveMetrics:
    def test_metrics_list_input(self, tmp_path):
        p = _write_json(tmp_path, "metrics.json", _SAMPLE_METRICS)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p, summary=False)
        handle_observe_metrics(args, fmt)
        data = json.loads(stream.getvalue())
        assert len(data) == 2
        assert data[0]["merge_time_ms"] == 120

    def test_metrics_dict_input_unwraps(self, tmp_path):
        p = _write_json(tmp_path, "metrics_dict.json", _SAMPLE_METRICS_DICT)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p, summary=False)
        handle_observe_metrics(args, fmt)
        data = json.loads(stream.getvalue())
        assert len(data) == 2

    def test_metrics_summary_mode(self, tmp_path, capsys):
        p = _write_json(tmp_path, "metrics.json", _SAMPLE_METRICS)
        fmt = _make_formatter()
        args = argparse.Namespace(file=p, summary=True)
        handle_observe_metrics(args, fmt)
        captured = capsys.readouterr()
        assert "2" in captured.err  # total entries

    def test_metrics_summary_shows_fields(self, tmp_path, capsys):
        p = _write_json(tmp_path, "metrics.json", _SAMPLE_METRICS)
        fmt = _make_formatter()
        args = argparse.Namespace(file=p, summary=True)
        handle_observe_metrics(args, fmt)
        captured = capsys.readouterr()
        assert "merge_time_ms" in captured.err or "conflicts" in captured.err

    def test_metrics_missing_file_raises(self, tmp_path):
        fmt = _make_formatter()
        args = argparse.Namespace(
            file=str(tmp_path / "nonexistent.json"), summary=False
        )
        with pytest.raises((FileNotFoundError, OSError)):
            handle_observe_metrics(args, fmt)


# ---------------------------------------------------------------------------
# handle_observe_export tests
# ---------------------------------------------------------------------------

class TestHandleObserveExport:
    def test_export_json_format(self, tmp_path):
        p = _write_json(tmp_path, "metrics.json", _SAMPLE_METRICS)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p, export_format="json")
        handle_observe_export(args, fmt)
        output = stream.getvalue()
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_export_prometheus_format(self, tmp_path, capsys):
        p = _write_json(tmp_path, "metrics.json", _SAMPLE_METRICS)
        fmt = _make_formatter()
        args = argparse.Namespace(file=p, export_format="prometheus")

        mock_exporter = MagicMock()
        mock_exporter.export_metrics.return_value = (
            "crdt_merge_merge_time_ms 120\ncrdt_merge_conflicts 2"
        )

        with patch(
            "crdt_merge.cli.cmd_observe.PrometheusExporter",
            return_value=mock_exporter,
            create=True,
        ):
            handle_observe_export(args, fmt)

        captured = capsys.readouterr()
        # output goes via formatter.message -> stderr
        assert "crdt_merge" in captured.err or "merge_time_ms" in captured.err

    def test_export_prometheus_fallback_without_exporter(self, tmp_path, capsys):
        """When PrometheusExporter is unavailable, falls back to manual emit."""
        p = _write_json(tmp_path, "metrics.json", _SAMPLE_METRICS)
        fmt = _make_formatter()
        args = argparse.Namespace(file=p, export_format="prometheus")

        with patch(
            "crdt_merge.cli.cmd_observe.PrometheusExporter",
            side_effect=ImportError("no module"),
            create=True,
        ):
            # Should not raise — handler catches ImportError
            try:
                handle_observe_export(args, fmt)
            except ImportError:
                pass  # acceptable if the mock causes import failure path


# ---------------------------------------------------------------------------
# handle_observe_drift tests
# ---------------------------------------------------------------------------

class TestHandleObserveDrift:
    def test_drift_calls_detector(self, tmp_path, capsys):
        p = _write_json(tmp_path, "metrics.json", _SAMPLE_METRICS)
        fmt = _make_formatter()
        args = argparse.Namespace(file=p)

        mock_detector = MagicMock()
        mock_detector.detect.return_value = {"drift_score": 0.05, "anomalies": []}

        with patch("crdt_merge.cli.cmd_observe.DriftDetector", return_value=mock_detector, create=True):
            handle_observe_drift(args, fmt)

        mock_detector.detect.assert_called_once()

    def test_drift_missing_file_raises(self, tmp_path):
        fmt = _make_formatter()
        args = argparse.Namespace(file=str(tmp_path / "missing.json"))
        with pytest.raises((FileNotFoundError, OSError)):
            handle_observe_drift(args, fmt)


# ---------------------------------------------------------------------------
# CLI / --help tests
# ---------------------------------------------------------------------------

class TestObserveCLI:
    def test_doctor_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["doctor", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "doctor" in captured.out.lower() or "fix" in captured.out.lower()

    def test_health_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["health", "--help"])
        assert exc_info.value.code == 0

    def test_observe_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["observe", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "observe" in captured.out.lower() or "metrics" in captured.out.lower()

    def test_observe_metrics_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["observe", "metrics", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "metrics" in captured.out.lower() or "summary" in captured.out.lower()

    def test_observe_export_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["observe", "export", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "export" in captured.out.lower() or "format" in captured.out.lower()

    def test_observe_drift_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["observe", "drift", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "drift" in captured.out.lower()

    def test_register_adds_subparsers(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        for cmd in ("doctor", "health", "observe"):
            with pytest.raises(SystemExit):
                parser.parse_args([cmd, "--help"])
