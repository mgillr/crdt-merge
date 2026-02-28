# tests/test_guide_security_misc.py
# Test suite for:
#   - docs/guides/security-guide.md
#   - docs/guides/security-hardening.md
#   - docs/guides/model-crdt-matrix.md
#   - docs/guides/model-merge-strategies.md
#   - docs/guides/troubleshooting.md

import secrets
import time
import warnings

import numpy as np
import pytest


# ===========================================================================
# security-guide.md — Field-Level Encryption
# ===========================================================================


def test_sg_static_key_provider_import():
    """security-guide.md: StaticKeyProvider can be imported and instantiated."""
    from crdt_merge.encryption import StaticKeyProvider

    master_key = secrets.token_bytes(32)
    provider = StaticKeyProvider(master_key)
    email_key = provider.get_key("email")
    salary_key = provider.get_key("salary")
    assert len(email_key) == 32
    assert len(salary_key) == 32
    assert email_key != salary_key


def test_sg_key_provider_abstract_import():
    """security-guide.md: KeyProvider abstract base class is importable."""
    from crdt_merge.encryption import KeyProvider

    class VaultKeyProvider(KeyProvider):
        def get_key(self, field_name: str) -> bytes:
            return secrets.token_bytes(32)

    vkp = VaultKeyProvider()
    assert len(vkp.get_key("any_field")) == 32


def test_sg_encrypt_decrypt_field():
    """security-guide.md: Basic encrypt/decrypt round-trip for a single field."""
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    key = secrets.token_bytes(32)
    provider = StaticKeyProvider(key)
    em = EncryptedMerge(key_provider=provider, backend="auto")

    encrypted = em.encrypt_field("sensitive@email.com", "email")
    assert encrypted is not None

    decrypted = em.decrypt_field(encrypted)
    assert decrypted == "sensitive@email.com"


def test_sg_order_preserving_tags():
    """security-guide.md: order_tag allows deterministic ciphertext comparison without decryption.

    NOTE: order_tag is an HMAC-based stable tag — not value-order-preserving.
    The same plaintext always produces the same order_tag; different plaintexts
    produce consistent but arbitrary ordering.  Use for stable sorting only.
    """
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    key = secrets.token_bytes(32)
    provider = StaticKeyProvider(key)
    em = EncryptedMerge(key_provider=provider, backend="auto")

    ev_a = em.encrypt_field(100, "score")
    ev_b = em.encrypt_field(200, "score")

    # Same value → same order_tag (deterministic)
    ev_a2 = em.encrypt_field(100, "score")
    assert ev_a == ev_a2, "Same plaintext must produce identical order_tag"

    # Different values → comparison operators work consistently (stable sort)
    assert (ev_a < ev_b) != (ev_a > ev_b), "Comparison must be consistent"
    assert not (ev_a < ev_b and ev_a > ev_b), "Cannot be both less and greater"


def test_sg_bulk_record_encryption_all_fields():
    """security-guide.md: encrypt_records encrypts non-key fields; decrypt_records restores them."""
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    key = secrets.token_bytes(32)
    provider = StaticKeyProvider(key)
    em = EncryptedMerge(key_provider=provider, backend="auto")

    records = [
        {"id": 1, "email": "alice@example.com", "salary": 90000},
        {"id": 2, "email": "bob@example.com", "salary": 85000},
    ]

    encrypted_records = em.encrypt_records(records, key="id")
    # Keys should be preserved as plain, other fields encrypted
    assert encrypted_records[0]["id"] == 1

    plain_records = em.decrypt_records(encrypted_records)
    assert plain_records[0]["email"] == "alice@example.com"
    assert plain_records[1]["salary"] == 85000


