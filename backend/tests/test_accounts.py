from datetime import UTC, datetime, timedelta
from decimal import Decimal

import jwt
import pytest
from sqlalchemy import select

from app.api.auth import get_current_user
from app.config import settings
from app.main import app
from app.db.models import Availability, BuildItem, Category, Component, Offer, User
from app.security import create_access_token, hash_password, read_access_token, verify_password

PASSWORD = "correct horse battery"


# ---------- Without a database ----------

def test_password_hash_round_trip():
    hashed = hash_password(PASSWORD)
    assert hashed != PASSWORD
    assert verify_password(hashed, PASSWORD)
    assert not verify_password(hashed, "wrong password")
    assert not verify_password(None, PASSWORD)
    assert not verify_password("not-an-argon2-hash", PASSWORD)


def test_token_round_trip_and_rejections():
    assert read_access_token(create_access_token(42)) == 42
    assert read_access_token("garbage") is None
    expired = jwt.encode({"sub": "42", "exp": datetime.now(UTC) - timedelta(seconds=1)},
                         settings.jwt_secret, algorithm="HS256")
    assert read_access_token(expired) is None
    forged = jwt.encode({"sub": "42", "exp": datetime.now(UTC) + timedelta(hours=1)},
                        "some-other-secret-at-least-32-bytes", algorithm="HS256")
    assert read_access_token(forged) is None


@pytest.mark.parametrize("body", [
    {"email": "not-an-email", "password": PASSWORD},
    {"email": "a@example.com", "password": "short"},
    {"email": "a@example.com", "password": "x" * 129},
    {"email": "a@example.com"},
    {"email": "a@example.com", "password": PASSWORD, "admin": True},
])
def test_invalid_credentials_payload(client, body):
    assert client.post("/auth/register", json=body).status_code == 422


