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

"""Tests for crdt_merge.cli.migrate — MergeKit Migration CLI."""

from __future__ import annotations

import os
import sys
import textwrap
import tempfile

import pytest

from crdt_merge.cli.migrate import (
    METHOD_TO_STRATEGY,
    _generate_code,
    _parse_basic_yaml,
    _parse_value,
    cli_migrate,
    load_yaml_config,
    load_yaml_string,
    migrate_config,
    migrate_config_string,
    migrate_config_to_schema,
    migrate_string_to_schema,
    parse_basic_yaml_string,
)
from crdt_merge.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path, name: str, content: str) -> str:
    """Write a YAML file and return its path."""
    p = os.path.join(str(tmp_path), name)
    with open(p, "w") as f:
        f.write(textwrap.dedent(content))
    return p


SIMPLE_LINEAR = """\
merge_method: linear
models:
  - model: modelA
    weight: 0.6
  - model: modelB
    weight: 0.4
parameters:
  normalize: true
"""

SLERP_CONFIG = """\
merge_method: slerp
models:
  - model: base-model
  - model: finetune-model
parameters:
  t: 0.5
"""

TIES_CONFIG = """\
merge_method: ties
base_model: base-model
models:
  - model: expert-a
  - model: expert-b
  - model: expert-c
parameters:
  density: 0.5
  normalize: true
"""

DARE_CONFIG = """\
merge_method: dare_ties
base_model: my-base
models:
  - model: adapter-1
    weight: 0.7
  - model: adapter-2
    weight: 0.3
parameters:
  density: 0.3
dtype: float16
"""

DARE_LINEAR_CONFIG = """\
merge_method: dare_linear
models:
  - model: path/a
  - model: path/b
"""

TASK_ARITHMETIC_CONFIG = """\
merge_method: task_arithmetic
base_model: pretrained
models:
  - model: task-a
  - model: task-b
parameters:
  scaling_factor: 0.8
"""

PASSTHROUGH_CONFIG = """\
merge_method: passthrough
models:
  - model: only-model
"""

SLICES_CONFIG = """\
merge_method: linear
models:
  - model: modelA
  - model: modelB
slices:
  - filter: "layers.0-12"
    merge_method: slerp
    sources:
      - model: modelA
      - model: modelB
  - filter: "layers.12-24"
    merge_method: ties
    sources:
      - model: modelA
"""

EMPTY_CONFIG = """\
"""

MINIMAL_CONFIG = """\
merge_method: linear
"""


# ===================================================================
# 1. Basic YAML parsing tests
# ===================================================================

class TestParseValue:
    def test_null_variants(self):
        assert _parse_value("~") is None
        assert _parse_value("null") is None
        assert _parse_value("NULL") is None
        assert _parse_value("") is None

    def test_booleans(self):
        assert _parse_value("true") is True
        assert _parse_value("True") is True
        assert _parse_value("yes") is True
        assert _parse_value("false") is False
        assert _parse_value("no") is False

    def test_integers(self):
        assert _parse_value("42") == 42
        assert _parse_value("-3") == -3
        assert _parse_value("0") == 0

    def test_floats(self):
        assert _parse_value("3.14") == pytest.approx(3.14)
        assert _parse_value("0.5") == pytest.approx(0.5)
        assert _parse_value("1e3") == pytest.approx(1000.0)

    def test_strings(self):
        assert _parse_value("hello") == "hello"
        assert _parse_value('"quoted"') == "quoted"
        assert _parse_value("'single'") == "single"


class TestBasicYamlParser:
    def test_simple_kv(self):
        result = parse_basic_yaml_string("key: value\ncount: 3")
        assert result == {"key": "value", "count": 3}

    def test_nested_dict(self):
        text = "outer:\n  inner: val\n  num: 5"
        result = parse_basic_yaml_string(text)
        assert result == {"outer": {"inner": "val", "num": 5}}

    def test_list(self):
        text = "items:\n  - alpha\n  - beta\n  - gamma"
        result = parse_basic_yaml_string(text)
        assert result == {"items": ["alpha", "beta", "gamma"]}

    def test_list_of_dicts(self):
        text = "models:\n  - model: a\n    weight: 0.5\n  - model: b\n    weight: 0.5"
        result = parse_basic_yaml_string(text)
        assert result["models"][0] == {"model": "a", "weight": 0.5}
        assert result["models"][1] == {"model": "b", "weight": 0.5}

    def test_comments_ignored(self):
        text = "# comment\nkey: value\n# another comment"
        result = parse_basic_yaml_string(text)
        assert result == {"key": "value"}

    def test_empty_input(self):
        assert parse_basic_yaml_string("") == {}
        assert parse_basic_yaml_string("# only comment") == {}

    def test_boolean_values(self):
        text = "a: true\nb: false\nc: yes"
        result = parse_basic_yaml_string(text)
        assert result == {"a": True, "b": False, "c": True}

    def test_file_load(self, tmp_path):
        p = _write_yaml(tmp_path, "test.yaml", "x: 10\ny: hello")
        result = _parse_basic_yaml(p)
        assert result == {"x": 10, "y": "hello"}


