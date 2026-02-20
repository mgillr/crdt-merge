# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI commands for model merge operations.

Registered sub-commands
-----------------------
* ``model merge``             -- Merge two or more model checkpoints.
* ``model strategies``        -- List available merge strategies.
* ``model safety``            -- Run safety analysis on models.
* ``model lora merge``        -- Merge LoRA adapters.
* ``model pipeline run``      -- Execute a multi-step merge pipeline.
* ``model pipeline validate`` -- Validate a pipeline configuration file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import argparse
    from crdt_merge.cli._output import OutputFormatter

EPILOG = """\
examples:
  %(prog)s merge model_a/ model_b/ --strategy slerp --output merged/
  %(prog)s merge model_a/ model_b/ model_c/ --strategy ties --weights 0.5,0.3,0.2 --base base/
  %(prog)s merge model_a/ model_b/ --strategy dare_ties --layer-strategy "layers.0.*=slerp" --output merged/
  %(prog)s strategies --verbose
  %(prog)s strategies --category linear
  %(prog)s safety model_a/ model_b/ --threshold 0.8
  %(prog)s lora merge adapter_a/ adapter_b/ --strategy cat --output merged_adapter/
  %(prog)s pipeline run pipeline.yaml --output merged/
  %(prog)s pipeline validate pipeline.yaml
"""

# ---------------------------------------------------------------------------
# Dependency messages
# ---------------------------------------------------------------------------