@pytest.mark.parametrize("path", ["/auth/me", "/builds", "/builds/1"])
def test_protected_endpoints_require_token(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_build_payloads(client):
    # A stand-in user, so body validation is tested without a database.
    app.dependency_overrides[get_current_user] = lambda: User(id=1, email="a@example.com")
    for body in [
        {"name": "  ", "components": {"cpu": 1}},
        {"name": "x" * 101, "components": {"cpu": 1}},
        {"name": "PC", "components": {}},
        {"name": "PC", "components": {"cpu": 1, "gpu": 1}},
        {"name": "PC", "components": {"cpu": "1"}},
        {"name": "PC", "components": {"cpu": 1}, "owner": 2},
    ]:
        assert client.post("/builds", json=body).status_code == 422


# ---------- Against the seeded database ----------

def register_and_login(client, email="user@example.com"):
    assert client.post("/auth/register", json={"email": email, "password": PASSWORD}).status_code == 201
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def ids(db, *slugs):
    return [db.scalar(select(Component.id).where(Component.slug == s)) for s in slugs]


def am5_build(db):
    cpu, board, ram, gpu, ssd, psu, case, cooler = ids(
        db, "amd-ryzen-5-7600", "gigabyte-b650m-d3hp", "kingston-kf560c36bbe2ak2-32",
        "gigabyte-rx-9060-xt-gaming-oc-16g", "samsung-990-evo-plus-1tb", "cougar-gex-pro-750",
        "deepcool-cc560-v2-black", "deepcool-ak620-digital",
    )
    return {"cpu": cpu, "motherboard": board, "ram": ram, "gpu": gpu, "storage": ssd,
            "psu": psu, "case": case, "cooler": cooler}


def test_register_login_me(catalog_client):
    client, db = catalog_client
    created = client.post("/auth/register", json={"email": "Mixed@Example.com", "password": PASSWORD})
    assert created.status_code == 201
    assert created.json()["email"] == "mixed@example.com"
    assert "password" not in str(created.json())
    stored = db.scalar(select(User).where(User.email == "mixed@example.com"))
    assert stored.password_hash.startswith("$argon2") and PASSWORD not in stored.password_hash

    duplicate = client.post("/auth/register", json={"email": "mixed@EXAMPLE.com", "password": PASSWORD})
    assert duplicate.status_code == 409

    login = client.post("/auth/login", json={"email": "MIXED@example.com", "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()
    assert token["token_type"] == "bearer" and token["expires_in"] == settings.access_token_minutes * 60
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.json()["email"] == "mixed@example.com"


def test_login_failures_are_indistinguishable(catalog_client):
    client, _ = catalog_client
    register_and_login(client)
    wrong_password = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong password"})
    unknown_email = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_token_for_deleted_user_is_rejected(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    db.delete(db.scalar(select(User).where(User.email == "user@example.com")))
    db.flush()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_build_lifecycle(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    selection = am5_build(db)

    created = client.post("/builds", json={"name": "  Mid AM5  ", "components": selection}, headers=headers)
    assert created.status_code == 201
    build = created.json()
    assert build["name"] == "Mid AM5"
    assert build["component_count"] == 8
    assert build["compatibility"]["status"] == "compatible"
    assert build["unpriced_categories"] == []
    for item in build["items"]:
        assert item["saved_price_mdl"] == item["current_price_mdl"]
        assert item["saved_store"] == item["current_store"]
    assert Decimal(build["saved_total_mdl"]) == Decimal(build["current_total_mdl"]) == sum(
        Decimal(i["saved_price_mdl"]) for i in build["items"])

    listed = client.get("/builds", headers=headers).json()
    assert [b["id"] for b in listed] == [build["id"]]
    assert client.get(f"/builds/{build['id']}", headers=headers).json() == build

    deleted = client.delete(f"/builds/{build['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/builds/{build['id']}", headers=headers).status_code == 404
    assert client.get("/builds", headers=headers).json() == []


def test_saved_price_survives_price_change(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    selection = am5_build(db)
    build = client.post("/builds", json={"name": "PC", "components": selection}, headers=headers).json()
    cpu_item = next(i for i in build["items"] if i["category"] == "cpu")

    for offer in db.scalars(select(Offer).where(Offer.component_id == selection["cpu"])):
        offer.price_mdl += 100
    db.flush()

    after = client.get(f"/builds/{build['id']}", headers=headers).json()
    cpu_after = next(i for i in after["items"] if i["category"] == "cpu")
    assert cpu_after["saved_price_mdl"] == cpu_item["saved_price_mdl"]
    assert Decimal(cpu_after["current_price_mdl"]) == Decimal(cpu_item["saved_price_mdl"]) + 100


def test_replace_keeps_saved_prices_of_unchanged_parts(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    selection = am5_build(db)
    build = client.post("/builds", json={"name": "PC", "components": selection}, headers=headers).json()
    psu_saved = next(i for i in build["items"] if i["category"] == "psu")["saved_price_mdl"]

    for offer in db.scalars(select(Offer).where(Offer.component_id == selection["psu"])):
        offer.price_mdl += 50
    db.flush()

    # Swap the GPU, drop the cooler, keep everything else.
    new_gpu, = ids(db, "gigabyte-rx-9060-xt-gaming-oc-8g")
    changed = {**selection, "gpu": new_gpu}
    del changed["cooler"]
    replaced = client.put(f"/builds/{build['id']}", json={"name": "PC v2", "components": changed}, headers=headers)
    assert replaced.status_code == 200
    body = replaced.json()
    assert body["name"] == "PC v2"
    assert {i["category"] for i in body["items"]} == set(changed)
    assert next(i for i in body["items"] if i["category"] == "psu")["saved_price_mdl"] == psu_saved
    assert next(i for i in body["items"] if i["category"] == "gpu")["component"]["id"] == new_gpu
    # Ryzen 5 7600 ships without a cooler, so removing it makes the build incomplete.
    assert body["compatibility"]["status"] == "incomplete"
    assert "cooler" in body["compatibility"]["missing_categories"]
    assert body["updated_at"] >= build["updated_at"]


def test_incompatible_build_can_be_saved(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    cpu, board = ids(db, "intel-core-i5-14400f", "gigabyte-b650m-d3hp")
    body = client.post("/builds", json={"name": "Draft", "components": {"cpu": cpu, "motherboard": board}},
                       headers=headers).json()
    assert body["compatibility"]["status"] == "incompatible"


def test_out_of_stock_parts_have_no_price(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    cpu, = ids(db, "intel-core-i3-12100f")
    for offer in db.scalars(select(Offer).where(Offer.component_id == cpu)):
        offer.availability = Availability.OUT_OF_STOCK
    db.flush()
    body = client.post("/builds", json={"name": "PC", "components": {"cpu": cpu}}, headers=headers).json()
    assert body["items"][0]["saved_price_mdl"] is None
    assert body["items"][0]["current_price_mdl"] is None
    assert body["unpriced_categories"] == ["cpu"]
    assert body["saved_total_mdl"] == body["current_total_mdl"] == "0"


def test_unknown_and_mismatched_components(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    cpu, board = ids(db, "amd-ryzen-5-7600", "gigabyte-b650m-d3hp")
    missing = client.post("/builds", json={"name": "PC", "components": {"cpu": 999999}}, headers=headers)
    assert missing.status_code == 404
    swapped = client.post("/builds", json={"name": "PC", "components": {"cpu": board, "motherboard": cpu}},
                          headers=headers)
    assert swapped.status_code == 422
    assert db.scalar(select(BuildItem.build_id).limit(1)) is None


def test_users_cannot_see_or_change_each_others_builds(catalog_client):
    client, db = catalog_client
    alice = register_and_login(client, "alice@example.com")
    bob = register_and_login(client, "bob@example.com")
    cpu, = ids(db, "amd-ryzen-5-7600")
    build_id = client.post("/builds", json={"name": "Alice's", "components": {"cpu": cpu}},
                           headers=alice).json()["id"]

    assert client.get("/builds", headers=bob).json() == []
    assert client.get(f"/builds/{build_id}", headers=bob).status_code == 404
    assert client.put(f"/builds/{build_id}", json={"name": "Mine now", "components": {"cpu": cpu}},
                      headers=bob).status_code == 404
    assert client.delete(f"/builds/{build_id}", headers=bob).status_code == 404
    assert client.get(f"/builds/{build_id}", headers=alice).json()["name"] == "Alice's"


def test_category_order_is_stable(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    body = client.post("/builds", json={"name": "PC", "components": am5_build(db)}, headers=headers).json()
    order = [i["category"] for i in body["items"]]
    assert order == [c.value for c in Category if c.value in order]


def test_build_with_a_second_drive(catalog_client):
    client, db = catalog_client
    headers = register_and_login(client)
    selection = am5_build(db)
    hdd, = ids(db, "samsung-990-pro-2tb")
    selection["storage2"] = hdd
    body = client.post("/builds", json={"name": "Two drives", "components": selection}, headers=headers).json()
    slots = [i["category"] for i in body["items"]]
    assert slots.index("storage") + 1 == slots.index("storage2")
    assert body["compatibility"]["status"] in ("compatible", "undetermined")
    assert "storage_m2_count" in body["compatibility"]["checked_rules"]
    # The same drive twice is a valid pair of identical drives.
    selection["storage2"] = selection["storage"]
    same = client.put(f"/builds/{body['id']}", json={"name": "Twins", "components": selection}, headers=headers)
    assert same.status_code == 200 and len(same.json()["items"]) == len(selection)
    plan = client.post("/purchase/plan", json={"components": selection}).json()
    assert sorted(i["category"] for i in plan["items"] + plan["unplanned"]).count("storage2") == 1


@pytest.mark.parametrize("secret", ["CHANGE_ME", "change_me", "short-secret", "x" * 31])
def test_weak_or_placeholder_jwt_secret_is_rejected(secret):
    from pydantic import ValidationError
    from app.config import Settings
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(database_url="postgresql+psycopg://u@h/db", jwt_secret=secret)


def test_strong_jwt_secret_is_accepted():
    from app.config import Settings
    assert Settings(database_url="postgresql+psycopg://u@h/db", jwt_secret="k" * 32).jwt_secret == "k" * 32
