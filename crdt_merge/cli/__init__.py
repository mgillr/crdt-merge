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

"""crdt-merge CLI tools."""


def main():
    """Entry point for crdt-merge CLI."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: crdt-merge <command> [args]")
        print("Commands:")
        print("  migrate <config.yaml> [--output file.py]  Convert MergeKit YAML to crdt-merge")
        sys.exit(1)

    command = sys.argv[1]
    if command == "migrate":
        from .migrate import cli_migrate

        cli_migrate(sys.argv[2:])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
