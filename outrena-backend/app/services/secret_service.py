"""
secret_service.py — Pluggable secret-backend abstraction + Fernet at-rest crypto.

Three production backends (selectable via ``SECRET_BACKEND`` env var):

  env    — read from os.environ (DEFAULT — dev/CI; prod should override).
  aws    — AWS Secrets Manager via boto3 (optional dependency).
  azure  — Azure Key Vault via azure-identity + azure-keyvault-secrets
           (optional dependency).

The ``encrypt_at_rest`` / ``decrypt_at_rest`` helpers use Fernet
(symmetric authenticated encryption). The key is read from
``ENCRYPTION_KEY`` (a URL-safe base64-encoded 32-byte key — generate with
``cryptography.fernet.Fernet.generate_key()``). When no key is configured
the helpers raise RuntimeError so production cannot silently fall back
to plaintext.

Used by app code to fetch LLM API keys etc. instead of plaintext DB
columns, and by config_models going forward to encrypt LlmConfig.apiKey
at rest.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


@runtime_checkable
class SecretBackend(Protocol):
    """The surface every secret backend must implement."""

    def get_secret(self, name: str) -> str | None:
        ...

    def put_secret(self, name: str, value: str) -> None:
        ...

    def rotate_secret(self, name: str) -> str:
        ...


# ── EnvSecretBackend (default) ───────────────────────────────────────────────


class EnvSecretBackend:
    """Reads secrets from os.environ. ``put_secret`` is a no-op (logs)."""

    def get_secret(self, name: str) -> str | None:
        return os.environ.get(name)

    def put_secret(self, name: str, value: str) -> None:
        # Env backend is read-only — never writes back. Log so the caller
        # knows the write was silently dropped (production should use aws/azure).
        logger.warning("secret.env.put_not_persistent", name=name)

    def rotate_secret(self, name: str) -> str:
        import secrets as _secrets
        new = _secrets.token_urlsafe(32)
        logger.warning("secret.env.rotate_not_persistent", name=name)
        return new


# ── AwsSecretsManagerBackend (optional — boto3) ─────────────────────────────


class AwsSecretsManagerBackend:
    """AWS Secrets Manager backend. Requires boto3 (optional dependency)."""

    def __init__(self, region_name: str) -> None:
        self._region = region_name
        self._client = None  # lazy

    def _get_client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            import boto3  # type: ignore[import-not-found] — optional dep
            self._client = boto3.client("secretsmanager", region_name=self._region)
        return self._client

    def get_secret(self, name: str) -> str | None:
        import json
        client = self._get_client()
        try:
            resp = client.get_secret_value(SecretId=name)
        except Exception as exc:  # noqa: BLE001
            logger.error("secret.aws.get_failed", name=name, error=str(exc))
            return None
        if "SecretString" in resp and resp["SecretString"]:
            try:
                return json.loads(resp["SecretString"]).get("value", resp["SecretString"])
            except json.JSONDecodeError:
                return resp["SecretString"]
        return None

    def put_secret(self, name: str, value: str) -> None:
        import json
        client = self._get_client()
        try:
            client.put_secret_value(SecretId=name, SecretString=json.dumps({"value": value}))
        except Exception as exc:  # noqa: BLE001
            logger.error("secret.aws.put_failed", name=name, error=str(exc))
            raise

    def rotate_secret(self, name: str) -> str:
        import secrets as _secrets
        new = _secrets.token_urlsafe(32)
        self.put_secret(name, new)
        return new


# ── AzureKeyVaultBackend (optional — azure-identity + azure-keyvault) ────────


class AzureKeyVaultBackend:
    """Azure Key Vault backend. Requires azure-identity + azure-keyvault-secrets."""

    def __init__(self, vault_url: str) -> None:
        self._vault_url = vault_url
        self._client = None  # lazy

    def _get_client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.secrets import SecretClient  # type: ignore
            self._client = SecretClient(
                vault_url=self._vault_url,
                credential=DefaultAzureCredential(),
            )
        return self._client

    def get_secret(self, name: str) -> str | None:
        try:
            secret = self._get_client().get_secret(name)
            return secret.value if secret is not None else None
        except Exception as exc:  # noqa: BLE001
            logger.error("secret.azure.get_failed", name=name, error=str(exc))
            return None

    def put_secret(self, name: str, value: str) -> None:
        try:
            self._get_client().set_secret(name, value)
        except Exception as exc:  # noqa: BLE001
            logger.error("secret.azure.put_failed", name=name, error=str(exc))
            raise

    def rotate_secret(self, name: str) -> str:
        import secrets as _secrets
        new = _secrets.token_urlsafe(32)
        self.put_secret(name, new)
        return new


# ── Selector ─────────────────────────────────────────────────────────────────


@lru_cache
def get_secret_backend() -> SecretBackend:
    """Return the configured SecretBackend (cached singleton)."""
    settings = get_settings()
    backend = (settings.SECRET_BACKEND or "env").lower()
    if backend == "aws":
        return AwsSecretsManagerBackend(region_name=settings.AWS_REGION)
    if backend == "azure":
        return AzureKeyVaultBackend(vault_url=settings.AZURE_KEYVAULT_URL)
    return EnvSecretBackend()


# ── Fernet at-rest encryption helpers ────────────────────────────────────────


def _get_fernet():  # type: ignore[no-untyped-def]
    from cryptography.fernet import Fernet  # type: ignore[import-not-found]
    key = get_settings().ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set — refusing to encrypt/decrypt at rest. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_at_rest(plaintext: str) -> str:
    """Encrypt ``plaintext`` with Fernet. Returns a URL-safe base64 ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_at_rest(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext produced by ``encrypt_at_rest``."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


__all__ = [
    "SecretBackend",
    "EnvSecretBackend",
    "AwsSecretsManagerBackend",
    "AzureKeyVaultBackend",
    "get_secret_backend",
    "encrypt_at_rest",
    "decrypt_at_rest",
]