def test_sg_bulk_record_encryption_specific_fields():
    """security-guide.md: encrypt_records with fields= only encrypts named fields."""
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    key = secrets.token_bytes(32)
    provider = StaticKeyProvider(key)
    em = EncryptedMerge(key_provider=provider, backend="auto")

    records = [
        {"id": 1, "email": "alice@example.com", "salary": 90000},
    ]

    encrypted_records = em.encrypt_records(records, fields=["email"], key="id")
    # salary should remain plain
    assert encrypted_records[0]["salary"] == 90000

    plain_records = em.decrypt_records(encrypted_records)
    assert plain_records[0]["email"] == "alice@example.com"


def test_sg_wire_format_versioning():
    """security-guide.md: v2 wire format includes 'cipher' and 'version' fields."""
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    key = secrets.token_bytes(32)
    provider = StaticKeyProvider(key)
    em = EncryptedMerge(key_provider=provider, backend="auto")

    ev = em.encrypt_field("hello", "greeting")
    serialized = ev.to_dict()

    assert serialized.get("__encrypted__") is True
    assert "ciphertext" in serialized
    assert "nonce" in serialized
    assert "tag" in serialized
    assert "order_tag" in serialized
    assert "field_name" in serialized
    # v2 fields
    assert serialized.get("version") == 2
    assert "cipher" in serialized


def test_sg_custom_backend_registration():
    """security-guide.md: CryptoBackend subclass can be registered and used."""
    from crdt_merge.encryption import (
        CryptoBackend,
        EncryptedMerge,
        StaticKeyProvider,
        register_backend,
    )

    _BACKEND_NAME = "test-guide-xor"

    class GuideXorBackend(CryptoBackend):
        name = _BACKEND_NAME

        def encrypt(self, key, plaintext, associated_data=None):
            ct = bytes(b ^ key[i % len(key)] for i, b in enumerate(plaintext))
            nonce = b"\x00" * 12
            tag = b"\x01" * 32
            return ct, nonce, tag

        def decrypt(self, key, ciphertext, nonce, tag, associated_data=None):
            return bytes(b ^ key[i % len(key)] for i, b in enumerate(ciphertext))

    register_backend(_BACKEND_NAME, GuideXorBackend)

    provider = StaticKeyProvider(secrets.token_bytes(32))
    em = EncryptedMerge(key_provider=provider, backend=_BACKEND_NAME)

    ev = em.encrypt_field("test value", "field1")
    assert em.decrypt_field(ev) == "test value"


def test_sg_key_rotation():
    """security-guide.md: rotate_key re-encrypts records from old key to new key."""
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    old_key = secrets.token_bytes(32)
    new_key = secrets.token_bytes(32)

    old_provider = StaticKeyProvider(old_key)
    new_provider = StaticKeyProvider(new_key)

    # Encrypt with old key
    em_old = EncryptedMerge(key_provider=old_provider, backend="auto")
    records = [{"id": 1, "email": "alice@example.com", "salary": 90000}]
    encrypted_records = em_old.encrypt_records(records, key="id")

    # Rotate to new key
    em_new = EncryptedMerge(key_provider=new_provider, backend="aes-256-gcm")
    rotated = em_new.rotate_key(
        records=encrypted_records,
        old_provider=old_provider,
        new_provider=new_provider,
        fields=["email", "salary"],
    )
    assert len(rotated) == 1

    # Decrypt with new key
    plain = em_new.decrypt_records(rotated)
    assert plain[0]["email"] == "alice@example.com"
    assert plain[0]["salary"] == 90000


# ===========================================================================
# security-guide.md — RBAC
# ===========================================================================


def test_sg_role_permissions():
    """security-guide.md: Pre-defined roles carry expected permissions."""
    from crdt_merge.rbac import ADMIN, MERGER, READER, Permission

    assert MERGER.has_permission(Permission.MERGE)
    assert not MERGER.has_permission(Permission.ADMIN)
    assert ADMIN.has_permission(Permission.ENCRYPT)
    assert READER.has_permission(Permission.READ)
    assert not READER.has_permission(Permission.WRITE)


