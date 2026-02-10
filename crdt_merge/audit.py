# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent Pending: UK Application No. 2607132.4
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""
Immutable, append-only audit log with cryptographic hash chaining.

Provides tamper-evident logging for merge operations using SHA-256
hash chains — each entry links to the previous via its hash, forming
a verifiable chain similar to a blockchain.

Classes:
    AuditEntry: Frozen dataclass representing a single audit log entry.
    AuditLog: Append-only log with chain verification and filtering.
    AuditedMerge: Wrapper around crdt_merge.merge() with automatic audit logging.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

import crdt_merge

__all__ = [
    "AuditEntry",
    "AuditLog",
    "AuditedMerge",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GENESIS_HASH = "genesis"

_VALID_OPERATIONS = frozenset({
    "merge",
    "encrypt",
    "decrypt",
    "unmerge",
    "key_rotate",
    "custom",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_data(data: Any) -> str:
    """Compute SHA-256 hex digest of JSON-serialized data."""
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compute_entry_hash(
    entry_id: str,
    timestamp: float,
    operation: str,
    node_id: str,
    input_hash: str,
    output_hash: str,
    prev_hash: str,
) -> str:
    """Deterministic hash over all identity fields of an entry."""
    payload = f"{entry_id}:{timestamp}:{operation}:{node_id}:{input_hash}:{output_hash}:{prev_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# AuditEntry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditEntry:
    """Single immutable audit log entry with cryptographic chain link.

    Attributes:
        entry_id:    Unique identifier (UUID4).
        timestamp:   Wall-clock time when the entry was created.
        operation:   Type of operation recorded.
        node_id:     Identifier of the node that performed the operation.
        input_hash:  SHA-256 digest of the operation's input data.
        output_hash: SHA-256 digest of the operation's output data.
        metadata:    Arbitrary operation-specific details.
        prev_hash:   Hash of the preceding entry (``"genesis"`` for the first).
        entry_hash:  SHA-256 digest computed over all identity fields.
    """

    entry_id: str
    timestamp: float
    operation: str
    node_id: str
    input_hash: str
    output_hash: str
    metadata: Dict[str, Any]
    prev_hash: str
    entry_hash: str

    # -- Serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dictionary representation."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "operation": self.operation,
            "node_id": self.node_id,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "metadata": self.metadata,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditEntry":
        """Reconstruct an ``AuditEntry`` from a dictionary."""
        return cls(
            entry_id=d["entry_id"],
            timestamp=d["timestamp"],
            operation=d["operation"],
            node_id=d["node_id"],
            input_hash=d["input_hash"],
            output_hash=d["output_hash"],
            metadata=d.get("metadata", {}),
            prev_hash=d["prev_hash"],
            entry_hash=d["entry_hash"],
        )

    # -- Verification --------------------------------------------------------

    def verify(self) -> bool:
        """Check that ``entry_hash`` matches the recomputed hash."""
        expected = _compute_entry_hash(
            self.entry_id,
            self.timestamp,
            self.operation,
            self.node_id,
            self.input_hash,
            self.output_hash,
            self.prev_hash,
        )
        return self.entry_hash == expected


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog:
    """Append-only audit log with SHA-256 hash chaining.

    Each entry's ``prev_hash`` references the ``entry_hash`` of the
    preceding entry.  The first entry in the log uses the sentinel value
    ``"genesis"`` as its ``prev_hash``.

    Parameters:
        node_id: Default node identifier stamped on new entries.
    """

    def __init__(self, node_id: str = "default") -> None:
        self._node_id = node_id
        self._entries: List[AuditEntry] = []

    # -- Properties ----------------------------------------------------------

    @property
    def entries(self) -> List[AuditEntry]:
        """Return a shallow copy of the entry list."""
        return list(self._entries)

    @property
    def node_id(self) -> str:
        return self._node_id

    # -- Core logging --------------------------------------------------------

    def _append(
        self,
        operation: str,
        input_hash: str,
        output_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Create a new chained entry and append it to the log."""
        prev_hash = (
            self._entries[-1].entry_hash if self._entries else _GENESIS_HASH
        )
        entry_id = str(uuid.uuid4())
        ts = time.time()
        entry_hash = _compute_entry_hash(
            entry_id, ts, operation, self._node_id,
            input_hash, output_hash, prev_hash,
        )
        entry = AuditEntry(
            entry_id=entry_id,
            timestamp=ts,
            operation=operation,
            node_id=self._node_id,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata=metadata or {},
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        return entry

    def log_merge(
        self,
        left_records: Any,
        right_records: Any,
        result_records: Any,
        schema: Any = None,
        **kwargs: Any,
    ) -> AuditEntry:
        """Record a merge operation.

        Computes input and output hashes from the provided data and
        stores merge-specific metadata (record counts, schema info).

        Returns:
            The newly created ``AuditEntry``.
        """
        input_data = {"left": left_records, "right": right_records}
        input_hash = _hash_data(input_data)
        output_hash = _hash_data(result_records)

        meta: Dict[str, Any] = {
            "left_count": len(left_records) if hasattr(left_records, "__len__") else 0,
            "right_count": len(right_records) if hasattr(right_records, "__len__") else 0,
            "result_count": len(result_records) if hasattr(result_records, "__len__") else 0,
        }
        if schema is not None:
            try:
                meta["schema"] = schema.to_dict() if hasattr(schema, "to_dict") else str(schema)
            except Exception:
                meta["schema"] = str(schema)

        meta.update(kwargs)
        return self._append("merge", input_hash, output_hash, meta)

    def log_operation(
        self,
        operation: str,
        input_data: Any = None,
        output_data: Any = None,
        **metadata: Any,
    ) -> AuditEntry:
        """Record an arbitrary named operation.

        Parameters:
            operation:   Label such as ``"encrypt"``, ``"decrypt"``, etc.
            input_data:  Input payload (hashed, not stored).
            output_data: Output payload (hashed, not stored).
            **metadata:  Additional key/value pairs stored on the entry.

        Returns:
            The newly created ``AuditEntry``.
        """
        input_hash = _hash_data(input_data) if input_data is not None else _hash_data("")
        output_hash = _hash_data(output_data) if output_data is not None else _hash_data("")
        return self._append(operation, input_hash, output_hash, dict(metadata))

    # -- Chain verification --------------------------------------------------

    def verify_chain(self) -> bool:
        """Verify the integrity of the entire hash chain.

        Returns ``True`` when:
        * The log is empty, **or**
        * Every entry's ``entry_hash`` is correctly computed, **and**
        * Every entry's ``prev_hash`` matches the previous entry's
          ``entry_hash`` (with the first using ``"genesis"``).
        """
        if not self._entries:
            return True

        for idx, entry in enumerate(self._entries):
            # Verify the entry's own hash.
            if not entry.verify():
                return False
            # Verify the chain link.
            expected_prev = (
                self._entries[idx - 1].entry_hash if idx > 0 else _GENESIS_HASH
            )
            if entry.prev_hash != expected_prev:
                return False

        return True

    # -- Filtering -----------------------------------------------------------

    def get_entries(
        self,
        operation: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[AuditEntry]:
        """Return entries matching the given filters.

        Parameters:
            operation: If provided, only entries of this type are returned.
            since:     Minimum timestamp (inclusive).
            until:     Maximum timestamp (inclusive).
        """
        results: List[AuditEntry] = []
        for entry in self._entries:
            if operation is not None and entry.operation != operation:
                continue
            if since is not None and entry.timestamp < since:
                continue
            if until is not None and entry.timestamp > until:
                continue
            results.append(entry)
        return results

    # -- Export / Import -----------------------------------------------------

    def export_log(self, filepath: Optional[str] = None) -> str:
        """Serialise the log to a JSON string.

        If *filepath* is provided the JSON is also written to that path.
        """
        payload = {
            "node_id": self._node_id,
            "entries": [e.to_dict() for e in self._entries],
        }
        text = json.dumps(payload, indent=2, default=str)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(text)
        return text

    @classmethod
    def import_log(cls, data: str) -> "AuditLog":
        """Deserialise an ``AuditLog`` from a JSON string.

        Raises ``ValueError`` if chain verification fails after import.
        """
        payload = json.loads(data)
        log = cls(node_id=payload.get("node_id", "default"))
        for entry_dict in payload.get("entries", []):
            entry = AuditEntry.from_dict(entry_dict)
            log._entries.append(entry)  # noqa: SLF001 – internal rebuild
        if not log.verify_chain():
            raise ValueError("Imported audit log failed chain verification")
        return log

    # -- Dunder helpers ------------------------------------------------------

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[AuditEntry]:
        return iter(self._entries)

    def __repr__(self) -> str:
        return f"AuditLog(node_id={self._node_id!r}, entries={len(self._entries)})"


# ---------------------------------------------------------------------------
# AuditedMerge
# ---------------------------------------------------------------------------

class AuditedMerge:
    """Convenience wrapper that calls ``crdt_merge.merge()`` and
    automatically records every invocation in an :class:`AuditLog`.

    Parameters:
        audit_log: Existing log to append to.  A new one is created
                   when ``None``.
        node_id:   Node identifier for log entries.
    """

    def __init__(
        self,
        audit_log: Optional[AuditLog] = None,
        node_id: str = "default",
    ) -> None:
        self._audit_log = audit_log if audit_log is not None else AuditLog(node_id=node_id)

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    def merge(
        self,
        left: Any,
        right: Any,
        key: Any,
        schema: Any = None,
        **kwargs: Any,
    ) -> Tuple[Any, AuditEntry]:
        """Execute ``crdt_merge.merge()`` and log the result.

        Parameters:
            left:   Left dataset (list of dicts, DataFrame, …).
            right:  Right dataset.
            key:    Key column(s) for the merge.
            schema: Optional ``MergeSchema`` governing field strategies.
            **kwargs: Forwarded to ``crdt_merge.merge()``.

        Returns:
            A tuple of ``(merged_result, audit_entry)``.
        """
        merge_kwargs: Dict[str, Any] = {}
        if schema is not None:
            merge_kwargs["schema"] = schema
        merge_kwargs.update(kwargs)

        result = crdt_merge.merge(left, right, key=key, **merge_kwargs)

        entry = self._audit_log.log_merge(
            left_records=left,
            right_records=right,
            result_records=result,
            schema=schema,
            key=key if isinstance(key, str) else str(key),
        )
        return result, entry
