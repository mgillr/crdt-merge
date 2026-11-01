# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""Keep the Nord SNN examples working.

``examples/`` is outside the default ``testpaths``, so without this module a
change to the library that breaks an example (as the fail-closed E4 change
did) would go unnoticed. Every example module must import, the notebook must
be valid JSON, and the examples' own test-suite must pass.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "nord-snn-integration"
MODULES = sorted(EXAMPLES.glob("nord_*.py"))


def test_examples_are_present():
    assert MODULES, "no example modules found"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_example_module_imports(path):
    sys.path.insert(0, str(EXAMPLES))
    try:
        spec = importlib.util.spec_from_file_location(f"_nord_example_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(EXAMPLES))


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.ipynb")), ids=lambda p: p.name)
def test_example_notebook_is_valid_json(path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    assert nb.get("cells"), "notebook has no cells"


def test_examples_test_suite_passes():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(EXAMPLES / "tests"), "-q", "-p", "no:cacheprovider"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
