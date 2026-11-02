"""
Zero-Knowledge & Server-Side AES-256-GCM Encryption Engine for PostgreSQL Chat History.
Matches Reeve memory graph cryptographic standards.

Prefixes:
  - 'enc:v2:zk:<base64(12B nonce + ciphertext + 16B tag)>' -> Sealed with Client 12-word Key.
  - 'enc:v2:srv:<base64(12B nonce + ciphertext + 16B tag)>' -> Shielded with Server-derived Key.
  - Legacy plaintext -> Unencrypted historical messages (auto-upgraded on next access).
"""

from __future__ import annotations
import base64
import hashlib
import hmac
import os
import logging
from typing import Any
from django.conf import settings
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("amour.crypto")

PREFIX_ZK = "enc:v2:zk:"
PREFIX_SRV = "enc:v2:srv:"
PREFIX_GENERIC = "enc:v2:"
NONCE_LENGTH = 12


def _get_master_server_key() -> bytes:
    raw = getattr(settings, "CHAT_ENCRYPTION_MASTER_KEY", None) or getattr(settings, "SECRET_KEY", "amour-default-secret-salt")
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return hashlib.sha256(raw).digest()


def derive_server_user_key(user_id: str) -> bytes:
    """Derives a deterministic 256-bit AES key for a specific user using HMAC-SHA256."""
    master = _get_master_server_key()
    user_bytes = str(user_id or "anonymous").encode("utf-8")
    return hmac.new(master, b"amour_user_chat_v1:" + user_bytes, hashlib.sha256).digest()


def normalize_client_key(user_key: str | bytes | None) -> bytes | None:
    """Normalizes client key to 32 bytes."""
    if not user_key:
        return None
    if isinstance(user_key, str):
        kb = user_key.strip().encode("utf-8")
    else:
        kb = bytes(user_key)
    if len(kb) == 32:
        return kb
    return hashlib.sha256(kb).digest()


def is_encrypted_message(text: str | None) -> bool:
    if not text or not isinstance(text, str):
        return False
    return text.startswith(PREFIX_GENERIC)


def encrypt_chat_message(plaintext: str, user_id: str, client_key: str | bytes | None = None) -> str:
    """
    Encrypts a chat message with AES-256-GCM.
    Prioritizes client zero-knowledge key ('enc:v2:zk:').
    Falls back to server-derived key ('enc:v2:srv:').
    """
    if plaintext is None:
        return ""
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)

    normalized_client = normalize_client_key(client_key)
    if normalized_client:
        key = normalized_client
        prefix = PREFIX_ZK
    else:
        key = derive_server_user_key(user_id)
        prefix = PREFIX_SRV

    try:
        aesgcm = AESGCM(key)
        nonce = os.urandom(NONCE_LENGTH)
        ct_and_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        payload = base64.b64encode(nonce + ct_and_tag).decode("ascii")
        return f"{prefix}{payload}"
    except Exception as exc:
        logger.error(f"Failed to encrypt chat message: {exc}")
        return plaintext


def decrypt_chat_message(ciphertext: str, user_id: str, client_key: str | bytes | None = None) -> str:
    """
    Decrypts an AES-256-GCM chat message.
    - If 'enc:v2:zk:': requires valid client_key. If missing, returns placeholder.
    - If 'enc:v2:srv:': decrypts using server-derived key for user_id.
    - If legacy plaintext: returns as-is.
    """
    if not ciphertext or not isinstance(ciphertext, str):
        return ""

    if not ciphertext.startswith(PREFIX_GENERIC):
        return ciphertext  # Legacy plaintext

    # 1. Zero-Knowledge Client Ciphertext
    if ciphertext.startswith(PREFIX_ZK):
        normalized_client = normalize_client_key(client_key)
        if not normalized_client:
            return "[🔒 Encrypted Message]"
        try:
            raw = base64.b64decode(ciphertext[len(PREFIX_ZK):])
            if len(raw) < NONCE_LENGTH + 16:
                return "[Decryption Error: Malformed Payload]"
            nonce = raw[:NONCE_LENGTH]
            ct_and_tag = raw[NONCE_LENGTH:]
            aesgcm = AESGCM(normalized_client)
            decrypted = aesgcm.decrypt(nonce, ct_and_tag, None)
            return decrypted.decode("utf-8")
        except Exception:
            return "[🔒 Encrypted Message]"

    # 2. Server-Shielded Ciphertext
    if ciphertext.startswith(PREFIX_SRV):
        srv_key = derive_server_user_key(user_id)
        try:
            raw = base64.b64decode(ciphertext[len(PREFIX_SRV):])
            if len(raw) < NONCE_LENGTH + 16:
                return "[Decryption Error: Malformed Payload]"
            nonce = raw[:NONCE_LENGTH]
            ct_and_tag = raw[NONCE_LENGTH:]
            aesgcm = AESGCM(srv_key)
            decrypted = aesgcm.decrypt(nonce, ct_and_tag, None)
            return decrypted.decode("utf-8")
        except Exception as exc:
            logger.warning(f"Failed server decryption for user {user_id}: {exc}")
            return "[Decryption Error]"

    # 3. Generic enc:v2: fallback (try client then server)
    raw_payload = ciphertext[len(PREFIX_GENERIC):]
    try:
        raw = base64.b64decode(raw_payload)
        nonce = raw[:NONCE_LENGTH]
        ct_and_tag = raw[NONCE_LENGTH:]
        # Try client key if provided
        normalized_client = normalize_client_key(client_key)
        if normalized_client:
            try:
                return AESGCM(normalized_client).decrypt(nonce, ct_and_tag, None).decode("utf-8")
            except Exception:
                pass
        # Try server key
        srv_key = derive_server_user_key(user_id)
        return AESGCM(srv_key).decrypt(nonce, ct_and_tag, None).decode("utf-8")
    except Exception:
        return "[🔒 Encrypted Message]"


def migrate_user_messages_to_client_key(user_id: str, client_key: str | bytes) -> int:
    """
    ONE-TIME HANDOVER:
    Finds any messages belonging to user_id that are not yet sealed with their
    client Zero-Knowledge key ('enc:v2:zk:'). Decrypts them and re-encrypts
    them with the client's key.
    """
    if not user_id or not client_key:
        return 0

    normalized_client = normalize_client_key(client_key)
    if not normalized_client:
        return 0

    from memory.models import PersonaChatMessage
    pending_msgs = PersonaChatMessage.objects.filter(user_identifier=user_id).exclude(text__startswith=PREFIX_ZK)
    if not pending_msgs.exists():
        return 0

    migrated_count = 0
    updated_records = []
    for msg in pending_msgs:
        plaintext = decrypt_chat_message(msg.text, user_id=user_id, client_key=normalized_client)
        if plaintext and not plaintext.startswith("["):
            new_ciphertext = encrypt_chat_message(plaintext, user_id=user_id, client_key=normalized_client)
            msg.text = new_ciphertext
            updated_records.append(msg)
            migrated_count += 1

    if updated_records:
        PersonaChatMessage.objects.bulk_update(updated_records, ["text"], batch_size=200)
        logger.info(f"Handover complete: Migrated {migrated_count} messages for user {user_id} to Client Zero-Knowledge encryption.")

    return migrated_count
