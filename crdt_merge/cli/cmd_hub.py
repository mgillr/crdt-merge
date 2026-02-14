# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI commands for HuggingFace Hub integration.

Registered sub-commands
-----------------------
* ``hub push``  -- Push a local model to the HuggingFace Hub.
* ``hub pull``  -- Pull a model from the HuggingFace Hub.
* ``hub merge`` -- Merge two Hub repositories and optionally push the result.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from crdt_merge.cli._output import OutputFormatter

EPILOG = """\
examples:
  %(prog)s push ./merged-model my-org/my-model --private --commit-message "v2 merge"
  %(prog)s pull my-org/my-model --output ./local-model --revision main
  %(prog)s merge my-org/model-a my-org/model-b --strategy slerp --push-to my-org/merged
  %(prog)s push ./model repo-id --token hf_xxxxxxxxxxxx

token resolution order:
  1. --token flag
  2. config hub.token
  3. HF_TOKEN environment variable
  4. HUGGINGFACE_TOKEN environment variable
"""

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_DEPENDENCY_MSG = (
    "Error: crdt_merge.hub.hf is not installed.\n"
    "Install it with:  pip install crdt-merge[hub]"
)


def _lazy_import_hub():
    """Lazily import HFMergeHub to avoid heavy dependencies at CLI startup."""
    try:
        from crdt_merge.hub.hf import HFMergeHub
    except ImportError as exc:
        print(_DEPENDENCY_MSG, file=sys.stderr)
        raise SystemExit(1) from exc
    return HFMergeHub


# ---------------------------------------------------------------------------
# Token resolution
# ---------------------------------------------------------------------------


