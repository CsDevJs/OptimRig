from app.api.auth import get_current_user
from app.config import settings
from app.db.models import User
from app.main import app


def login_as(user_id: int):
    app.dependency_overrides[get_current_user] = lambda: User(id=user_id)


def test_admin_emails_needs_a_login(client):
    assert client.get("/admin/emails").status_code == 401


def test_only_admins_see_the_emails(client, vault, activity_log, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", " Boss@Example.com ")
    vault.add(1, "boss@example.com", "hash")
    vault.add(2, "ana@example.com", "hash")

    login_as(2)
    response = client.get("/admin/emails")
    assert response.status_code == 403 and "ana@example.com" not in response.text
    assert "ADMIN_DENIED | email=ana@example.com" in activity_log()[-1]

    login_as(1)
    response = client.get("/admin/emails")
    assert response.status_code == 200
    assert response.json() == {"emails": ["boss@example.com", "ana@example.com"]}
    assert "ADMIN_EMAILS_VIEWED | email=boss@example.com" in activity_log()[-1]


def test_nobody_is_admin_by_default(client, vault, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "")
    vault.add(1, "boss@example.com", "hash")
    login_as(1)
    assert client.get("/admin/emails").status_code == 403