_CORE_MSG = (
    "Error: crdt_merge.model.core is not installed.\n"
    "Install it with:  pip install crdt-merge[model]"
)
_STRATEGIES_MSG = (
    "Error: crdt_merge.model.strategies is not installed.\n"
    "Install it with:  pip install crdt-merge[model]"
)
_LORA_MSG = (
    "Error: crdt_merge.model.lora is not installed.\n"
    "Install it with:  pip install crdt-merge[model]"
)
_PIPELINE_MSG = (
    "Error: crdt_merge.model.pipeline is not installed.\n"
    "Install it with:  pip install crdt-merge[model]"
)
_SAFETY_MSG = (
    "Error: crdt_merge.model.safety is not installed.\n"
    "Install it with:  pip install crdt-merge[model]"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_weights(raw: str | None) -> list[float] | None:
    """Parse a comma-separated string of floats into a list.

    Returns ``None`` when *raw* is ``None`` or empty.
    """
    if not raw:
        return None
    try:
        weights = [float(w.strip()) for w in raw.split(",")]
    except ValueError as exc:
        print(
            f"Error: invalid --weights value: {raw}\n"
            f"  Expected comma-separated floats (e.g. 0.5,0.3,0.2)\n"
            f"  Detail: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return weights


def _parse_layer_strategies(raw: list[str] | None) -> dict[str, str] | None:
    """Parse ``--layer-strategy PAT=STRAT`` flags into a dict.

    Returns ``None`` when *raw* is ``None`` or empty.
    """
    if not raw:
        return None
    result: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            print(
                f"Error: invalid --layer-strategy format: '{entry}'\n"
                f"  Expected format: PATTERN=STRATEGY (e.g. 'layers.0.*=slerp')",
                file=sys.stderr,
            )
            raise SystemExit(1)
        pattern, strategy = entry.split("=", 1)
        pattern = pattern.strip()
        strategy = strategy.strip()
        if not pattern or not strategy:
            print(
                f"Error: empty pattern or strategy in --layer-strategy: '{entry}'",
                file=sys.stderr,
            )
            raise SystemExit(1)
        result[pattern] = strategy
    return result


def _load_config(path: str) -> dict:
    """Load a YAML or JSON configuration file."""
    filepath = Path(path)
    if not filepath.exists():
        print(f"Error: config file not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    text = filepath.read_text(encoding="utf-8")

    # Try YAML first, fall back to JSON
    if filepath.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]

            return yaml.safe_load(text)
        except ImportError:
            print(
                "Error: YAML config requires PyYAML.\n"
                "  Install it with:  pip install pyyaml",
                file=sys.stderr,
            )
            raise SystemExit(1)
        except yaml.YAMLError as exc:
            print(f"Error: invalid YAML in {path}: {exc}", file=sys.stderr)
            raise SystemExit(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_merge(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Merge two or more model checkpoints."""
    try:
        from crdt_merge.model.core import ModelMerge, ModelMergeSchema
    except ImportError as exc:
        print(_CORE_MSG, file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        from crdt_merge.cli._progress import ProgressBar
    except ImportError:
        ProgressBar = None  # type: ignore[assignment,misc]

    models = args.models
    if len(models) < 2:
        print("Error: at least two models are required for merging.", file=sys.stderr)
        raise SystemExit(1)

    # Build merge schema
    schema_kwargs: Dict[str, Any] = {
        "strategy": args.strategy or "linear",
    }

    weights = _parse_weights(args.weights)
    if weights is not None:
        if len(weights) != len(models):
            print(
                f"Error: number of weights ({len(weights)}) does not match "
                f"number of models ({len(models)}).",
                file=sys.stderr,
            )
            raise SystemExit(1)
        schema_kwargs["weights"] = weights

    layer_strategies = _parse_layer_strategies(args.layer_strategy)
    if layer_strategies is not None:
        schema_kwargs["layer_strategies"] = layer_strategies

    if args.base:
        schema_kwargs["base_model"] = args.base

    if args.dtype:
        schema_kwargs["dtype"] = args.dtype

    if args.config:
        config_overrides = _load_config(args.config)
        schema_kwargs.update(config_overrides)

    schema = ModelMergeSchema(**schema_kwargs)

    # Execute the merge
    merger = ModelMerge(models=models, schema=schema)

    progress = None
    if ProgressBar is not None:
        progress = ProgressBar("Merging models")

    try:
        result = merger.execute(
            progress_callback=progress.update if progress else None,
        )
    except Exception as exc:
        print(f"Error: model merge failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        if progress is not None:
            progress.close()

    # Write output
    if not args.output:
        print("Error: --output is required for model merge.", file=sys.stderr)
        raise SystemExit(1)

    try:
        result.save(args.output)
    except Exception as exc:
        print(f"Error: failed to save merged model: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    formatter.success(f"Merged model written to {args.output}")

    # Optional provenance
    if args.provenance:
        provenance = result.provenance()
        provenance_path = Path(args.output) / "provenance.json"
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        with open(provenance_path, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2, default=str)
            f.write("\n")
        formatter.success(f"Provenance metadata written to {provenance_path}")

    # Optional safety check
    if args.safety:
        try:
            from crdt_merge.model.safety import SafetyAnalyzer
        except ImportError as exc:
            print(
                "Warning: --safety flag requires crdt_merge.model.safety.\n"
                "  Install it with:  pip install crdt-merge[model]",
                file=sys.stderr,
            )
        else:
            analyzer = SafetyAnalyzer()
            report = analyzer.analyze(result)
            formatter.json(report.to_dict() if hasattr(report, "to_dict") else report)


def handle_strategies(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """List all registered merge strategies."""
    try:
        from crdt_merge.model.strategies import get_strategy, list_strategies
    except ImportError as exc:
        print(_STRATEGIES_MSG, file=sys.stderr)
        raise SystemExit(1) from exc

    all_strategies = list_strategies()

    # Filter by category if provided
    category = getattr(args, "category", None)
    if category:
        filtered = []
        for s in all_strategies:
            try:
                info = get_strategy(s) if isinstance(s, str) else s
                if getattr(info, "category", "").lower() == category.lower():
                    filtered.append(s)
            except Exception:
                pass
        strategies = filtered
    else:
        strategies = all_strategies

    if not strategies:
        formatter.warning("No strategies found.")
        return

    if args.verbose:
        rows = []
        for s in strategies:
            info = get_strategy(s) if isinstance(s, str) else s
            rows.append({
                "name": getattr(info, "name", str(s)),
                "category": getattr(info, "category", ""),
                "description": getattr(info, "description", ""),
            })
        formatter.table(rows, columns=["name", "category", "description"])
    else:
        rows = []
        for s in strategies:
            info = get_strategy(s) if isinstance(s, str) else s
            rows.append({
                "name": getattr(info, "name", str(s)),
                "category": getattr(info, "category", ""),
            })
        formatter.table(rows, columns=["name", "category"])


def handle_safety(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Run safety analysis on model checkpoints."""
    try:
        from crdt_merge.model.safety import SafetyAnalyzer
    except ImportError as exc:
        print(_SAFETY_MSG, file=sys.stderr)
        raise SystemExit(1) from exc

    models = args.models
    if len(models) < 2:
        print("Error: at least two models are required for safety analysis.", file=sys.stderr)
        raise SystemExit(1)

    analyzer = SafetyAnalyzer(threshold=args.threshold)

    try:
        report = analyzer.analyze_models(models)
    except Exception as exc:
        print(f"Error: safety analysis failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    report_data = report.to_dict() if hasattr(report, "to_dict") else report
    formatter.json(report_data)


def handle_lora_merge(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Merge two or more LoRA adapters."""
    try:
        from crdt_merge.model.lora import LoRAMerge
    except ImportError as exc:
        print(_LORA_MSG, file=sys.stderr)
        raise SystemExit(1) from exc

    adapters = args.adapters
    if len(adapters) < 2:
        print("Error: at least two adapters are required for merging.", file=sys.stderr)
        raise SystemExit(1)

    merge_kwargs: Dict[str, Any] = {
        "strategy": args.strategy or "linear",
    }

    weights = _parse_weights(args.weights)
    if weights is not None:
        if len(weights) != len(adapters):
            print(
                f"Error: number of weights ({len(weights)}) does not match "
                f"number of adapters ({len(adapters)}).",
                file=sys.stderr,
            )
            raise SystemExit(1)
        merge_kwargs["weights"] = weights

    if args.rank_method:
        merge_kwargs["rank_method"] = args.rank_method

    merger = LoRAMerge(adapters=adapters, **merge_kwargs)

    try:
        result = merger.execute()
    except Exception as exc:
        print(f"Error: LoRA merge failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not args.output:
        print("Error: --output is required for LoRA merge.", file=sys.stderr)
        raise SystemExit(1)

    try:
        result.save(args.output)
    except Exception as exc:
        print(f"Error: failed to save merged adapter: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    formatter.success(f"Merged LoRA adapter written to {args.output}")


def handle_pipeline_run(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Execute a multi-step merge pipeline from a configuration file."""
    try:
        from crdt_merge.model.pipeline import MergePipeline
    except ImportError as exc:
        print(_PIPELINE_MSG, file=sys.stderr)
        raise SystemExit(1) from exc

    config = _load_config(args.config_file)

    pipeline = MergePipeline.from_dict(config)

    if args.dry_run:
        plan = pipeline.plan()
        plan_data = plan.to_dict() if hasattr(plan, "to_dict") else plan
        formatter.json(plan_data)
        formatter.message("Dry run complete -- no models were modified.")
        return

    try:
        from crdt_merge.cli._progress import ProgressBar
    except ImportError:
        ProgressBar = None  # type: ignore[assignment,misc]

    progress = None
    if ProgressBar is not None:
        progress = ProgressBar("Running pipeline")

    try:
        result = pipeline.execute(
            progress_callback=progress.update if progress else None,
        )
    except Exception as exc:
        print(f"Error: pipeline execution failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        if progress is not None:
            progress.close()

    if args.output:
        try:
            result.save(args.output)
        except Exception as exc:
            print(f"Error: failed to save pipeline output: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        formatter.success(f"Pipeline output written to {args.output}")
    else:
        result_data = result.to_dict() if hasattr(result, "to_dict") else result
        formatter.json(result_data)


def handle_pipeline_validate(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Validate a pipeline configuration file without executing it."""
    try:
        from crdt_merge.model.pipeline import MergePipeline
    except ImportError as exc:
        print(_PIPELINE_MSG, file=sys.stderr)
        raise SystemExit(1) from exc

    config = _load_config(args.config_file)

    try:
        pipeline = MergePipeline.from_dict(config)
        errors = pipeline.validate()
    except Exception as exc:
        print(f"Error: pipeline validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if errors:
        formatter.error("Pipeline configuration has errors:")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
        sys.stderr.flush()
        raise SystemExit(1)

    formatter.success("Pipeline configuration is valid.")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``model`` sub-commands (merge, strategies, safety, lora, pipeline)."""
    model_parser = subparsers.add_parser(
        "model",
        help="Model merge operations (checkpoints, LoRA, pipelines)",
        epilog=EPILOG,
        formatter_class=lambda prog: __import__(
            "argparse"
        ).RawDescriptionHelpFormatter(prog, max_help_position=40),
    )
    model_sub = model_parser.add_subparsers(dest="model_command", required=True)

    # -- model merge ----------------------------------------------------------
    _register_model_merge(model_sub)

    # -- model strategies -----------------------------------------------------
    _register_model_strategies(model_sub)

    # -- model safety ---------------------------------------------------------
    _register_model_safety(model_sub)

    # -- model lora -----------------------------------------------------------
    _register_model_lora(model_sub)

    # -- model pipeline -------------------------------------------------------
    _register_model_pipeline(model_sub)


def _register_model_merge(model_sub) -> None:
    merge_p = model_sub.add_parser(
        "merge",
        help="Merge two or more model checkpoints",
    )
    merge_p.add_argument(
        "models",
        nargs="+",
        help="Paths to model checkpoints to merge (minimum 2)",
    )
    merge_p.add_argument(
        "--strategy",
        default=None,
        metavar="NAME",
        help="Global merge strategy name (e.g. linear, slerp, ties, dare_ties)",
    )
    merge_p.add_argument(
        "--layer-strategy",
        action="append",
        metavar="PAT=STRAT",
        help=(
            "Per-layer strategy override using glob patterns. May be repeated. "
            "Example: --layer-strategy 'layers.0.*=slerp'"
        ),
    )
    merge_p.add_argument(
        "--weights",
        default=None,
        metavar="FLOAT,FLOAT,...",
        help="Comma-separated merge weights, one per model (e.g. 0.5,0.3,0.2)",
    )
    merge_p.add_argument(
        "--base",
        default=None,
        metavar="MODEL",
        help="Path to a base model (required by some strategies like TIES, DARE)",
    )
    merge_p.add_argument(
        "--dtype",
        choices=["float16", "float32", "bfloat16"],
        default=None,
        help="Data type for the merged model tensors",
    )
    merge_p.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Path to a YAML/JSON configuration file with additional merge parameters",
    )
    merge_p.add_argument(
        "--provenance",
        action="store_true",
        default=False,
        help="Generate and save provenance metadata alongside the merged model",
    )
    merge_p.add_argument(
        "--safety",
        action="store_true",
        default=False,
        help="Run safety analysis on the merged model after merging",
    )
    merge_p.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output path for the merged model",
    )
    merge_p.set_defaults(handler=handle_merge)


def _register_model_strategies(model_sub) -> None:
    strat_p = model_sub.add_parser(
        "strategies",
        help="List all registered merge strategies",
    )
    strat_p.add_argument(
        "--category",
        default=None,
        metavar="NAME",
        help="Filter strategies by category",
    )
    strat_p.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show full descriptions for each strategy",
    )
    strat_p.set_defaults(handler=handle_strategies)


def _register_model_safety(model_sub) -> None:
    safety_p = model_sub.add_parser(
        "safety",
        help="Run safety analysis on model checkpoints",
    )
    safety_p.add_argument(
        "models",
        nargs="+",
        help="Paths to model checkpoints to analyse (minimum 2)",
    )
    safety_p.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="Safety threshold (0.0-1.0, default: 0.9). Lower values are stricter.",
    )
    safety_p.set_defaults(handler=handle_safety)


def _register_model_lora(model_sub) -> None:
    lora_parser = model_sub.add_parser(
        "lora",
        help="LoRA adapter operations",
    )
    lora_sub = lora_parser.add_subparsers(dest="lora_command", required=True)

    lora_merge_p = lora_sub.add_parser(
        "merge",
        help="Merge two or more LoRA adapters",
    )
    lora_merge_p.add_argument(
        "adapters",
        nargs="+",
        help="Paths to LoRA adapter directories to merge (minimum 2)",
    )
    lora_merge_p.add_argument(
        "--strategy",
        default=None,
        metavar="NAME",
        help="Merge strategy for LoRA adapters (e.g. linear, cat, svd)",
    )
    lora_merge_p.add_argument(
        "--weights",
        default=None,
        metavar="FLOAT,FLOAT,...",
        help="Comma-separated merge weights, one per adapter",
    )
    lora_merge_p.add_argument(
        "--rank-method",
        choices=["max", "min", "mean", "adaptive"],
        default=None,
        help="Method for determining the rank of the merged adapter",
    )
    lora_merge_p.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output path for the merged LoRA adapter",
    )
    lora_merge_p.set_defaults(handler=handle_lora_merge)


def _register_model_pipeline(model_sub) -> None:
    pipeline_parser = model_sub.add_parser(
        "pipeline",
        help="Multi-step merge pipelines",
    )
    pipeline_sub = pipeline_parser.add_subparsers(dest="pipeline_command", required=True)

    # pipeline run
    run_p = pipeline_sub.add_parser(
        "run",
        help="Execute a merge pipeline from a config file",
    )
    run_p.add_argument(
        "config_file",
        help="Path to the pipeline YAML/JSON configuration file",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show the execution plan without running the pipeline",
    )
    run_p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Output path for the final pipeline result",
    )
    run_p.set_defaults(handler=handle_pipeline_run)

    # pipeline validate
    val_p = pipeline_sub.add_parser(
        "validate",
        help="Validate a pipeline configuration file",
    )
    val_p.add_argument(
        "config_file",
        help="Path to the pipeline YAML/JSON configuration file",
    )
    val_p.set_defaults(handler=handle_pipeline_validate)
