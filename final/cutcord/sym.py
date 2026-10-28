"""Symmetric building blocks: HKDF-SHA256, AES-128-GCM, HMAC-SHA256."""
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def kdf(*parts, length=16):
    ikm = b"".join(len(p).to_bytes(4, "big") + p for p in parts)
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=b"cutcord").derive(ikm)


def seal(key, plaintext, ad=b""):
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, ad)


def open_(key, blob, ad=b""):
    """returns plaintext, or None if authentication fails"""
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], ad)
    except InvalidTag:
        return None


def mac(key, *parts):
    return hmac.new(key, b"".join(len(p).to_bytes(4, "big") + p for p in parts), hashlib.sha256).digest()


def mac_ok(key, tag, *parts):
    return hmac.compare_digest(mac(key, *parts), tag)
