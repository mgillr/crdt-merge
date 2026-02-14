# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Environment and dependency health checker for the crdt-merge CLI."""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Dict, List


def run_doctor() -> List[Dict[str, Any]]:
    """Run a full health check and return results."""
    results: List[Dict[str, Any]] = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    results.append({
        "name": "Python",
        "available": sys.version_info >= (3, 9),
        "version": py_ver,
        "extra": "-",
        "install_cmd": None,
    })

    # Core library
    try:
        import crdt_merge
        results.append({
            "name": "crdt-merge (core)",
            "available": True,
            "version": crdt_merge.__version__,
            "extra": "-",
            "install_cmd": None,
        })
    except ImportError:
        results.append({
            "name": "crdt-merge (core)",
            "available": False,
            "version": "-",
            "extra": "-",
            "install_cmd": "pip install crdt-merge",
        })

    # Optional extras
    extras = [
        ("pandas", "pandas", "pandas"),
        ("polars", "polars", "fast"),
        ("numpy", "numpy", "model"),
        ("torch", "torch", "gpu"),
        ("cryptography", "cryptography", "crypto"),
        ("datasets", "datasets", "datasets"),
        ("orjson", "orjson", "fast"),
        ("xxhash", "xxhash", "fast"),
        ("flwr", "flwr", "flower"),
        ("rich", "rich", "cli"),
        ("pyarrow", "pyarrow", "-"),
    ]

    for display_name, import_name, extra in extras:
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", "installed")
            results.append({
                "name": display_name,
                "available": True,
                "version": version,
                "extra": extra,
                "install_cmd": None,
            })
        except ImportError:
            cmd = f"pip install crdt-merge[{extra}]" if extra != "-" else f"pip install {import_name}"
            results.append({
                "name": display_name,
                "available": False,
                "version": "-",
                "extra": extra,
                "install_cmd": cmd,
            })

    # Accelerators
    accel_modules = {
        "DuckDB UDF": "crdt_merge.accelerators.duckdb_udf",
        "SQLite Ext": "crdt_merge.accelerators.sqlite_ext",
        "Polars Plugin": "crdt_merge.accelerators.polars_plugin",
        "Arrow Flight": "crdt_merge.accelerators.flight_server",
        "Airbyte": "crdt_merge.accelerators.airbyte",
        "dbt Package": "crdt_merge.accelerators.dbt_package",
        "DuckLake": "crdt_merge.accelerators.ducklake",
        "Streamlit UI": "crdt_merge.accelerators.streamlit_ui",
    }

    for name, mod_path in accel_modules.items():
        try:
            mod = importlib.import_module(mod_path)
            version = "-"
            # Try to get version from registered class
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name, None)
                if hasattr(obj, "version"):
                    version = getattr(obj, "version", "-")
                    break
            results.append({
                "name": f"Accel: {name}",
                "available": True,
                "version": version,
                "extra": "accel",
                "install_cmd": None,
            })
        except (ImportError, Exception):
            results.append({
                "name": f"Accel: {name}",
                "available": False,
                "version": "-",
                "extra": "accel",
                "install_cmd": None,
            })

    # Crypto backends
    crypto_backends = ["aes-gcm", "aes-gcm-siv", "chacha20", "xor"]
    for backend_name in crypto_backends:
        try:
            from crdt_merge.encryption import get_backend
            backend = get_backend(backend_name)
            results.append({
                "name": f"Crypto: {backend_name}",
                "available": True,
                "version": "-",
                "extra": "crypto",
                "install_cmd": None,
            })
        except Exception:
            available = backend_name == "xor"  # XOR is always available
            results.append({
                "name": f"Crypto: {backend_name}",
                "available": available,
                "version": "-",
                "extra": "crypto",
                "install_cmd": "pip install crdt-merge[crypto]" if not available else None,
            })

    # Config files
    global_config = os.path.expanduser("~/.crdt-merge.toml")
    local_config = os.path.join(os.getcwd(), ".crdt-merge.toml")

    results.append({
        "name": "Config: global",
        "available": os.path.exists(global_config),
        "version": global_config,
        "extra": "config",
        "install_cmd": None,
    })
    results.append({
        "name": "Config: project",
        "available": os.path.exists(local_config),
        "version": local_config,
        "extra": "config",
        "install_cmd": None,
    })

    return results
