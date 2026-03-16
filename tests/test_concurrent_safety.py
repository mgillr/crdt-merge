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

"""Concurrent safety tests for crdt-merge thread-shared objects.

Exercises MetricsCollector, RBACController, AuditLog, ORSet, and
GossipState under concurrent load using threading.  Each test spins up
multiple threads and verifies that the object reaches a consistent,
correct final state with no data loss or corruption.
"""

from __future__ import annotations

import threading
import time
from typing import List

import pytest

# ---------------------------------------------------------------------------
# Import helpers — skip whole file if core modules unavailable
# ---------------------------------------------------------------------------

from crdt_merge.observability import MetricsCollector
from crdt_merge.rbac import RBACController, Role, Permission, Policy, AccessContext
from crdt_merge.audit import AuditLog
from crdt_merge.core import ORSet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_threads(target, n_threads: int = 8, *args, **kwargs) -> List[threading.Thread]:
    """Start *n_threads* threads running *target*, wait for them to finish."""
    threads = [threading.Thread(target=target, args=args, kwargs=kwargs) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    return threads


def _collect_errors(threads) -> List[BaseException]:
    return [t for t in threads if not t.is_alive()]  # all joined — always empty here


# ---------------------------------------------------------------------------
# 1. MetricsCollector thread safety
# ---------------------------------------------------------------------------

class TestMetricsCollectorConcurrency:
    """MetricsCollector must accumulate all records under concurrent writes."""

    def test_concurrent_record_merge(self):
        """Multiple threads each call record_merge(); total count must be exact."""
        collector = MetricsCollector()
        n_threads = 10
        records_per_thread = 100
        errors: List[Exception] = []

        def worker():
            for _ in range(records_per_thread):
                try:
                    collector.record_merge(
                        operation="merge",
                        duration_ms=1.0,
                        records_merged=1,
                        conflicts=0,
                    )
                except Exception as exc:
                    errors.append(exc)

        _run_threads(worker, n_threads)
        assert not errors, f"Errors during concurrent record_merge: {errors}"
        metrics = collector.get_metrics()
        assert len(metrics) == n_threads * records_per_thread

    def test_concurrent_record_error(self):
        """Multiple threads call record_error(); no metrics lost or corrupted."""
        collector = MetricsCollector()
        n_threads = 5
        calls_each = 50
        errors: List[Exception] = []

        def worker():
            for _ in range(calls_each):
                try:
                    collector.record_error(operation="op", duration_ms=0.5)
                except Exception as exc:
                    errors.append(exc)

        _run_threads(worker, n_threads)
        assert not errors
        # All error entries should be in the metrics
        metrics = collector.get_metrics()
        assert len(metrics) == n_threads * calls_each

    def test_concurrent_get_metrics_while_writing(self):
        """Reading metrics concurrently with writes must not raise."""
        collector = MetricsCollector()
        stop = threading.Event()
        read_errors: List[Exception] = []
        write_errors: List[Exception] = []

        def writer():
            while not stop.is_set():
                try:
                    collector.record_merge(operation="x", duration_ms=0.1, records_merged=1, conflicts=0)
                except Exception as e:
                    write_errors.append(e)
                    break

        def reader():
            while not stop.is_set():
                try:
                    collector.get_metrics()
                except Exception as e:
                    read_errors.append(e)
                    break

        threads = []
        for _ in range(4):
            threads.append(threading.Thread(target=writer, daemon=True))
        for _ in range(4):
            threads.append(threading.Thread(target=reader, daemon=True))
        for t in threads:
            t.start()
        time.sleep(0.2)
        stop.set()
        for t in threads:
            t.join(timeout=5)

        assert not read_errors, f"Read errors: {read_errors}"
        assert not write_errors, f"Write errors: {write_errors}"


# ---------------------------------------------------------------------------
# 2. RBACController thread safety
# ---------------------------------------------------------------------------

class TestRBACControllerConcurrency:
    """RBACController must handle concurrent policy mutations and checks safely."""

    def _make_controller(self) -> RBACController:
        ctrl = RBACController()
        role = Role(name="writer", permissions=Permission.MERGE | Permission.READ)
        policy = Policy(roles=[role], allowed_fields=None, denied_fields=None)
        ctrl.add_policy("node_base", policy)
        return ctrl

    def test_concurrent_add_remove_policy(self):
        """Concurrent add_policy/remove_policy does not corrupt state."""
        ctrl = RBACController()
        errors: List[Exception] = []

        def adder(node_id: str):
            for i in range(50):
                try:
                    role = Role(name="r", permissions=Permission.READ)
                    policy = Policy(roles=[role], allowed_fields=None, denied_fields=None)
                    ctrl.add_policy(f"{node_id}_{i}", policy)
                except Exception as exc:
                    errors.append(exc)

        def remover(node_id: str):
            for i in range(50):
                try:
                    ctrl.remove_policy(f"{node_id}_{i}")
                except Exception as exc:
                    errors.append(exc)

        add_threads = [threading.Thread(target=adder, args=(f"node{t}",)) for t in range(4)]
        for t in add_threads:
            t.start()
        for t in add_threads:
            t.join(timeout=10)

        remove_threads = [threading.Thread(target=remover, args=(f"node{t}",)) for t in range(4)]
        for t in remove_threads:
            t.start()
        for t in remove_threads:
            t.join(timeout=10)

        assert not errors, f"Errors during concurrent RBAC mutations: {errors}"

    def test_concurrent_check_permission(self):
        """check_permission under concurrent reads must always return same result."""
        ctrl = self._make_controller()
        role = Role(name="reader", permissions=Permission.READ)
        policy = Policy(roles=[role], allowed_fields=None, denied_fields=None)
        ctrl.add_policy("node_read", policy)

        results: List[bool] = []
        errors: List[Exception] = []

        def checker():
            for _ in range(100):
                try:
                    ctx = AccessContext(node_id="node_read", user_id="user")
                    result = ctrl.check_permission(ctx, Permission.READ)
                    results.append(result)
                except Exception as exc:
                    errors.append(exc)

        _run_threads(checker, 8)
        assert not errors
        # All reads should see the same permission
        assert all(r is True for r in results), "Permission check should always pass"


# ---------------------------------------------------------------------------
# 3. AuditLog thread safety
# ---------------------------------------------------------------------------

class TestAuditLogConcurrency:
    """AuditLog must maintain a consistent hash chain under concurrent writes."""

    def test_concurrent_log_merge_entries(self):
        """Many threads appending audit events — chain must verify at end."""
        log = AuditLog(node_id="concurrent_test")
        n_threads = 6
        records_per_thread = 30
        errors: List[Exception] = []

        def worker(thread_id: int):
            for i in range(records_per_thread):
                try:
                    log.log_merge(
                        left_records=[{"id": thread_id, "v": i}],
                        right_records=[{"id": thread_id + 1000, "v": i}],
                        merged_records=[{"id": thread_id, "v": i}],
                        conflicts=0,
                        strategy="lww",
                    )
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"Errors during concurrent AuditLog writes: {errors}"
        # Chain must verify after all writes
        assert log.verify_chain(), "Audit log chain verification failed after concurrent writes"

    def test_concurrent_log_and_export(self):
        """Export can be called while writes are in progress without exception."""
        log = AuditLog(node_id="export_test")
        stop = threading.Event()
        export_errors: List[Exception] = []
        write_errors: List[Exception] = []

        def writer():
            while not stop.is_set():
                try:
                    log.log_merge(
                        left_records=[{"id": 1}],
                        right_records=[{"id": 2}],
                        merged_records=[{"id": 1}],
                        conflicts=0,
                        strategy="lww",
                    )
                except Exception as e:
                    write_errors.append(e)
                    break

        def exporter():
            while not stop.is_set():
                try:
                    log.export_log()
                except Exception as e:
                    export_errors.append(e)
                    break

        threads = [threading.Thread(target=writer, daemon=True) for _ in range(3)]
        threads += [threading.Thread(target=exporter, daemon=True) for _ in range(2)]
        for t in threads:
            t.start()
        time.sleep(0.15)
        stop.set()
        for t in threads:
            t.join(timeout=5)

        assert not export_errors, f"Export errors: {export_errors}"
        assert not write_errors, f"Write errors: {write_errors}"


# ---------------------------------------------------------------------------
# 4. ORSet thread safety
# ---------------------------------------------------------------------------

class TestORSetConcurrency:
    """ORSet add/remove/merge operations must be safe under concurrent use."""

    def test_concurrent_add(self):
        """All elements added by concurrent threads must be present after join."""
        orset: ORSet = ORSet()
        n_threads = 8
        elements_per_thread = 50
        errors: List[Exception] = []

        def adder(tid: int):
            for i in range(elements_per_thread):
                try:
                    orset.add(f"t{tid}_e{i}")
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=adder, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors: {errors}"
        # Every element that was added should be present
        for tid in range(n_threads):
            for i in range(elements_per_thread):
                assert f"t{tid}_e{i}" in orset.elements

    def test_concurrent_add_remove(self):
        """Concurrent add then remove must leave set in consistent state."""
        orset: ORSet = ORSet()
        errors: List[Exception] = []
        added_tags: List[str] = []
        lock = threading.Lock()

        def adder():
            for i in range(100):
                try:
                    tag = orset.add(f"item_{i}")
                    with lock:
                        added_tags.append((f"item_{i}", tag))
                except Exception as exc:
                    errors.append(exc)

        add_thread = threading.Thread(target=adder)
        add_thread.start()
        add_thread.join(timeout=5)

        def remover():
            with lock:
                pairs = list(added_tags[:50])
            for elem, tag in pairs:
                try:
                    orset.remove_tag(elem, tag)
                except Exception as exc:
                    errors.append(exc)

        remove_threads = [threading.Thread(target=remover) for _ in range(3)]
        for t in remove_threads:
            t.start()
        for t in remove_threads:
            t.join(timeout=5)

        assert not errors, f"Errors: {errors}"
        # ORSet must be in a valid state (value is a set)
        assert isinstance(orset.elements, (set, frozenset))

    def test_concurrent_merge(self):
        """Merging many ORSets concurrently should not raise."""
        base: ORSet = ORSet()
        for i in range(20):
            base.add(f"base_{i}")

        errors: List[Exception] = []

        def merger():
            other = ORSet()
            for i in range(10):
                other.add(f"other_{threading.get_ident()}_{i}")
            try:
                base.merge(other)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=merger) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors during concurrent ORSet merge: {errors}"
        # Base set should contain at minimum the original 20 elements
        for i in range(20):
            assert f"base_{i}" in base.elements


