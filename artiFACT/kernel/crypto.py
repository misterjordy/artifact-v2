"""Encryption helpers (AES-256-GCM for user AI keys)."""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from artiFACT.kernel.config import settings

_NONCE_SIZE = 12


def _get_master_key() -> bytes:
    raw = settings.SECRET_KEY.encode()
    if len(raw) < 32:
        raw = raw.ljust(32, b"\0")
    return raw[:32]


def encrypt(plaintext: str) -> bytes:
    key = _get_master_key()
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ct


def decrypt(ciphertext: bytes) -> str:
    key = _get_master_key()
    nonce = ciphertext[:_NONCE_SIZE]
    ct = ciphertext[_NONCE_SIZE:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()
