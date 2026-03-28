import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _get_key() -> bytes:
    """환경변수 또는 JWT 시크릿에서 32바이트 키 파생"""
    key_source = settings.JWT_SECRET_KEY.encode()
    # SHA-256으로 정확히 32바이트 키 생성
    return hashlib.sha256(key_source).digest()


def encrypt_api_key(plaintext: str) -> bytes:
    """API Key를 AES-256-GCM으로 암호화. 반환값: nonce(12) + ciphertext"""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt_api_key(encrypted: bytes) -> str:
    """암호화된 API Key 복호화"""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