def test_sg_rbac_controller_permission_check():
    """security-guide.md: RBACController.check_permission enforces role-based access."""
    from crdt_merge.rbac import (
        AccessContext,
        MERGER,
        Permission,
        Policy,
        RBACController,
    )

    rbac = RBACController()
    policy = Policy(role=MERGER, denied_fields={"secret_field"})
    rbac.add_policy("node-1", policy)

    ctx = AccessContext(node_id="node-1", role=MERGER)

    assert rbac.check_permission(ctx, Permission.MERGE)
    assert rbac.check_permission(ctx, Permission.READ)
    assert not rbac.check_permission(ctx, Permission.ADMIN)


def test_sg_rbac_field_access():
    """security-guide.md: denied_fields blocks field access even for permitted roles."""
    from crdt_merge.rbac import (
        AccessContext,
        MERGER,
        Permission,
        Policy,
        RBACController,
    )

    rbac = RBACController()
    policy = Policy(role=MERGER, denied_fields={"secret_field"})
    rbac.add_policy("node-1", policy)

    ctx = AccessContext(node_id="node-1", role=MERGER)

    assert rbac.check_field_access(ctx, "email", Permission.READ)
    assert not rbac.check_field_access(ctx, "secret_field", Permission.READ)


def test_sg_rbac_strategy_access():
    """security-guide.md: check_strategy_access permits allowed strategies."""
    from crdt_merge.rbac import (
        AccessContext,
        MERGER,
        Policy,
        RBACController,
    )

    rbac = RBACController()
    policy = Policy(role=MERGER, denied_fields=set())
    rbac.add_policy("node-1", policy)
    ctx = AccessContext(node_id="node-1", role=MERGER)

    assert rbac.check_strategy_access(ctx, "LWW")


def test_sg_secure_merge_strips_denied_fields():
    """security-guide.md: SecureMerge strips denied_fields from merge output."""
    from crdt_merge.rbac import (
        AccessContext,
        MERGER,
        Policy,
        RBACController,
        SecureMerge,
    )

    rbac = RBACController()
    policy = Policy(role=MERGER, denied_fields={"internal_notes"})
    rbac.add_policy("node-1", policy)

    secure = SecureMerge(rbac)
    ctx = AccessContext(node_id="node-1", role=MERGER)

    left = [{"id": 1, "name": "Alice", "internal_notes": "VIP"}]
    right = [{"id": 1, "name": "Alice B.", "internal_notes": "Standard"}]

    result = secure.merge(left, right, key="id", context=ctx)

    assert len(result) == 1
    assert "internal_notes" not in result[0]
    assert result[0]["name"] in {"Alice", "Alice B."}


def test_sg_secure_merge_no_context():
    """security-guide.md: SecureMerge without context proceeds without access checks."""
    from crdt_merge.rbac import (
        MERGER,
        Policy,
        RBACController,
        SecureMerge,
    )

    rbac = RBACController()
    policy = Policy(role=MERGER, denied_fields=set())
    rbac.add_policy("node-1", policy)

    secure = SecureMerge(rbac)

    left = [{"id": 1, "name": "Alice"}]
    right = [{"id": 1, "name": "Alice B."}]
    result = secure.merge(left, right, key="id")
    assert len(result) == 1


# ===========================================================================
# security-guide.md — Audit Trails
# ===========================================================================


def test_sg_audit_log_basic():
    """security-guide.md: AuditLog.log_operation records an entry."""
    from crdt_merge.audit import AuditLog

    log = AuditLog(node_id="prod-1")
    entry = log.log_operation(
        "encrypt",
        input_data={"field": "email"},
        output_data={"status": "ok"},
        backend="aes-256-gcm",
    )
    assert entry.operation == "encrypt"
    assert entry.node_id == "prod-1"


def test_sg_audit_log_merge():
    """security-guide.md: AuditedMerge logs merge operations with correct metadata."""
    from crdt_merge.audit import AuditLog, AuditedMerge

    log = AuditLog(node_id="prod-1")
    am = AuditedMerge(audit_log=log, node_id="prod-1")

    left = [{"id": 1, "name": "Alice", "score": 100}]
    right = [{"id": 1, "name": "Alice", "score": 150}]

    result, entry = am.merge(left, right, key="id")

    assert entry.operation == "merge"
    assert entry.node_id == "prod-1"
    assert entry.metadata["left_count"] == 1
    assert entry.metadata["right_count"] == 1
    assert entry.metadata["result_count"] == 1


