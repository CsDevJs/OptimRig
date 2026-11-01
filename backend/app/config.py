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
