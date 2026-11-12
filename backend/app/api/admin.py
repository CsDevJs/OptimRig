"""Admin page data: the emails of every account, for the accounts in ADMIN_EMAILS only."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.auth import CurrentUser, Vault, email_of
from app.audit import log_action
from app.config import settings
from app.vault import VaultError

router = APIRouter(prefix="/admin", tags=["Admin"])


class AccountEmails(BaseModel):
    emails: list[str]


@router.get("/emails", response_model=AccountEmails, responses={
    401: {"description": "Not authenticated"}, 403: {"description": "Not an administrator"},
})
def account_emails(user: CurrentUser, vault: Vault) -> AccountEmails:
    """The email of every registered account, oldest first. Only for accounts whose
    email is in ADMIN_EMAILS; every attempt goes to the activity log."""
    email = email_of(user, vault)
    if email is None or email not in settings.admin_email_list:
        log_action("ADMIN_DENIED", email, user_id=user.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nu ai acces la această pagină.")
    try:
        users = vault.all()
    except VaultError:
        raise HTTPException(status_code=503, detail="Conturile nu pot fi citite momentan.") from None
    log_action("ADMIN_EMAILS_VIEWED", email, user_id=user.id, count=len(users))
    return AccountEmails(emails=[u.email for u in users])