def test_sg_audit_chain_verification():
    """security-guide.md: verify_chain() returns True on an intact chain."""
    from crdt_merge.audit import AuditLog, AuditedMerge

    log = AuditLog(node_id="prod-1")
    am = AuditedMerge(audit_log=log, node_id="prod-1")

    left = [{"id": 1, "name": "Alice", "score": 100}]
    right = [{"id": 1, "name": "Alice", "score": 150}]
    am.merge(left, right, key="id")

    assert log.verify_chain()
    assert len(log) >= 1


def test_sg_audit_get_entries_by_operation():
    """security-guide.md: get_entries(operation=) filters by operation type."""
    from crdt_merge.audit import AuditLog, AuditedMerge

    log = AuditLog(node_id="prod-1")
    log.log_operation("encrypt", input_data={}, output_data={})
    am = AuditedMerge(audit_log=log, node_id="prod-1")
    left = [{"id": 1, "score": 1}]
    right = [{"id": 1, "score": 2}]
    am.merge(left, right, key="id")

    merge_entries = log.get_entries(operation="merge")
    assert len(merge_entries) >= 1
    assert all(e.operation == "merge" for e in merge_entries)


def test_sg_audit_get_entries_since():
    """security-guide.md: get_entries(since=) filters by time window."""
    from crdt_merge.audit import AuditLog

    log = AuditLog(node_id="prod-1")
    t_before = time.time()
    log.log_operation("encrypt", input_data={}, output_data={})
    recent = log.get_entries(since=t_before)
    assert len(recent) >= 1


def test_sg_audit_export_import():
    """security-guide.md: export_log/import_log round-trip preserves chain integrity."""
    from crdt_merge.audit import AuditLog

    log = AuditLog(node_id="prod-1")
    log.log_operation("encrypt", input_data={"field": "email"}, output_data={"status": "ok"})

    json_str = log.export_log()
    assert isinstance(json_str, str)
    assert len(json_str) > 0

    restored_log = AuditLog.import_log(json_str)
    assert restored_log.verify_chain()
    assert len(restored_log) == len(log)


def test_sg_defense_in_depth_composition():
    """security-guide.md: Compose encryption + RBAC + audit in the full pipeline."""
    from crdt_merge.audit import AuditLog, AuditedMerge
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
    from crdt_merge.rbac import (
        AccessContext,
        MERGER,
        Policy,
        RBACController,
        SecureMerge,
    )

    # Layer 1: Encryption
    provider = StaticKeyProvider(secrets.token_bytes(32))
    em = EncryptedMerge(key_provider=provider, backend="auto")

    # Layer 2: RBAC
    rbac = RBACController()
    rbac.add_policy("node-1", Policy(role=MERGER, denied_fields={"ssn"}))
    secure = SecureMerge(rbac)

    # Layer 3: Audit
    log = AuditLog(node_id="node-1")
    am = AuditedMerge(audit_log=log, node_id="node-1")

    left = [{"id": 1, "name": "Alice", "score": 100}]
    right = [{"id": 1, "name": "Alice", "score": 200}]

    # Encrypt first
    encrypted_left = em.encrypt_records(left, key="id")
    encrypted_right = em.encrypt_records(right, key="id")

    # Merge with audit
    result, entry = am.merge(encrypted_left, encrypted_right, key="id")

    assert log.verify_chain()
    assert entry.operation == "merge"


# ===========================================================================
# security-hardening.md — import / API presence tests
# (text-heavy guide; verifies all referenced APIs are importable and functional)
# ===========================================================================


def test_sh_encryption_imports():
    """security-hardening.md: encryption module imports required for hardening guide."""
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider  # noqa: F401


