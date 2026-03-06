"""Tests for Stage 4 — ChaCha20 Symmetric Encryption."""

import pytest

from blackhorse.crypto.symmetric import ChaCha20Cipher
from blackhorse.crypto.symmetric.chacha20 import ChaCha20Error


class TestChaCha20:
    def setup_method(self):
        self.cipher = ChaCha20Cipher()
        self.key = ChaCha20Cipher.generate_key()
        self.nonce = ChaCha20Cipher.generate_nonce()

    def test_encrypt_decrypt_round_trip(self):
        plaintext = b"Hello, Blackhorse!"
        ciphertext = self.cipher.encrypt(self.key, self.nonce, plaintext)
        recovered = self.cipher.decrypt(self.key, self.nonce, ciphertext)
        assert recovered == plaintext

    def test_ciphertext_differs_from_plaintext(self):
        plaintext = b"top secret data"
        ciphertext = self.cipher.encrypt(self.key, self.nonce, plaintext)
        assert ciphertext != plaintext

    def test_ciphertext_same_length_as_plaintext(self):
        plaintext = b"A" * 100
        ciphertext = self.cipher.encrypt(self.key, self.nonce, plaintext)
        assert len(ciphertext) == len(plaintext)

    def test_different_nonces_produce_different_ciphertext(self):
        plaintext = b"same plaintext"
        n1 = ChaCha20Cipher.generate_nonce()
        n2 = ChaCha20Cipher.generate_nonce()
        ct1 = self.cipher.encrypt(self.key, n1, plaintext)
        ct2 = self.cipher.encrypt(self.key, n2, plaintext)
        assert ct1 != ct2

    def test_different_keys_produce_different_ciphertext(self):
        plaintext = b"same plaintext"
        key2 = ChaCha20Cipher.generate_key()
        ct1 = self.cipher.encrypt(self.key, self.nonce, plaintext)
        ct2 = self.cipher.encrypt(key2, self.nonce, plaintext)
        assert ct1 != ct2

    def test_wrong_key_decrypts_to_garbage(self):
        plaintext = b"secret message"
        ciphertext = self.cipher.encrypt(self.key, self.nonce, plaintext)
        wrong_key = ChaCha20Cipher.generate_key()
        garbage = self.cipher.decrypt(wrong_key, self.nonce, ciphertext)
        assert garbage != plaintext

    def test_empty_plaintext(self):
        ciphertext = self.cipher.encrypt(self.key, self.nonce, b"")
        assert ciphertext == b""
        assert self.cipher.decrypt(self.key, self.nonce, b"") == b""

    def test_generate_key_length(self):
        key = ChaCha20Cipher.generate_key()
        assert len(key) == ChaCha20Cipher.KEY_SIZE

    def test_generate_nonce_length(self):
        nonce = ChaCha20Cipher.generate_nonce()
        assert len(nonce) == ChaCha20Cipher.NONCE_SIZE

    def test_generate_key_is_random(self):
        k1 = ChaCha20Cipher.generate_key()
        k2 = ChaCha20Cipher.generate_key()
        assert k1 != k2

    def test_counter_parameter(self):
        plaintext = b"counter test"
        ct0 = self.cipher.encrypt(self.key, self.nonce, plaintext, counter=0)
        ct1 = self.cipher.encrypt(self.key, self.nonce, plaintext, counter=1)
        assert ct0 != ct1
        assert self.cipher.decrypt(self.key, self.nonce, ct0, counter=0) == plaintext

    def test_bad_key_length_raises(self):
        with pytest.raises(ChaCha20Error):
            self.cipher.encrypt(b"short_key", self.nonce, b"data")

    def test_bad_nonce_length_raises(self):
        with pytest.raises(ChaCha20Error):
            self.cipher.encrypt(self.key, b"short", b"data")

    def test_large_data_round_trip(self):
        plaintext = bytes(range(256)) * 100   # 25 600 bytes
        ciphertext = self.cipher.encrypt(self.key, self.nonce, plaintext)
        recovered = self.cipher.decrypt(self.key, self.nonce, ciphertext)
        assert recovered == plaintext
