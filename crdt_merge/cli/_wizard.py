# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Interactive wizard framework and guided flows for the crdt-merge CLI.

Provides reusable input primitives and four wizard flows:
- merge: guided data merge
- schema: interactive MergeSchema builder
- model: model merge config builder
- pipeline: multi-stage pipeline builder
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ── Input Primitives ──────────────────────────────────────

def ask(
    prompt: str,
    type_fn: Callable = str,
    default: Any = None,
    choices: Optional[Sequence[str]] = None,
    validate: Optional[Callable[[Any], bool]] = None,
) -> Any:
    """Ask for a single input with validation.

    Args:
        prompt: The question to display.
        type_fn: Type converter (e.g. int, float, str).
        default: Default value shown in brackets.
        choices: Valid choices (displayed).
        validate: Custom validation function.

    Returns:
        The validated, type-converted input.
    """
    suffix = ""
    if default is not None:
        suffix = f" [{default}]"
    if choices:
        suffix += f" ({'/'.join(choices)})"

    while True:
        try:
            raw = input(f"{prompt}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if not raw and default is not None:
            return default

        if not raw:
            print("  Input required.")
            continue

        try:
            value = type_fn(raw)
        except (ValueError, TypeError) as e:
            print(f"  Invalid input: {e}")
            continue

        if choices and str(value) not in choices:
            print(f"  Must be one of: {', '.join(choices)}")
            continue

        if validate and not validate(value):
            print("  Invalid value.")
            continue

        return value


def ask_choice(prompt: str, options: List[str]) -> str:
    """Ask the user to pick from a numbered menu.

    Args:
        prompt: Question text.
        options: List of option labels.

    Returns:
        The selected option string.
    """
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")

    while True:
        try:
            raw = input(f"Choose [1-{len(options)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except (ValueError, IndexError):
            pass
        print(f"  Enter a number between 1 and {len(options)}.")


def ask_confirm(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question.

    Args:
        prompt: Question text.
        default: Default answer.

    Returns:
        True for yes, False for no.
    """
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            raw = input(f"{prompt} [{hint}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please answer y or n.")


def ask_multi(prompt: str, options: List[str]) -> List[str]:
    """Multi-select from a list (comma-separated indices).

    Args:
        prompt: Question text.
        options: Available options.

    Returns:
        List of selected option strings.
    """
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")

    while True:
        try:
            raw = input("Select (comma-separated, e.g. 1,3,5): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if not raw:
            print("  Select at least one option.")
            continue

        try:
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            selected = [options[i] for i in indices if 0 <= i < len(options)]
            if selected:
                return selected
        except (ValueError, IndexError):
            pass
        print("  Invalid selection. Use comma-separated numbers.")


# ── Wizard Registration ──────────────────────────────────

def register(subparsers: argparse._SubParsersAction) -> None:
    """Register wizard and repl commands."""
    # REPL
    repl_p = subparsers.add_parser(
        "repl", help="Start interactive REPL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  crdt-merge repl\n  crdt-merge repl --history /tmp/hist\n",
    )
    repl_p.add_argument("--history", metavar="PATH", help="History file path")
    repl_p.set_defaults(handler=handle_repl)

    # Wizard
    p = subparsers.add_parser(
        "wizard", help="Interactive guided wizards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge wizard merge\n"
            "  crdt-merge wizard schema\n"
            "  crdt-merge wizard model\n"
            "  crdt-merge wizard pipeline\n"
        ),
    )
    sp = p.add_subparsers(dest="wizard_cmd")

    sp.add_parser("merge", help="Guided data merge").set_defaults(handler=handle_wizard_merge)
    sp.add_parser("schema", help="Interactive schema builder").set_defaults(handler=handle_wizard_schema)
    sp.add_parser("model", help="Model merge config builder").set_defaults(handler=handle_wizard_model)
    sp.add_parser("pipeline", help="Multi-stage pipeline builder").set_defaults(handler=handle_wizard_pipeline)


# ── REPL Handler ──────────────────────────────────────────

def handle_repl(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._interactive import start_repl
    from crdt_merge.cli._parser import build_parser
    from crdt_merge.cli._config import load_config

    parser = build_parser()
    config = load_config(getattr(args, "config", None))
    start_repl(parser, formatter, config, history_path=args.history)


# ── Wizard Flows ──────────────────────────────────────────

def handle_wizard_merge(args: argparse.Namespace, formatter: Any) -> None:
    """Guided merge wizard."""
    print("\n=== Merge Wizard ===\n")

    # Step 1: File type
    file_type = ask_choice("What type of data files?",
                            ["CSV", "JSON", "JSONL", "Parquet"])

    ext = {"CSV": ".csv", "JSON": ".json", "JSONL": ".jsonl", "Parquet": ".parquet"}[file_type]

    # Step 2: File paths
    file_a = ask(f"Path to first file (*{ext})")
    if not os.path.exists(file_a):
        formatter.warning(f"File not found: {file_a}")

    file_b = ask(f"Path to second file (*{ext})")
    if not os.path.exists(file_b):
        formatter.warning(f"File not found: {file_b}")

    # Step 3: Detect columns
    columns: List[str] = []
    try:
        from crdt_merge.cli._util import load_data
        sample = load_data(file_a)
        if sample:
            columns = list(sample[0].keys())
            print(f"\nDetected columns: {', '.join(columns)}")
    except Exception:
        pass

    # Step 4: Key column
    if columns:
        key = ask_choice("Key column for matching rows?", columns)
    else:
        key = ask("Key column name")

    # Step 5: Conflict resolution
    prefer = ask_choice("Default conflict resolution?",
                         ["latest", "a", "b"])

    # Step 6: Per-column strategies
    strategies: Dict[str, str] = {}
    available_strategies = ["lww", "max", "min", "union", "concat", "longest"]

    if columns and ask_confirm("Set per-column strategies?", default=False):
        for col in columns:
            if col == key:
                continue
            strat = ask_choice(f"Strategy for '{col}'?",
                                ["default"] + available_strategies)
            if strat != "default":
                strategies[col] = strat

    # Step 7: Options
    dedup = ask_confirm("Deduplicate after merge?", default=True)
    provenance = ask_confirm("Track merge provenance?", default=False)

    # Step 8: Output
    output = ask(f"Output file path", default=f"merged{ext}")

    # Step 9: Preview command
    cmd_parts = ["crdt-merge", "merge", file_a, file_b, "--key", key, "--prefer", prefer]
    if dedup:
        cmd_parts.append("--dedup")
    for col, strat in strategies.items():
        cmd_parts.extend(["--strategy", f"{col}={strat}"])
    if provenance:
        cmd_parts.append("--provenance")
    cmd_parts.extend(["--output", output])

    cmd_str = " ".join(cmd_parts)
    print(f"\nGenerated command:\n  {cmd_str}\n")

    # Step 10: Execute or copy
    action = ask_choice("What would you like to do?",
                         ["Execute now", "Copy command (print only)"])

    if action == "Execute now":
        try:
            from crdt_merge.cli._util import load_data, write_data
            from crdt_merge.dataframe import merge

            data_a = load_data(file_a)
            data_b = load_data(file_b)

            try:
                import pandas as pd
                df_a = pd.DataFrame(data_a)
                df_b = pd.DataFrame(data_b)
                result = merge(df_a, df_b, key=key, prefer=prefer, dedup=dedup)
                result_data = result.to_dict("records")
            except ImportError:
                result = merge(data_a, data_b, key=key, prefer=prefer, dedup=dedup)
                result_data = result if isinstance(result, list) else [result]

            write_data(result_data, output)
            formatter.success(f"Merge complete! {len(result_data)} rows -> {output}")
        except Exception as e:
            formatter.error(str(e))
    else:
        print(f"\n{cmd_str}")


def handle_wizard_schema(args: argparse.Namespace, formatter: Any) -> None:
    """Interactive schema builder."""
    print("\n=== Schema Builder Wizard ===\n")

    # Step 1: Load sample file
    sample_path = ask("Path to a sample data file (to detect columns)")

    columns: List[str] = []
    try:
        from crdt_merge.cli._util import load_data
        sample = load_data(sample_path)
        if sample:
            columns = list(sample[0].keys())
            print(f"\nDetected columns: {', '.join(columns)}")
    except Exception as e:
        formatter.error(str(e))
        columns_str = ask("Enter column names (comma-separated)")
        columns = [c.strip() for c in columns_str.split(",")]

    if not columns:
        formatter.error("No columns to configure.")
        return

    # Step 2: Per-column strategy
    available = ["lww", "max", "min", "union", "concat", "longest"]
    schema_config: Dict[str, str] = {}

    default_strategy = ask_choice("Default strategy for all columns?", available)
    schema_config["default"] = default_strategy

    print()
    for col in columns:
        strat = ask_choice(f"Strategy for '{col}'?",
                            ["(use default)"] + available)
        if strat != "(use default)":
            schema_config[col] = strat

    # Step 3: Export format
    export_fmt = ask_choice("Export format?", ["TOML", "JSON", "Python code"])

    # Step 4: Output
    ext_map = {"TOML": ".toml", "JSON": ".json", "Python code": ".py"}
    default_out = f"merge_schema{ext_map[export_fmt]}"
    output = ask("Output file path", default=default_out)

    if export_fmt == "JSON":
        with open(output, "w") as f:
            json.dump(schema_config, f, indent=2)
    elif export_fmt == "TOML":
        with open(output, "w") as f:
            f.write("[strategies]\n")
            for k, v in schema_config.items():
                f.write(f'{k} = "{v}"\n')
    elif export_fmt == "Python code":
        lines = [
            "from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, Concat, LongestWins",
            "",
            "schema = MergeSchema(",
        ]
        strategy_map = {
            "lww": "LWW()", "max": "MaxWins()", "min": "MinWins()",
            "union": "UnionSet()", "concat": "Concat()", "longest": "LongestWins()",
        }
        for k, v in schema_config.items():
            cls = strategy_map.get(v, f"LWW()  # {v}")
            if k == "default":
                lines.append(f"    default={cls},")
            else:
                lines.append(f"    {k}={cls},")
        lines.append(")")
        with open(output, "w") as f:
            f.write("\n".join(lines) + "\n")

    formatter.success(f"Schema saved to {output}")


def handle_wizard_model(args: argparse.Namespace, formatter: Any) -> None:
    """Model merge config builder."""
    print("\n=== Model Merge Config Wizard ===\n")

    # Step 1: Models
    models: List[str] = []
    print("Enter model paths/HF repo IDs (empty line to finish):")
    while True:
        path = ask(f"  Model {len(models) + 1}", default="")
        if not path:
            break
        models.append(path)

    if len(models) < 2:
        formatter.error("Need at least 2 models.")
        return

    # Step 2: List strategies
    try:
        from crdt_merge.model.strategies import list_strategies
        available = list_strategies()
    except ImportError:
        available = ["linear", "slerp", "ties", "dare", "task_arithmetic"]

    # Step 3: Default strategy
    default_strategy = ask_choice("Default merge strategy?", available)

    # Step 4: Weights
    weights: List[float] = []
    if ask_confirm("Set custom weights per model?", default=False):
        for i, m in enumerate(models):
            w = ask(f"Weight for {m}", type_fn=float, default=1.0)
            weights.append(w)
    else:
        weights = [1.0] * len(models)

    # Step 5: Per-layer overrides
    layer_strategies: Dict[str, str] = {}
    if ask_confirm("Set per-layer strategy overrides?", default=False):
        print("Enter layer patterns (glob/regex) and strategies (empty to finish):")
        while True:
            pattern = ask("  Layer pattern (e.g. 'layers.0-6.*')", default="")
            if not pattern:
                break
            strat = ask_choice(f"  Strategy for '{pattern}'?", available)
            layer_strategies[pattern] = strat

    # Step 6: Options
    dtype = ask_choice("Output dtype?", ["float16", "float32", "bfloat16"])
    safety = ask_confirm("Run safety analysis?", default=False)

    # Step 7: Output
    output_fmt = ask_choice("Config output format?", ["TOML", "JSON"])
    default_out = f"model_merge.{'toml' if output_fmt == 'TOML' else 'json'}"
    output = ask("Output path", default=default_out)

    config = {
        "models": models,
        "weights": weights,
        "strategy": default_strategy,
        "layer_strategies": layer_strategies,
        "dtype": dtype,
        "safety": safety,
    }

    if output_fmt == "JSON":
        with open(output, "w") as f:
            json.dump(config, f, indent=2)
    else:
        with open(output, "w") as f:
            f.write("[model]\n")
            f.write(f'strategy = "{default_strategy}"\n')
            f.write(f'dtype = "{dtype}"\n')
            f.write(f"safety = {'true' if safety else 'false'}\n\n")
            f.write("[models]\n")
            for i, m in enumerate(models):
                f.write(f'model_{i} = {{path = "{m}", weight = {weights[i]}}}\n')
            if layer_strategies:
                f.write("\n[layer_strategies]\n")
                for pat, strat in layer_strategies.items():
                    f.write(f'"{pat}" = "{strat}"\n')

    formatter.success(f"Config saved to {output}")

    if ask_confirm("Execute merge now?", default=False):
        cmd = f"crdt-merge model merge {' '.join(models)} --strategy {default_strategy} --config {output}"
        print(f"\n  {cmd}\n")
        formatter.message("Run this command to execute the merge.")


def handle_wizard_pipeline(args: argparse.Namespace, formatter: Any) -> None:
    """Multi-stage pipeline builder."""
    print("\n=== Pipeline Builder Wizard ===\n")

    stages: List[Dict[str, Any]] = []

    while True:
        stage_num = len(stages) + 1
        print(f"\n--- Stage {stage_num} ---")

        stage_type = ask_choice("Stage type?",
                                 ["merge", "dedup", "model_merge", "transform", "done"])

        if stage_type == "done":
            break

        stage: Dict[str, Any] = {"type": stage_type, "stage": stage_num}

        if stage_type == "merge":
            stage["file_a"] = ask("Source A file")
            stage["file_b"] = ask("Source B file")
            stage["key"] = ask("Key column")
        elif stage_type == "dedup":
            stage["input"] = ask("Input file (or 'previous' for last stage output)",
                                  default="previous")
            stage["method"] = ask_choice("Method?", ["exact", "fuzzy", "minhash"])
        elif stage_type == "model_merge":
            n_models = ask("Number of models", type_fn=int, default=2)
            stage["models"] = []
            for i in range(n_models):
                stage["models"].append(ask(f"  Model {i+1} path"))
            try:
                from crdt_merge.model.strategies import list_strategies
                available = list_strategies()
            except ImportError:
                available = ["linear", "slerp", "ties", "dare"]
            stage["strategy"] = ask_choice("Strategy?", available)
        elif stage_type == "transform":
            stage["operation"] = ask("Transform description")

        stages.append(stage)

    if not stages:
        formatter.warning("No stages defined.")
        return

    output = ask("Pipeline config output file", default="pipeline.json")
    pipeline_config = {"version": 1, "stages": stages}

    with open(output, "w") as f:
        json.dump(pipeline_config, f, indent=2)

    formatter.success(f"Pipeline config ({len(stages)} stages) saved to {output}")