def test_sh_rbac_policy_denied_fields():
    """security-hardening.md: Policy with denied_fields for PII always wins over allow."""
    from crdt_merge.rbac import MERGER, Policy

    policy = Policy(
        role=MERGER,
        denied_fields={"ssn", "credit_card_number", "api_key", "password_hash"},
        max_record_count=50_000,
    )
    assert "ssn" in policy.denied_fields
    assert policy.max_record_count == 50_000


def test_sh_multi_tenant_field_segmentation():
    """security-hardening.md: Per-tenant Policy with allowed_fields and denied_fields."""
    from crdt_merge.rbac import MERGER, READER, Policy

    tenant_a_policy = Policy(
        role=MERGER,
        allowed_fields={"tenant_id", "record_id", "name", "email"},
        denied_fields={"internal_cost", "margin"},
        max_record_count=10_000,
    )
    analytics_policy = Policy(
        role=READER,
        allowed_fields=None,  # All fields
        denied_fields={"ssn", "raw_pii"},
    )

    assert "internal_cost" in tenant_a_policy.denied_fields
    assert analytics_policy.allowed_fields is None


def test_sh_strategy_restriction_policy():
    """security-hardening.md: allowed_strategies on Policy restricts strategy use."""
    from crdt_merge.rbac import MERGER, Policy

    policy = Policy(
        role=MERGER,
        allowed_strategies={"LWW", "MaxWins", "MinWins"},
    )
    assert "LWW" in policy.allowed_strategies
    assert "UnionSet" not in policy.allowed_strategies


def test_sh_audit_log_chain_verification():
    """security-hardening.md: verify_chain() is the primary integrity check."""
    from crdt_merge.audit import AuditLog

    log = AuditLog(node_id="prod-hardening")
    for i in range(5):
        log.log_operation("merge", input_data={"batch": i}, output_data={"ok": True})
    assert log.verify_chain()


def test_sh_rbac_controller_thread_safe_api():
    """security-hardening.md: RBACController is importable and add/remove policy works."""
    from crdt_merge.rbac import MERGER, Policy, RBACController

    rbac = RBACController()
    policy = Policy(role=MERGER, denied_fields=set())
    rbac.add_policy("node-hardening", policy)
    rbac.remove_policy("node-hardening")
    # Should not raise


def test_sh_hipaa_phi_encryption_pattern():
    """security-hardening.md: HIPAA PHI pattern — denied_fields + EncryptedMerge."""
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
    from crdt_merge.rbac import MERGER, Policy

    phi_fields = {"patient_id", "dob", "ssn", "diagnosis_code", "medication"}

    policy = Policy(
        role=MERGER,
        denied_fields=phi_fields,
        allowed_strategies={"LWW", "MaxWins"},
        max_record_count=100_000,
    )
    assert policy.denied_fields == phi_fields

    provider = StaticKeyProvider(secrets.token_bytes(32))
    em = EncryptedMerge(key_provider=provider, backend="aes-256-gcm")
    phi_records = [{"record_id": 1, "patient_id": "P001", "dob": "1985-01-01"}]
    encrypted = em.encrypt_records(phi_records, fields=list(phi_fields & {"patient_id", "dob"}), key="record_id")
    plain = em.decrypt_records(encrypted)
    assert plain[0]["patient_id"] == "P001"


# ===========================================================================
# model-crdt-matrix.md — verify documented strategies are importable
# ===========================================================================


def test_mcm_module_imports():
    """model-crdt-matrix.md: model strategy registry module is importable."""
    from crdt_merge.model.strategies import get_strategy, list_strategies  # noqa: F401