# ===================================================================
# 2. MergeKit config parsing tests
# ===================================================================

class TestMergeKitConfigParsing:
    def test_parse_linear(self):
        cfg = parse_basic_yaml_string(SIMPLE_LINEAR)
        assert cfg["merge_method"] == "linear"
        assert len(cfg["models"]) == 2
        assert cfg["models"][0]["model"] == "modelA"
        assert cfg["models"][0]["weight"] == 0.6

    def test_parse_slerp(self):
        cfg = parse_basic_yaml_string(SLERP_CONFIG)
        assert cfg["merge_method"] == "slerp"
        assert cfg["parameters"]["t"] == 0.5

    def test_parse_ties(self):
        cfg = parse_basic_yaml_string(TIES_CONFIG)
        assert cfg["merge_method"] == "ties"
        assert cfg["base_model"] == "base-model"
        assert cfg["parameters"]["density"] == 0.5

    def test_parse_dare_ties(self):
        cfg = parse_basic_yaml_string(DARE_CONFIG)
        assert cfg["merge_method"] == "dare_ties"
        assert cfg["dtype"] == "float16"

    def test_parse_dare_linear(self):
        cfg = parse_basic_yaml_string(DARE_LINEAR_CONFIG)
        assert cfg["merge_method"] == "dare_linear"

    def test_parse_task_arithmetic(self):
        cfg = parse_basic_yaml_string(TASK_ARITHMETIC_CONFIG)
        assert cfg["merge_method"] == "task_arithmetic"
        assert cfg["base_model"] == "pretrained"

    def test_parse_passthrough(self):
        cfg = parse_basic_yaml_string(PASSTHROUGH_CONFIG)
        assert cfg["merge_method"] == "passthrough"


# ===================================================================
# 3. Code generation tests
# ===================================================================

class TestCodeGeneration:
    def test_linear_code(self, tmp_path):
        p = _write_yaml(tmp_path, "linear.yaml", SIMPLE_LINEAR)
        code = migrate_config(p)
        assert "ModelMergeSchema" in code
        assert "get_strategy" in code
        assert "modelA" in code
        assert "modelB" in code
        assert "linear" in code

    def test_slerp_code(self, tmp_path):
        p = _write_yaml(tmp_path, "slerp.yaml", SLERP_CONFIG)
        code = migrate_config(p)
        assert "slerp" in code
        assert "base-model" in code

    def test_ties_code(self, tmp_path):
        p = _write_yaml(tmp_path, "ties.yaml", TIES_CONFIG)
        code = migrate_config(p)
        assert "ties" in code
        assert "BASE_MODEL" in code

    def test_dare_code(self, tmp_path):
        p = _write_yaml(tmp_path, "dare.yaml", DARE_CONFIG)
        code = migrate_config(p)
        assert "dare_ties" in code
        assert "dtype" in code

    def test_dare_linear_code(self, tmp_path):
        p = _write_yaml(tmp_path, "dare_lin.yaml", DARE_LINEAR_CONFIG)
        code = migrate_config(p)
        assert "dare" in code

    def test_passthrough_code(self, tmp_path):
        p = _write_yaml(tmp_path, "pass.yaml", PASSTHROUGH_CONFIG)
        code = migrate_config(p)
        assert "linear" in code  # passthrough maps to linear

    def test_slices_code(self, tmp_path):
        p = _write_yaml(tmp_path, "slices.yaml", SLICES_CONFIG)
        code = migrate_config(p)
        assert "layers.0-12" in code or "slerp" in code

    def test_minimal_config_code(self, tmp_path):
        p = _write_yaml(tmp_path, "min.yaml", MINIMAL_CONFIG)
        code = migrate_config(p)
        assert "ModelMergeSchema" in code

    def test_code_has_docstring(self, tmp_path):
        p = _write_yaml(tmp_path, "doc.yaml", SIMPLE_LINEAR)
        code = migrate_config(p)
        assert '"""Auto-generated by crdt-merge migrate' in code

    def test_string_migrate(self):
        code = migrate_config_string(SIMPLE_LINEAR)
        assert "ModelMergeSchema" in code
        assert "modelA" in code


# ===================================================================
# 4. Schema conversion tests
# ===================================================================

