"""Secret resolution helpers for env and system keyring references."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_environment() -> None:
    load_dotenv(ENV_FILE)


def resolve_secret_reference(raw_value: str | None, *, setting_name: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""

    if value.startswith("env:"):
        env_name = value.removeprefix("env:").strip()
        if not env_name:
            raise ValueError(f"{setting_name} uses an empty env: reference")
        return os.getenv(env_name, "").strip()

    if value.startswith("keyring:"):
        keyring_ref = value.removeprefix("keyring:").strip()
        service_name, separator, secret_name = keyring_ref.partition("/")
        if not separator or not service_name or not secret_name:
            raise ValueError(
                f"{setting_name} must use keyring:service/secret_name format"
            )

        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError(
                "keyring package is required for keyring: references"
            ) from exc

        secret_value = keyring.get_password(service_name, secret_name)
        return (secret_value or "").strip()

    return value


def read_secret(setting_name: str, default: str = "") -> str:
    return resolve_secret_reference(os.getenv(setting_name, default), setting_name=setting_name)