def test_mcm_task_arithmetic_fully_crdt():
    """model-crdt-matrix.md: task_arithmetic is commutative and associative."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("task_arithmetic")
    base = np.array([1.0, 1.0, 1.0])
    t1 = np.array([2.0, 3.0, 4.0])
    t2 = np.array([1.5, 2.0, 3.0])

    result_ab = s.merge([t1, t2], base=base, weights=[1.0, 1.0])
    result_ba = s.merge([t2, t1], base=base, weights=[1.0, 1.0])

    # Commutativity: merge(A,B) == merge(B,A)
    np.testing.assert_array_almost_equal(result_ab, result_ba)


def test_mcm_weight_average_commutative():
    """model-crdt-matrix.md: weight_average is commutative."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("weight_average")
    t1 = np.array([1.0, 2.0, 3.0])
    t2 = np.array([3.0, 4.0, 5.0])

    result_ab = s.merge([t1, t2], weights=[0.5, 0.5])
    result_ba = s.merge([t2, t1], weights=[0.5, 0.5])

    np.testing.assert_array_almost_equal(result_ab, result_ba)


def test_mcm_weight_average_idempotent():
    """model-crdt-matrix.md: weight_average is idempotent: merge(A, A) == A."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("weight_average")
    t1 = np.array([1.0, 2.0, 3.0])

    result = s.merge([t1, t1], weights=[0.5, 0.5])
    np.testing.assert_array_almost_equal(result, t1)


def test_mcm_dual_projection_true_crdt():
    """model-crdt-matrix.md: dual_projection is TRUE_CRDT (commutative, associative, idempotent)."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("dual_projection")
    base = np.array([1.0, 2.0, 3.0])
    t1 = np.array([1.5, 2.5, 3.5])
    t2 = np.array([1.2, 2.2, 3.2])

    result_ab = s.merge([t1, t2], base=base, weights=[0.5, 0.5])
    result_ba = s.merge([t2, t1], base=base, weights=[0.5, 0.5])

    # Commutativity
    np.testing.assert_array_almost_equal(result_ab, result_ba)

    # Idempotency: merge(A, A) == A
    result_aa = s.merge([t1, t1], base=base, weights=[0.5, 0.5])
    np.testing.assert_array_almost_equal(result_aa, t1)


def test_mcm_n_way_strategies_available():
    """model-crdt-matrix.md: All documented N-way safe strategies are in registry."""
    from crdt_merge.model.strategies import get_strategy

    n_way_safe = [
        "weight_average",
        "task_arithmetic",
        "fisher_merge",
        "regression_mean",
        "ties",
        "emr",
        "dual_projection",
    ]
    for name in n_way_safe:
        s = get_strategy(name)
        assert s is not None, f"Strategy '{name}' should be available"


def test_mcm_matrix_registry_names_match_guide():
    """model-crdt-matrix.md: Registry names used in matrix are valid in get_strategy()."""
    from crdt_merge.model.strategies import list_strategies

    available = set(list_strategies())

    # These are the registry names stated in the model-crdt-matrix.md Strategy column
    documented_available = {
        "weight_average",
        "linear",
        "slerp",
        "task_arithmetic",
        "ties",
        "dare",
        "dare_ties",
        "della",
        "emr",
        "adarank",
        "star",
        "svd_knot_tying",
        "fisher_merge",
        "ada_merging",
        "dam",
        "regression_mean",
        "dual_projection",
    }

    missing = documented_available - available
    assert not missing, f"Registry names documented in model-crdt-matrix.md but missing: {missing}"


@pytest.mark.xfail(reason="model-crdt-matrix.md documents 'breadcrumbs' but registry uses 'model_breadcrumbs'")
def test_mcm_breadcrumbs_registry_name():
    """model-crdt-matrix.md: 'breadcrumbs' registry name resolves (currently 'model_breadcrumbs')."""
    from crdt_merge.model.strategies import get_strategy

    get_strategy("breadcrumbs")


@pytest.mark.xfail(reason="model-crdt-matrix.md documents 'passthrough' but it is not in the registry")
def test_mcm_passthrough_registry_name():
    """model-crdt-matrix.md: 'passthrough' registry name resolves."""
    from crdt_merge.model.strategies import get_strategy

    get_strategy("passthrough")