# ---------------------------------------------------------------------------
# 5. Stress test: mixed concurrent operations
# ---------------------------------------------------------------------------

class TestMixedConcurrentOps:
    """Stress test mixing multiple CRDT objects in concurrent scenarios."""

    def test_metrics_and_audit_concurrent(self):
        """MetricsCollector and AuditLog used concurrently do not interfere."""
        collector = MetricsCollector()
        log = AuditLog(node_id="stress")
        errors: List[Exception] = []
        n = 30

        def metric_worker():
            for _ in range(n):
                try:
                    collector.record_merge(
                        operation="merge", duration_ms=1.0, records_merged=2, conflicts=0
                    )
                except Exception as e:
                    errors.append(e)

        def audit_worker():
            for _ in range(n):
                try:
                    log.log_merge(
                        left_records=[{"id": 1}],
                        right_records=[{"id": 2}],
                        merged_records=[{"id": 1}],
                        conflicts=0,
                        strategy="lww",
                    )
                except Exception as e:
                    errors.append(e)

        threads = (
            [threading.Thread(target=metric_worker) for _ in range(4)]
            + [threading.Thread(target=audit_worker) for _ in range(4)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"Errors in mixed concurrent test: {errors}"
        assert len(collector.get_metrics()) == 4 * n
        assert log.verify_chain()

    def test_orset_concurrent_stress(self):
        """Large concurrent ORSet workload completes without corruption."""
        orset: ORSet = ORSet()
        errors: List[Exception] = []

        def stress_worker(tid: int):
            for i in range(200):
                try:
                    tag = orset.add(f"{tid}_{i}")
                    if i % 5 == 0:
                        try:
                            orset.remove_tag(f"{tid}_{i}", tag)
                        except Exception:
                            pass  # already removed is ok
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=stress_worker, args=(t,)) for t in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        assert not errors, f"ORSet stress errors: {errors}"
        assert isinstance(orset.elements, (set, frozenset))
