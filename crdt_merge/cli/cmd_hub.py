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
    # HFMergeHub is imported for token resolution; actual upload uses HfApi directly.
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
    # Use HfApi.upload_folder -- HFMergeHub has no push() method.
    api = hub._hub_api()

    try:
        api.create_repo(repo_id=args.repo_id, private=args.private, exist_ok=True)
        commit_msg = args.commit_message or f"Upload via crdt-merge hub push"
        api.upload_folder(
            folder_path=str(local_path),
            repo_id=args.repo_id,
            commit_message=commit_msg,
        )
    except Exception as exc:
        print(f"Error: push failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    formatter.success(f"Model pushed to https://huggingface.co/{args.repo_id}")


def handle_pull(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Pull a model from the HuggingFace Hub to a local directory."""
    # HFMergeHub has no pull() method -- use HfApi.snapshot_download() directly.
    HFMergeHub = _lazy_import_hub()

    token = _resolve_token(args)
    hub = HFMergeHub(token=token)
    api = hub._hub_api()

    output = args.output or args.repo_id.replace("/", "--")

    download_kwargs: dict = {
        "repo_id": args.repo_id,
        "local_dir": output,
    }
    if args.revision:
        download_kwargs["revision"] = args.revision

    try:
        local_dir = api.snapshot_download(**download_kwargs)
    except Exception as exc:
        print(f"Error: pull failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    formatter.success(f"Model pulled to {local_dir}")


def handle_merge(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Merge two Hub repositories, optionally pushing the result."""
    HFMergeHub = _lazy_import_hub()

    token = _resolve_token(args)
    hub = HFMergeHub(token=token)

    # HFMergeHub.merge() takes sources: List[str], not repo_a/repo_b kwargs.
    # It also has no progress_callback parameter.
    merge_kwargs: dict = {
        "sources": [args.repo_a, args.repo_b],
    }
    if args.strategy:
        merge_kwargs["strategy"] = args.strategy
    if args.push_to:
        if token is None:
            print(
                "Error: --push-to requires a HuggingFace token.\n"
                "  Set a token via --token, HF_TOKEN env var, or config hub.token.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        merge_kwargs["destination"] = args.push_to

    try:
        from crdt_merge.cli._progress import ProgressBar
    except ImportError:
        ProgressBar = None  # type: ignore[assignment,misc]

    progress = ProgressBar(desc="Merging repositories") if ProgressBar is not None else None

    try:
        result = hub.merge(**merge_kwargs)
    except Exception as exc:
        print(f"Error: hub merge failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        if progress is not None:
            progress.finish()

    if args.push_to:
        url = result.repo_url or f"https://huggingface.co/{args.push_to}"
        formatter.success(f"Merged model pushed to {url}")
    else:
        n_layers = len(result.state_dict) if result.state_dict else 0
        formatter.success(
            f"Merged {n_layers} weight tensor(s) from "
            f"{args.repo_a} + {args.repo_b}"
        )
        if result.model_card:
            formatter.message("\n--- Model Card ---\n" + result.model_card[:500] + "...")


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