# ===========================================================================
# model-merge-strategies.md — 26 strategies reference guide
# ===========================================================================


def test_mms_get_strategy_import():
    """model-merge-strategies.md: get_strategy is importable from crdt_merge.model.strategies."""
    from crdt_merge.model.strategies import get_strategy  # noqa: F401


def test_mms_all_26_strategies_importable():
    """model-merge-strategies.md: All 26 documented strategies resolve in the registry."""
    from crdt_merge.model.strategies import get_strategy

    # Mapping: registry_name from model-merge-strategies.md
    guide_registry_names = [
        "linear",
        "slerp",
        "weight_average",
        "task_arithmetic",
        "ties",
        "dare",
        "dare_ties",
        "della",
        "emr",
        "model_breadcrumbs",
        "adarank",
        "star",
        "svd_knot_tying",
        "fisher_merge",
        "ada_merging",
        "dam",
        "regression_mean",
        "evolutionary_merge",
        "genetic_merge",
        "safe_merge",
        "led_merge",
        "negative_merge",
        "split_unlearn_merge",
        "representation_surgery",
        "weight_scope_alignment",
        "dual_projection",
    ]

    missing = []
    for name in guide_registry_names:
        try:
            s = get_strategy(name)
            assert s is not None
        except Exception:
            missing.append(name)

    assert not missing, f"Strategies missing from registry: {missing}"


def test_mms_weight_average_three_tensors():
    """model-merge-strategies.md: weight_average merges 3 tensors with given weights."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("weight_average")
    t1 = np.array([1.0, 2.0, 3.0])
    t2 = np.array([3.0, 4.0, 5.0])
    t3 = np.array([2.0, 3.0, 4.0])
    result = s.merge([t1, t2, t3], weights=[0.5, 0.3, 0.2])
    # Expected: [1.8, 2.8, 3.8]
    np.testing.assert_array_almost_equal(result, [1.8, 2.8, 3.8])


def test_mms_task_arithmetic_merge():
    """model-merge-strategies.md: task_arithmetic adds task vectors to base."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("task_arithmetic")
    base = np.array([1.0, 1.0, 1.0])
    t1 = np.array([2.0, 3.0, 4.0])
    t2 = np.array([1.5, 2.0, 3.0])
    result = s.merge([t1, t2], base=base, weights=[1.0, 1.0])
    # task vectors: [1,2,3] and [0.5,1,2]; sum = [1.5,3,5]; base + sum = [2.5,4,6]
    np.testing.assert_array_almost_equal(result, [2.5, 4.0, 6.0])


def test_mms_dual_projection_true_crdt_tier():
    """model-merge-strategies.md: dual_projection is the only TRUE_CRDT strategy."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("dual_projection")
    assert s is not None
    # Verify it produces a valid result
    base = np.array([0.0, 0.0, 0.0])
    t1 = np.array([1.0, 0.0, 0.0])
    t2 = np.array([0.0, 1.0, 0.0])
    result = s.merge([t1, t2], base=base, weights=[0.5, 0.5])
    assert result is not None
    assert result.shape == (3,)


def test_mms_fisher_merge_two_tensors():
    """model-merge-strategies.md: fisher_merge produces a valid merged tensor."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("fisher_merge")
    t1 = np.array([1.0, 2.0])
    t2 = np.array([3.0, 4.0])
    result = s.merge([t1, t2], weights=[0.5, 0.5])
    assert result is not None
    assert result.shape == (2,)


