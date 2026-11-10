from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
_PLACEHOLDER_SECRETS = {"CHANGE_ME", "change_me", "changeme", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str
    # Signs login tokens. Use a long random value; changing it logs everyone out.
    jwt_secret: str
    access_token_minutes: int = 60 * 24
    # Encrypts the users' vault (email, password hash). Keep it out of git and away
    # from the vault file: with both, anyone can read every account; losing it loses them.
    vault_key: str
    vault_path: Path = BACKEND_DIR / "data" / "users.vault"
    # Activity log (app/audit.py): logins, failed logins, saved builds, each with the email.
    # Any folder works, e.g. AUDIT_LOG_DIR=D:/pc-configurator-logs
    audit_log_dir: Path = BACKEND_DIR / "logs"
    audit_log_max_bytes: int = 5 * 1024 * 1024  # rotate at 5 MB
    audit_log_backup_count: int = 10  # keep activity.log.1 ... activity.log.10
    # Sites on another domain allowed to call the API from the browser, comma-separated,
    # e.g. CORS_ORIGINS=https://csdevjs.github.io (scheme + host, no path). Empty: none.
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @field_validator("vault_key")
    @classmethod
    def valid_vault_key(cls, value: str) -> str:
        from app.vault import decode_key
        decode_key(value)
        return value

    @field_validator("jwt_secret")
    @classmethod
    def strong_secret(cls, value: str) -> str:
        # Anyone who knows the secret can sign a token for any user, so refuse
        # the public placeholder from .env.example and short, guessable values.
        if value.strip() in _PLACEHOLDER_SECRETS or len(value) < 32:
            raise ValueError(
                "JWT_SECRET must be a random value of at least 32 characters. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value


settings = Settings()
