"""Tests for pluggable encryption backends in crdt_merge.encryption."""

import secrets

import pytest

# ---------------------------------------------------------------------------
# Detect whether the cryptography Rust bindings are actually functional.
# The top-level `import cryptography` may succeed while the Rust-backed AEAD
# primitives (AESGCM, ChaCha20Poly1305, etc.) throw pyo3 PanicException
# (a BaseException subclass) on first use.  All tests that require AEAD must
# skip rather than error when this environment is detected.
# ---------------------------------------------------------------------------
def _aead_available() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        AESGCM(secrets.token_bytes(32))
        return True
    except BaseException:
        return False

def _aesgcmsiv_available() -> bool:
    """AES-GCM-SIV requires cryptography >= 42.0.0."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
        AESGCMSIV(secrets.token_bytes(32))
        return True
    except BaseException:
        return False

AEAD_AVAILABLE = _aead_available()
AESGCMSIV_AVAILABLE = _aesgcmsiv_available()
requires_aead = pytest.mark.skipif(
    not AEAD_AVAILABLE,
    reason="cryptography AEAD Rust bindings unavailable in this environment",
)
requires_siv = pytest.mark.skipif(
    not AESGCMSIV_AVAILABLE,
    reason="AES-GCM-SIV requires cryptography>=42.0.0",
)

from crdt_merge.encryption import (
    CryptoBackend,
    EncryptedMerge,
    EncryptedValue,
    StaticKeyProvider,
    XORLegacyBackend,
    _BACKEND_REGISTRY,
    get_backend,
    register_backend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_warned():
    """Reset the warning guard before each test."""
    EncryptedMerge._warned = False
    yield
    EncryptedMerge._warned = False


def _make_provider(key: bytes | None = None) -> StaticKeyProvider:
    return StaticKeyProvider(key or secrets.token_bytes(32))


def _make_em(backend: str = "auto", key: bytes | None = None) -> EncryptedMerge:
    return EncryptedMerge(_make_provider(key), backend=backend)


# ---------------------------------------------------------------------------
# 1. TestCryptoBackendRegistry
# ---------------------------------------------------------------------------

class TestCryptoBackendRegistry:
    """Backend registry tests."""

    def test_xor_legacy_always_registered(self):
        assert "xor-legacy" in _BACKEND_REGISTRY

    def test_aead_backends_registered_when_cryptography_available(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        assert "aes-256-gcm" in _BACKEND_REGISTRY
        assert "chacha20-poly1305" in _BACKEND_REGISTRY
        if AESGCMSIV_AVAILABLE:
            assert "aes-256-gcm-siv" in _BACKEND_REGISTRY

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown crypto backend"):
            get_backend("nonexistent-cipher")

    def test_register_custom_backend(self):
        class DummyBackend(CryptoBackend):
            name = "dummy-test"
            def encrypt(self, key, plaintext, associated_data=None):
                return plaintext, b"\x00" * 12, b"\x00" * 16
            def decrypt(self, key, ciphertext, nonce, tag, associated_data=None):
                return ciphertext

        register_backend("dummy-test", DummyBackend)
        try:
            b = get_backend("dummy-test")
            assert isinstance(b, DummyBackend)
            assert b.name == "dummy-test"
        finally:
            _BACKEND_REGISTRY.pop("dummy-test", None)

    def test_get_backend_returns_correct_type(self):
        b = get_backend("xor-legacy")
        assert isinstance(b, XORLegacyBackend)
        assert b.name == "xor-legacy"


# ---------------------------------------------------------------------------
# 2. TestAES256GCMBackend
# ---------------------------------------------------------------------------

class TestAES256GCMBackend:
    """AES-256-GCM backend tests."""

    @pytest.fixture(autouse=True)
    def _require_cryptography(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        from crdt_merge.encryption import AES256GCMBackend
        self.backend = AES256GCMBackend()
        self.key = secrets.token_bytes(32)

    def test_round_trip(self):
        pt = b"hello world"
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_different_nonces(self):
        pt = b"same plaintext"
        _, n1, _ = self.backend.encrypt(self.key, pt)
        _, n2, _ = self.backend.encrypt(self.key, pt)
        assert n1 != n2

    def test_tampered_ciphertext_raises(self):
        pt = b"secret data"
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        bad_ct = bytearray(ct)
        bad_ct[0] ^= 0xFF
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(self.key, bytes(bad_ct), nonce, tag)

    def test_tampered_tag_raises(self):
        pt = b"data"
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        bad_tag = bytearray(tag)
        bad_tag[0] ^= 0xFF
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(self.key, ct, nonce, bytes(bad_tag))

    def test_wrong_key_raises(self):
        pt = b"message"
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        wrong_key = secrets.token_bytes(32)
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(wrong_key, ct, nonce, tag)

    def test_associated_data_mismatch_raises(self):
        pt = b"message"
        ct, nonce, tag = self.backend.encrypt(self.key, pt, associated_data=b"aad1")
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(self.key, ct, nonce, tag, associated_data=b"aad2")

    def test_empty_plaintext(self):
        pt = b""
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_large_plaintext(self):
        pt = secrets.token_bytes(10240)
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_unicode_plaintext(self):
        pt = "café ☕ 日本語 ".encode("utf-8")
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_key_derivation_produces_32_bytes(self):
        provider = _make_provider()
        k = provider.get_key("any_field")
        assert len(k) == 32


# ---------------------------------------------------------------------------
# 3. TestAESGCMSIVBackend
# ---------------------------------------------------------------------------

class TestAESGCMSIVBackend:
    """AES-256-GCM-SIV backend tests."""

    @pytest.fixture(autouse=True)
    def _require_cryptography(self):
        if not AESGCMSIV_AVAILABLE:
            pytest.skip("AES-GCM-SIV requires cryptography>=42.0.0")
        from crdt_merge.encryption import AESGCMSIVBackend
        self.backend = AESGCMSIVBackend()
        self.key = secrets.token_bytes(32)

    def test_round_trip(self):
        pt = b"test data"
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_different_nonces(self):
        pt = b"same"
        _, n1, _ = self.backend.encrypt(self.key, pt)
        _, n2, _ = self.backend.encrypt(self.key, pt)
        assert n1 != n2

    def test_tampered_ciphertext_raises(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"data")
        bad = bytearray(ct)
        bad[0] ^= 0xFF
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(self.key, bytes(bad), nonce, tag)

    def test_wrong_key_raises(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"x")
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(secrets.token_bytes(32), ct, nonce, tag)

    def test_empty_plaintext(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"")
        assert self.backend.decrypt(self.key, ct, nonce, tag) == b""

    def test_large_plaintext(self):
        pt = secrets.token_bytes(10240)
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_round_trip_with_associated_data(self):
        pt = b"payload"
        aad = b"context"
        ct, nonce, tag = self.backend.encrypt(self.key, pt, associated_data=aad)
        assert self.backend.decrypt(self.key, ct, nonce, tag, associated_data=aad) == pt

    def test_associated_data_mismatch_raises(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"x", associated_data=b"a")
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(self.key, ct, nonce, tag, associated_data=b"b")


# ---------------------------------------------------------------------------
# 4. TestChaCha20Poly1305Backend
# ---------------------------------------------------------------------------

class TestChaCha20Poly1305Backend:
    """ChaCha20-Poly1305 backend tests."""

    @pytest.fixture(autouse=True)
    def _require_cryptography(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        from crdt_merge.encryption import ChaCha20Poly1305Backend
        self.backend = ChaCha20Poly1305Backend()
        self.key = secrets.token_bytes(32)

    def test_round_trip(self):
        pt = b"chacha test"
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_different_nonces(self):
        _, n1, _ = self.backend.encrypt(self.key, b"x")
        _, n2, _ = self.backend.encrypt(self.key, b"x")
        assert n1 != n2

    def test_tampered_ciphertext_raises(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"data")
        bad = bytearray(ct)
        bad[0] ^= 0xFF
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(self.key, bytes(bad), nonce, tag)

    def test_wrong_key_raises(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"msg")
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(secrets.token_bytes(32), ct, nonce, tag)

    def test_empty_plaintext(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"")
        assert self.backend.decrypt(self.key, ct, nonce, tag) == b""

    def test_large_plaintext(self):
        pt = secrets.token_bytes(10240)
        ct, nonce, tag = self.backend.encrypt(self.key, pt)
        assert self.backend.decrypt(self.key, ct, nonce, tag) == pt

    def test_round_trip_with_associated_data(self):
        pt = b"payload"
        aad = b"header"
        ct, nonce, tag = self.backend.encrypt(self.key, pt, associated_data=aad)
        assert self.backend.decrypt(self.key, ct, nonce, tag, associated_data=aad) == pt

    def test_associated_data_mismatch_raises(self):
        ct, nonce, tag = self.backend.encrypt(self.key, b"data", associated_data=b"a")
        with pytest.raises(ValueError, match="Authentication failed"):
            self.backend.decrypt(self.key, ct, nonce, tag, associated_data=b"b")


# ---------------------------------------------------------------------------
# 5. TestBackwardCompatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Wire format backward compatibility between v1 (XOR) and v2 (AEAD)."""

    def test_xor_encrypted_decrypts_with_aead_em(self):
        """XOR-encrypted data decrypts via auto-routing even when EM uses AES-GCM."""
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)

        em_xor = EncryptedMerge(prov, backend="xor-legacy")
        ev = em_xor.encrypt_field("secret", "f")
        d = ev.to_dict()

        # Decrypt with AES-GCM EncryptedMerge — should auto-route to XOR
        em_gcm = EncryptedMerge(prov, backend="aes-256-gcm")
        restored = EncryptedValue.from_dict(d)
        assert em_gcm.decrypt_field(restored) == "secret"

    def test_aes_gcm_serialize_deserialize_decrypt(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="aes-256-gcm")

        ev = em.encrypt_field({"key": "value"}, "data")
        d = ev.to_dict()
        assert d["cipher"] == "aes-256-gcm"
        assert d["version"] == 2

        restored = EncryptedValue.from_dict(d)
        assert em.decrypt_field(restored) == {"key": "value"}

    def test_v1_wire_format_no_cipher_field(self):
        """v1 dicts (no cipher key) decrypt correctly."""
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="xor-legacy")

        ev = em.encrypt_field(42, "num")
        d = ev.to_dict()
        assert "cipher" not in d
        assert "version" not in d

        restored = EncryptedValue.from_dict(d)
        assert em.decrypt_field(restored) == 42

    def test_v2_wire_format_has_cipher_field(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="chacha20-poly1305")

        ev = em.encrypt_field("test", "f")
        d = ev.to_dict()
        assert d["cipher"] == "chacha20-poly1305"
        assert d["version"] == 2

        restored = EncryptedValue.from_dict(d)
        assert em.decrypt_field(restored) == "test"

    def test_mixed_v1_v2_decrypt_records(self):
        """decrypt_records handles a mix of v1 and v2 encrypted fields."""
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)

        em_xor = EncryptedMerge(prov, backend="xor-legacy")
        em_gcm = EncryptedMerge(prov, backend="aes-256-gcm")

        rec = {
            "id": "1",
            "legacy_field": em_xor.encrypt_field("old", "legacy_field").to_dict(),
            "modern_field": em_gcm.encrypt_field("new", "modern_field").to_dict(),
        }

        decrypted = em_gcm.decrypt_records([rec])
        assert decrypted[0]["legacy_field"] == "old"
        assert decrypted[0]["modern_field"] == "new"

    def test_rotate_key_xor_to_aes_gcm(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        old_key = secrets.token_bytes(32)
        new_key = secrets.token_bytes(32)
        old_prov = StaticKeyProvider(old_key)
        new_prov = StaticKeyProvider(new_key)

        # Encrypt with XOR
        em_old = EncryptedMerge(old_prov, backend="xor-legacy")
        records = em_old.encrypt_records([{"id": "1", "val": "classified"}], key="id")

        # Rotate to AES-GCM
        em_new = EncryptedMerge(new_prov, backend="aes-256-gcm")
        rotated = em_new.rotate_key(records, old_prov, new_prov)

        # Should now be v2 (AES-GCM)
        assert rotated[0]["val"]["cipher"] == "aes-256-gcm"
        dec = em_new.decrypt_records(rotated)
        assert dec[0]["val"] == "classified"

    def test_rotate_key_aes_gcm_to_chacha(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        old_key = secrets.token_bytes(32)
        new_key = secrets.token_bytes(32)
        old_prov = StaticKeyProvider(old_key)
        new_prov = StaticKeyProvider(new_key)

        # Encrypt with AES-GCM
        em_old = EncryptedMerge(old_prov, backend="aes-256-gcm")
        records = em_old.encrypt_records([{"id": "1", "s": "data"}], key="id")

        # Rotate to ChaCha20
        em_new = EncryptedMerge(new_prov, backend="chacha20-poly1305")
        rotated = em_new.rotate_key(records, old_prov, new_prov)

        assert rotated[0]["s"]["cipher"] == "chacha20-poly1305"
        dec = em_new.decrypt_records(rotated)
        assert dec[0]["s"] == "data"

    def test_old_key_cannot_decrypt_after_rotation(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        old_key = secrets.token_bytes(32)
        new_key = secrets.token_bytes(32)
        old_prov = StaticKeyProvider(old_key)
        new_prov = StaticKeyProvider(new_key)

        em_old = EncryptedMerge(old_prov, backend="aes-256-gcm")
        records = em_old.encrypt_records([{"id": "1", "x": "secret"}], key="id")

        em_new = EncryptedMerge(new_prov, backend="aes-256-gcm")
        rotated = em_new.rotate_key(records, old_prov, new_prov)

        with pytest.raises(ValueError, match="Authentication failed"):
            em_old.decrypt_records(rotated)


# ---------------------------------------------------------------------------
# 6. TestEncryptedMergeWithBackends
# ---------------------------------------------------------------------------

class TestEncryptedMergeWithBackends:
    """End-to-end merge operations with various backends."""

    @pytest.fixture(autouse=True)
    def _require_cryptography(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")

    def test_merge_with_aes_gcm(self):
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="aes-256-gcm")

        left = em.encrypt_records([{"id": "1", "v": 10}], key="id")
        right = em.encrypt_records([{"id": "2", "v": 20}], key="id")
        merged = em.merge_encrypted(left, right, key="id")
        dec = em.decrypt_records(merged)
        ids = {r["id"] for r in dec}
        assert ids == {"1", "2"}

    def test_merge_mixed_v1_v2(self):
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em_xor = EncryptedMerge(prov, backend="xor-legacy")
        em_gcm = EncryptedMerge(prov, backend="aes-256-gcm")

        left = em_xor.encrypt_records([{"id": "1", "v": "old"}], key="id")
        right = em_gcm.encrypt_records([{"id": "2", "v": "new"}], key="id")
        merged = em_gcm.merge_encrypted(left, right, key="id")
        dec = em_gcm.decrypt_records(merged)
        vals = {r["id"]: r["v"] for r in dec}
        assert vals == {"1": "old", "2": "new"}

    def test_order_tags_backend_independent(self):
        """Order tags are HMAC-based and don't depend on the crypto backend."""
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)

        em_xor = EncryptedMerge(prov, backend="xor-legacy")
        em_gcm = EncryptedMerge(prov, backend="aes-256-gcm")
        em_cc = EncryptedMerge(prov, backend="chacha20-poly1305")

        tag_xor = em_xor.encrypt_field(42, "f").order_tag
        tag_gcm = em_gcm.encrypt_field(42, "f").order_tag
        tag_cc = em_cc.encrypt_field(42, "f").order_tag

        assert tag_xor == tag_gcm == tag_cc

        if AESGCMSIV_AVAILABLE:
            em_siv = EncryptedMerge(prov, backend="aes-256-gcm-siv")
            tag_siv = em_siv.encrypt_field(42, "f").order_tag
            assert tag_xor == tag_siv

    def test_encrypt_records_explicit_siv(self):
        if not AESGCMSIV_AVAILABLE:
            pytest.skip("AES-GCM-SIV requires cryptography>=42.0.0")
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="aes-256-gcm-siv")
        records = em.encrypt_records([{"id": "1", "msg": "hello"}], key="id")
        assert records[0]["msg"]["cipher"] == "aes-256-gcm-siv"

        dec = em.decrypt_records(records)
        assert dec[0]["msg"] == "hello"

    def test_full_pipeline_aes_gcm(self):
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="aes-256-gcm")
        left = em.encrypt_records([{"id": "1", "x": 100}], key="id")
        right = em.encrypt_records([{"id": "1", "x": 200}], key="id")
        merged = em.merge_encrypted(left, right, key="id")
        dec = em.decrypt_records(merged)
        assert len(dec) == 1
        assert dec[0]["x"] in (100, 200)

    def test_full_pipeline_chacha(self):
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="chacha20-poly1305")
        left = em.encrypt_records([{"id": "A", "v": "alpha"}], key="id")
        right = em.encrypt_records([{"id": "B", "v": "beta"}], key="id")
        merged = em.merge_encrypted(left, right, key="id")
        dec = em.decrypt_records(merged)
        assert {r["id"] for r in dec} == {"A", "B"}

    def test_full_pipeline_gcm_siv(self):
        if not AESGCMSIV_AVAILABLE:
            pytest.skip("AES-GCM-SIV requires cryptography>=42.0.0")
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="aes-256-gcm-siv")
        left = em.encrypt_records([{"id": "1", "d": {"nested": True}}], key="id")
        right = em.encrypt_records([{"id": "2", "d": [1, 2, 3]}], key="id")
        merged = em.merge_encrypted(left, right, key="id")
        dec = em.decrypt_records(merged)
        assert len(dec) == 2

    def test_full_pipeline_xor_legacy(self):
        key = secrets.token_bytes(32)
        prov = StaticKeyProvider(key)
        em = EncryptedMerge(prov, backend="xor-legacy")
        left = em.encrypt_records([{"id": "1", "s": "left"}], key="id")
        right = em.encrypt_records([{"id": "1", "s": "right"}], key="id")
        merged = em.merge_encrypted(left, right, key="id")
        dec = em.decrypt_records(merged)
        assert len(dec) == 1
        assert dec[0]["s"] in ("left", "right")


# ---------------------------------------------------------------------------
# 7. TestAutoDetection
# ---------------------------------------------------------------------------

class TestAutoDetection:
    """Backend auto-detection and selection."""

    def test_auto_uses_best_available(self):
        """With cryptography installed, auto picks AES-256-GCM."""
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        em = _make_em(backend="auto")
        assert em._backend.name == "aes-256-gcm"

    def test_explicit_xor_legacy(self):
        em = _make_em(backend="xor-legacy")
        assert em._backend.name == "xor-legacy"

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown crypto backend"):
            _make_em(backend="nonexistent-cipher")

    def test_backend_name_accessible(self):
        if not AEAD_AVAILABLE:
            pytest.skip("cryptography AEAD unavailable")
        em = _make_em(backend="chacha20-poly1305")
        assert em._backend.name == "chacha20-poly1305"