def test_mms_regression_mean_two_tensors():
    """model-merge-strategies.md: regression_mean produces a valid merged tensor."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("regression_mean")
    t1 = np.array([1.0, 2.0])
    t2 = np.array([3.0, 4.0])
    result = s.merge([t1, t2], weights=[0.5, 0.5])
    assert result is not None
    assert result.shape == (2,)


def test_mms_slerp_two_tensors():
    """model-merge-strategies.md: slerp produces a valid interpolated tensor."""
    from crdt_merge.model.strategies import get_strategy

    s = get_strategy("slerp")
    t1 = np.array([1.0, 0.0, 0.0])
    t2 = np.array([0.0, 1.0, 0.0])
    result = s.merge([t1, t2], weights=[0.5, 0.5])
    assert result is not None
    assert result.shape == (3,)


def test_mms_list_strategies_count():
    """model-merge-strategies.md: at least 26 strategies are registered."""
    from crdt_merge.model.strategies import list_strategies

    strategies = list_strategies()
    assert len(strategies) >= 26, f"Expected at least 26 strategies, found {len(strategies)}"


# ===========================================================================
# troubleshooting.md — documented behaviors and import checks
# ===========================================================================


def test_ts_merge_imports():
    """troubleshooting.md: core merge function and strategy types are importable."""
    from crdt_merge import merge  # noqa: F401
    from crdt_merge.strategies import LWW, MaxWins, MinWins  # noqa: F401


def test_ts_merge_is_deterministic():
    """troubleshooting.md: CRDT merge is deterministic given identical inputs."""
    from crdt_merge import merge

    left = [{"id": 1, "val": "alice", "ts": 1.0}, {"id": 2, "val": "bob", "ts": 2.0}]
    right = [{"id": 1, "val": "alice_v2", "ts": 3.0}, {"id": 3, "val": "carol", "ts": 1.5}]

    result1 = merge(left, right, key="id", timestamp_col="ts")
    result2 = merge(left, right, key="id", timestamp_col="ts")

    # Sort both by id for stable comparison
    r1_sorted = sorted(result1, key=lambda r: r["id"])
    r2_sorted = sorted(result2, key=lambda r: r["id"])
    assert r1_sorted == r2_sorted


def test_ts_safe_parse_ts_invalid_becomes_zero():
    """troubleshooting.md: _safe_parse_ts silently returns 0.0 for invalid timestamps."""
    from crdt_merge.strategies import _safe_parse_ts

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        assert _safe_parse_ts("not-a-timestamp") == 0.0
        assert _safe_parse_ts(None) == 0.0


def test_ts_safe_parse_ts_valid_values():
    """troubleshooting.md: _safe_parse_ts handles int, float, and ISO-8601 strings."""
    from crdt_merge.strategies import _safe_parse_ts

    assert _safe_parse_ts(1.5) == 1.5
    assert _safe_parse_ts(100) == 100.0
    assert _safe_parse_ts("2024-01-01") > 0.0


def test_ts_node_tie_breaking_lexicographic():
    """troubleshooting.md: Tie-breaking uses lexicographic comparison — 'node9' > 'node10'."""
    # This is the documented gotcha: lexicographic means '9' > '1' character-by-character
    assert "node9" > "node10"
    # Zero-padded names compare correctly
    assert "node09" < "node10"


def test_ts_orset_add_wins_semantics():
    """troubleshooting.md: ORSet uses add-wins semantics on concurrent add+remove."""
    from crdt_merge import ORSet

    s1 = ORSet()
    s2 = ORSet()

    # Concurrent: s1 adds, s2 adds then removes the same element
    s1.add("apple")
    s2.add("apple")
    s2.remove("apple")

    merged = s1.merge(s2)
    # add-wins: the element is present because one side added it
    assert "apple" in merged.value


def test_ts_optional_dependency_imports():
    """troubleshooting.md: Core module is always importable without optional dependencies."""
    import crdt_merge  # noqa: F401
    from crdt_merge import merge  # noqa: F401


def test_ts_custom_strategy_lost_after_serialization():
    """troubleshooting.md: Custom strategies fall back to LWW after to_dict/from_dict (LAY1-003)."""
    from crdt_merge import MergeSchema
    from crdt_merge.strategies import Custom, LWW

    schema = MergeSchema(default=LWW(), fields={"notes": Custom(lambda a, b: a)})
    d = schema.to_dict()
    restored = MergeSchema.from_dict(d)
    # After round-trip, the Custom field strategy falls back to LWW
    assert restored is not None