class TestSchemaConversion:
    def test_schema_from_file(self, tmp_path):
        p = _write_yaml(tmp_path, "linear.yaml", SIMPLE_LINEAR)
        schema, extra = migrate_config_to_schema(p)
        assert hasattr(schema, "to_dict")
        assert extra["merge_method"] == "linear"
        assert "modelA" in extra["model_paths"]

    def test_schema_from_string(self):
        schema, extra = migrate_string_to_schema(SLERP_CONFIG)
        assert extra["crdt_strategy"] == "slerp"

    def test_schema_ties(self):
        schema, extra = migrate_string_to_schema(TIES_CONFIG)
        assert extra["crdt_strategy"] == "ties"
        assert extra["base_model"] == "base-model"

    def test_schema_dare(self):
        schema, extra = migrate_string_to_schema(DARE_CONFIG)
        assert extra["crdt_strategy"] == "dare_ties"
        assert extra["dtype"] == "float16"

    def test_schema_roundtrip(self):
        """Schema export → reimport produces equivalent config."""
        from crdt_merge.model.formats import export_mergekit_config
        schema, extra = migrate_string_to_schema(SIMPLE_LINEAR)
        exported = export_mergekit_config(schema, models=extra["model_paths"])
        assert "merge_method" in exported
        assert "models" in exported


# ===================================================================
# 5. CLI tests
# ===================================================================

class TestCLI:
    def test_cli_stdout(self, tmp_path, capsys):
        p = _write_yaml(tmp_path, "cli.yaml", SIMPLE_LINEAR)
        cli_migrate([p])
        captured = capsys.readouterr()
        assert "ModelMergeSchema" in captured.out

    def test_cli_output_file(self, tmp_path, capsys):
        src = _write_yaml(tmp_path, "src.yaml", SIMPLE_LINEAR)
        out = os.path.join(str(tmp_path), "out.py")
        cli_migrate([src, "--output", out])
        assert os.path.exists(out)
        with open(out) as f:
            content = f.read()
        assert "ModelMergeSchema" in content
        captured = capsys.readouterr()
        assert "✅" in captured.out

    def test_cli_schema_mode(self, tmp_path, capsys):
        p = _write_yaml(tmp_path, "schema.yaml", TIES_CONFIG)
        cli_migrate([p, "--schema"])
        captured = capsys.readouterr()
        assert "Schema:" in captured.out
        assert "ties" in captured.out

    def test_cli_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli_migrate(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_cli_no_args(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli_migrate([])
        assert exc_info.value.code == 0

    def test_cli_missing_file(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli_migrate(["/nonexistent/file.yaml"])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_main_no_args(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["crdt-merge"])
        with pytest.raises(SystemExit):
            main()
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_main_unknown_command(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["crdt-merge", "bogus"])
        with pytest.raises(SystemExit):
            main()
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err or "Unknown command" in captured.err


# ===================================================================
# 6. Edge cases
# ===================================================================

class TestEdgeCases:
    def test_empty_config(self, tmp_path):
        p = _write_yaml(tmp_path, "empty.yaml", "merge_method: linear\n")
        code = migrate_config(p)
        assert "ModelMergeSchema" in code

    def test_unknown_method(self, tmp_path):
        p = _write_yaml(tmp_path, "unk.yaml", "merge_method: super_merge\nmodels:\n  - model: x\n")
        code = migrate_config(p)
        # Falls through to using the unknown name directly
        assert "super_merge" in code

    def test_method_map_completeness(self):
        """All METHOD_TO_STRATEGY keys have values."""
        for k, v in METHOD_TO_STRATEGY.items():
            assert isinstance(k, str)
            assert isinstance(v, str)
            assert len(v) > 0

    def test_string_model_entries(self):
        yaml = "merge_method: linear\nmodels:\n  - modelA\n  - modelB\n"
        code = migrate_config_string(yaml)
        assert "modelA" in code

    def test_load_yaml_config_file(self, tmp_path):
        p = _write_yaml(tmp_path, "test.yaml", "a: 1\nb: two")
        result = load_yaml_config(p)
        assert result["a"] == 1
        assert result["b"] == "two"

    def test_load_yaml_string_func(self):
        result = load_yaml_string("x: 5\ny: hello")
        assert result["x"] == 5
        assert result["y"] == "hello"


# ===================================================================
# 7. Roundtrip tests
# ===================================================================

class TestRoundtrip:
    def test_generated_code_imports(self, tmp_path):
        """Generated code can be exec'd and imports resolve."""
        p = _write_yaml(tmp_path, "rt.yaml", SIMPLE_LINEAR)
        code = migrate_config(p)
        # Exec the generated code; should not raise
        namespace: dict = {}
        exec(code, namespace)
        assert "schema" in namespace
        assert "strategy" in namespace

    def test_generated_code_schema_valid(self, tmp_path):
        """Generated code produces a valid ModelMergeSchema."""
        p = _write_yaml(tmp_path, "rt2.yaml", TIES_CONFIG)
        code = migrate_config(p)
        namespace: dict = {}
        exec(code, namespace)
        schema = namespace["schema"]
        d = schema.to_dict()
        assert "default" in d
        assert d["default"] == "ties"

    def test_roundtrip_dare(self, tmp_path):
        """DARE config round-trips through code gen."""
        p = _write_yaml(tmp_path, "dare_rt.yaml", DARE_CONFIG)
        code = migrate_config(p)
        namespace: dict = {}
        exec(code, namespace)
        assert namespace["schema"].to_dict()["default"] == "dare_ties"
