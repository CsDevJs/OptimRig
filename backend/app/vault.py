"""Users' personal data (email, password hash) in one encrypted file.

The whole file is encrypted with AES-256-GCM (authenticated encryption: a changed or
truncated file fails to decrypt instead of giving wrong data). The 32-byte key comes
from VAULT_KEY and is never stored next to the file, so a copy of the file alone, or
of the database, reveals nothing. Each save picks a new random 96-bit nonce and
replaces the file atomically (write a temporary file, flush it to disk, rename), so
a crash never leaves half a file. The database keeps only the user id, which saved
builds point to. The email can be decrypted; the password is stored only as
an Argon2id hash (app/security.py), which nobody can turn back into the password.

File layout (JSON): {"format": "pc-configurator-vault", "version": 1,
"nonce": base64, "ciphertext": base64}. The plaintext is JSON:
{"users": {"<id>": {"email": ..., "password_hash": ...}}}.
"""

import base64
import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT = "pc-configurator-vault"
VERSION = 1
# Bound to the ciphertext: a vault encrypted for another purpose or version won't decrypt.
_AAD = f"{FORMAT}/v{VERSION}".encode()


class VaultError(Exception):
    """The vault file can't be read: wrong key, or it was changed or damaged."""


class DuplicateEmail(Exception):
    pass


@dataclass(frozen=True)
class VaultUser:
    id: int
    email: str  # lowercased
    password_hash: str  # Argon2id, from security.hash_password


def decode_key(value: str) -> bytes:
    """VAULT_KEY: 32 random bytes, URL-safe base64 (44 characters)."""
    try:
        key = base64.urlsafe_b64decode(value.strip())
    except (ValueError, TypeError):
        key = b""
    if len(key) != 32:
        raise ValueError(
            "VAULT_KEY must be 32 random bytes in URL-safe base64. Generate one with: "
            'python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"'
        )
    return key


class UserVault:
    def __init__(self, path: Path, key: bytes):
        self.path = Path(path)
        self._aead = AESGCM(key)
        # One writer at a time: a read-check-write (e.g. "is this email free?") is atomic.
        self.lock = threading.RLock()

    # ---------- File ----------

    def _load(self) -> dict[int, VaultUser]:
        if not self.path.exists():
            return {}
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
            if envelope.get("format") != FORMAT or envelope.get("version") != VERSION:
                raise VaultError(f"{self.path} is not a version {VERSION} vault")
            plaintext = self._aead.decrypt(base64.b64decode(envelope["nonce"]),
                                           base64.b64decode(envelope["ciphertext"]), _AAD)
        except InvalidTag:
            raise VaultError(f"{self.path} can't be decrypted: wrong VAULT_KEY, or the file was changed") from None
        except (ValueError, KeyError, TypeError) as error:
            raise VaultError(f"{self.path} is damaged: {error}") from None
        users = json.loads(plaintext)["users"]
        # Entries written before usernames were dropped still carry one; it is ignored.
        return {int(uid): VaultUser(id=int(uid), email=data["email"], password_hash=data["password_hash"])
                for uid, data in users.items()}

    def _save(self, users: dict[int, VaultUser]) -> None:
        plaintext = json.dumps({"users": {str(u.id): {k: v for k, v in asdict(u).items() if k != "id"}
                                          for u in users.values()}}, ensure_ascii=False).encode()
        nonce = os.urandom(12)
        envelope = {"format": FORMAT, "version": VERSION, "nonce": base64.b64encode(nonce).decode(),
                    "ciphertext": base64.b64encode(self._aead.encrypt(nonce, plaintext, _AAD)).decode()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".vault-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(envelope, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise

    # ---------- Users ----------

    def all(self) -> list[VaultUser]:
        with self.lock:
            return sorted(self._load().values(), key=lambda u: u.id)

    def get(self, user_id: int) -> VaultUser | None:
        with self.lock:
            return self._load().get(user_id)

    def find(self, login: str) -> VaultUser | None:
        """The user whose email is `login` (case-insensitive)."""
        wanted = login.strip().lower()
        with self.lock:
            return next((u for u in self._load().values() if u.email == wanted), None)

    def check_free(self, email: str) -> None:
        if any(u.email == email.lower() for u in self._load().values()):
            raise DuplicateEmail

    def add(self, user_id: int, email: str, password_hash: str) -> VaultUser:
        with self.lock:
            self.check_free(email)
            users = self._load()
            user = VaultUser(id=user_id, email=email.lower(), password_hash=password_hash)
            users[user_id] = user
            self._save(users)
            return user

    def remove(self, user_id: int) -> None:
        with self.lock:
            users = self._load()
            if users.pop(user_id, None) is not None:
                self._save(users)


_vault: UserVault | None = None


def get_vault() -> UserVault:
    """FastAPI dependency; tests override it with a vault in a temporary folder."""
    global _vault
    if _vault is None:
        from app.config import settings
        _vault = UserVault(settings.vault_path, decode_key(settings.vault_key))
    return _vault