def _resolve_token(args: argparse.Namespace) -> str | None:
    """Resolve the HuggingFace API token from multiple sources.

    Resolution order:
    1. ``--token`` CLI flag
    2. Configuration file ``hub.token``
    3. ``HF_TOKEN`` environment variable
    4. ``HUGGINGFACE_TOKEN`` environment variable

    Returns ``None`` when no token is found (the Hub client may still work
    for public repositories).
    """
    # 1. Explicit CLI flag
    token = getattr(args, "token", None)
    if token:
        return token

    # 2. Configuration file
    try:
        from crdt_merge.cli._config import get_config

        config = get_config()
        config_token = config.get("hub", {}).get("token")
        if config_token:
            return config_token
    except Exception:
        pass  # config module may not be available

    # 3. HF_TOKEN env var
    token = os.environ.get("HF_TOKEN")
    if token:
        return token

    # 4. HUGGINGFACE_TOKEN env var
    token = os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        return token

    return None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_push(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Push a local model directory to the HuggingFace Hub."""
    HFMergeHub = _lazy_import_hub()

    local_path = Path(args.local_model)
    if not local_path.exists():
        print(f"Error: local model path not found: {args.local_model}", file=sys.stderr)
        raise SystemExit(1)

    token = _resolve_token(args)
    if token is None:
        print(
            "Warning: no HuggingFace token found. Push may fail for private repos.\n"
            "  Set a token via --token, HF_TOKEN env var, or config hub.token.",
            file=sys.stderr,
        )

    hub = HFMergeHub(token=token)

    push_kwargs = {
        "local_path": str(local_path),
        "repo_id": args.repo_id,
        "private": args.private,
    }
    if args.commit_message:
        push_kwargs["commit_message"] = args.commit_message

    try:
        result = hub.push(**push_kwargs)
    except Exception as exc:
        print(f"Error: push failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    url = getattr(result, "url", None) or f"https://huggingface.co/{args.repo_id}"
    formatter.success(f"Model pushed to {url}")


def handle_pull(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Pull a model from the HuggingFace Hub to a local directory."""
    HFMergeHub = _lazy_import_hub()

    token = _resolve_token(args)
    hub = HFMergeHub(token=token)

    output = args.output or args.repo_id.replace("/", "--")

    pull_kwargs = {
        "repo_id": args.repo_id,
        "local_path": output,
    }
    if args.revision:
        pull_kwargs["revision"] = args.revision

    try:
        result = hub.pull(**pull_kwargs)
    except Exception as exc:
        print(f"Error: pull failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    local_dir = getattr(result, "local_path", output)
    formatter.success(f"Model pulled to {local_dir}")


def handle_merge(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Merge two Hub repositories, optionally pushing the result."""
    HFMergeHub = _lazy_import_hub()

    token = _resolve_token(args)
    hub = HFMergeHub(token=token)

    merge_kwargs = {
        "repo_a": args.repo_a,
        "repo_b": args.repo_b,
    }
    if args.strategy:
        merge_kwargs["strategy"] = args.strategy

    try:
        from crdt_merge.cli._progress import ProgressBar
    except ImportError:
        ProgressBar = None  # type: ignore[assignment,misc]

    progress = None
    if ProgressBar is not None:
        progress = ProgressBar("Merging repositories")

    try:
        result = hub.merge(
            **merge_kwargs,
            progress_callback=progress.update if progress else None,
        )
    except Exception as exc:
        print(f"Error: hub merge failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        if progress is not None:
            progress.close()

    # Optionally push the merged result
    if args.push_to:
        push_token = token
        if push_token is None:
            print(
                "Error: --push-to requires a HuggingFace token.\n"
                "  Set a token via --token, HF_TOKEN env var, or config hub.token.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        try:
            push_result = hub.push(
                local_path=result.local_path if hasattr(result, "local_path") else str(result),
                repo_id=args.push_to,
            )
        except Exception as exc:
            print(f"Error: failed to push merged model: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        url = (
            getattr(push_result, "url", None)
            or f"https://huggingface.co/{args.push_to}"
        )
        formatter.success(f"Merged model pushed to {url}")
    else:
        local_dir = getattr(result, "local_path", str(result))
        formatter.success(f"Merged model saved locally at {local_dir}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``hub`` sub-commands (push, pull, merge)."""
    hub_parser = subparsers.add_parser(
        "hub",
        help="HuggingFace Hub integration (push, pull, merge)",
        epilog=EPILOG,
        formatter_class=lambda prog: __import__(
            "argparse"
        ).RawDescriptionHelpFormatter(prog, max_help_position=40),
    )
    hub_sub = hub_parser.add_subparsers(dest="hub_command", required=True)

    # -- hub push -------------------------------------------------------------
    _register_hub_push(hub_sub)

    # -- hub pull -------------------------------------------------------------
    _register_hub_pull(hub_sub)

    # -- hub merge ------------------------------------------------------------
    _register_hub_merge(hub_sub)


def _register_hub_push(hub_sub) -> None:
    push_p = hub_sub.add_parser(
        "push",
        help="Push a local model to the HuggingFace Hub",
    )
    push_p.add_argument(
        "local_model",
        help="Path to the local model directory to push",
    )
    push_p.add_argument(
        "repo_id",
        help="HuggingFace Hub repository ID (e.g. my-org/my-model)",
    )
    push_p.add_argument(
        "--token",
        default=None,
        metavar="TOKEN",
        help="HuggingFace API token (overrides env vars and config)",
    )
    push_p.add_argument(
        "--private",
        action="store_true",
        default=False,
        help="Create the repository as private",
    )
    push_p.add_argument(
        "--commit-message",
        default=None,
        metavar="MSG",
        help="Custom commit message for the push (default: auto-generated)",
    )
    push_p.set_defaults(handler=handle_push)


def _register_hub_pull(hub_sub) -> None:
    pull_p = hub_sub.add_parser(
        "pull",
        help="Pull a model from the HuggingFace Hub",
    )
    pull_p.add_argument(
        "repo_id",
        help="HuggingFace Hub repository ID (e.g. my-org/my-model)",
    )
    pull_p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Local directory to save the model (default: derived from repo_id)",
    )
    pull_p.add_argument(
        "--revision",
        default=None,
        metavar="REV",
        help="Git revision to pull (branch, tag, or commit hash)",
    )
    pull_p.add_argument(
        "--token",
        default=None,
        metavar="TOKEN",
        help="HuggingFace API token (overrides env vars and config)",
    )
    pull_p.set_defaults(handler=handle_pull)


def _register_hub_merge(hub_sub) -> None:
    merge_p = hub_sub.add_parser(
        "merge",
        help="Merge two Hub repositories",
    )
    merge_p.add_argument(
        "repo_a",
        help="First HuggingFace Hub repository ID",
    )
    merge_p.add_argument(
        "repo_b",
        help="Second HuggingFace Hub repository ID",
    )
    merge_p.add_argument(
        "--strategy",
        default=None,
        metavar="NAME",
        help="Merge strategy name (e.g. linear, slerp, ties)",
    )
    merge_p.add_argument(
        "--push-to",
        default=None,
        metavar="REPO_ID",
        help="Push the merged result to this Hub repository",
    )
    merge_p.add_argument(
        "--token",
        default=None,
        metavar="TOKEN",
        help="HuggingFace API token (overrides env vars and config)",
    )
    merge_p.set_defaults(handler=handle_merge)
