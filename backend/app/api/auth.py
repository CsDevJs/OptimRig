from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.account_schemas import LoginRequest, Registration, TokenRead, UserRead
from app.audit import log_action
from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.security import create_access_token, hash_password, read_access_token, verify_password
from app.vault import DuplicateEmail, UserVault, get_vault

router = APIRouter(prefix="/auth", tags=["Accounts"])
DbSession = Annotated[Session, Depends(get_db)]
Vault = Annotated[UserVault, Depends(get_vault)]
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    """Resolve the bearer token to a user; any problem is the same generic 401."""
    if credentials is None:
        raise _UNAUTHORIZED
    user_id = read_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def email_of(user: User, vault: UserVault) -> str | None:
    """The account's email, for the activity log."""
    data = vault.get(user.id)
    return data.email if data else None


def _read(user: User, vault: UserVault) -> UserRead:
    data = vault.get(user.id)
    if data is None:  # an account row whose vault entry is gone: treat as no account
        raise _UNAUTHORIZED
    return UserRead(id=user.id, email=data.email, created_at=user.created_at)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED,
             responses={409: {"description": "Email already registered"}})
def register(payload: Registration, db: DbSession, vault: Vault) -> UserRead:
    """Create an account. The email and the password's Argon2id hash go to the
    encrypted vault; the database row only gives the account its id."""
    with vault.lock:  # the free-check and the write happen as one step
        try:
            vault.check_free(payload.email)
        except DuplicateEmail:
            log_action("REGISTER_FAILED", payload.email.lower(), reason="email already registered")
            raise HTTPException(status_code=409, detail="Email already registered") from None
        user = User()
        db.add(user)
        db.flush()
        vault.add(user.id, payload.email, hash_password(payload.password))
        try:
            db.commit()
        except Exception:
            vault.remove(user.id)
            log_action("REGISTER_FAILED", payload.email.lower(), reason="database error")
            raise
    log_action("REGISTERED", payload.email.lower(), user_id=user.id)
    db.refresh(user)
    return _read(user, vault)


@router.post("/login", response_model=TokenRead, responses={401: {"description": "Wrong login or password"}})
def login(payload: LoginRequest, db: DbSession, vault: Vault) -> TokenRead:
    """Log in with email and password."""
    data = vault.find(payload.login)
    user = db.get(User, data.id) if data else None
    # Same answer for an unknown login and a wrong password, so accounts can't be probed.
    if not verify_password(data.password_hash if data and user else None, payload.password):
        # The client gets one generic answer; the log says which case it was.
        log_action("LOGIN_FAILED", data.email if data else payload.login.lower(),
                   reason="wrong password" if data and user else "no account with this email")
        raise HTTPException(status_code=401, detail="Wrong login or password")
    log_action("LOGIN_OK", data.email, user_id=user.id)
    return TokenRead(access_token=create_access_token(user.id), expires_in=settings.access_token_minutes * 60)


@router.get("/me", response_model=UserRead, responses={401: {"description": "Not authenticated"}})
def me(user: CurrentUser, vault: Vault) -> UserRead:
    return _read(user, vault)
