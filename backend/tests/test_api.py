from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.db.models import Category, Component, SPEC_MODELS, Store
from app.db.session import get_db
from app.main import app


def test_liveness_does_not_connect_to_database(client):
    def forbidden_db():
        raise AssertionError("Liveness must not use the database")

    app.dependency_overrides[get_db] = forbidden_db
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_routes_also_answer_under_the_api_prefix(client):
    # On Vercel the backend service may receive the site's /api/... path unchanged.
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/components?limit=0").status_code == 422
    assert client.get("/apifoo/health").status_code == 404
    docs = client.get("/api/docs").text
    assert "/api/openapi.json" in docs
    assert client.get("/api/openapi.json").status_code == 200


@pytest.mark.parametrize("query", [
    "category=unknown", "tier=unknown", "limit=0", "limit=1001", "offset=-1",
    "brand=", "brand=%20%20", "limit=abc",
])
def test_invalid_filters(client, query):
    response = client.get(f"/components?{query}")
    assert response.status_code == 422


@pytest.mark.parametrize("component_id", ["0", "-1", "abc"])
def test_invalid_component_id(client, component_id):
    assert client.get(f"/components/{component_id}").status_code == 422


def test_database_health_hides_connection_details(client):
    class UnavailableSession:
        def execute(self, statement):
            raise OperationalError("secret connection details", {}, Exception("password"))

    app.dependency_overrides[get_db] = lambda: UnavailableSession()
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_openapi_documents_all_spec_shapes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]) == {
        "/health", "/health/db", "/components", "/components/{component_id}", "/stores",
        "/compatibility/check", "/compatibility/filter",
        "/auth/register", "/auth/login", "/auth/me", "/builds", "/builds/{build_id}", "/purchase/plan",
        "/recommendations",
    }
    assert "CpuSpecRead" in schema["components"]["schemas"]
    assert "CoolerSpecRead" in schema["components"]["schemas"]


def test_catalog_filters_and_pagination(catalog_client):
    client, db = catalog_client
    response = client.get("/components?category=cpu&tier=low&brand=%20amd%20&limit=1")
    assert response.status_code == 200
    page = response.json()
    assert page["limit"] == 1 and page["offset"] == 0
    assert page["total"] >= 1
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert (item["category"], item["tier"], item["brand"]) == ("cpu", "low", "AMD")

    expected_total = db.scalar(select(func.count()).select_from(Component))
    first = client.get("/components?limit=1").json()
    second = client.get("/components?limit=1&offset=1").json()
    assert first["total"] == second["total"] == expected_total
    assert first["items"][0]["id"] < second["items"][0]["id"]
    beyond = client.get(f"/components?offset={expected_total}").json()
    assert beyond["items"] == [] and beyond["total"] == expected_total


def test_empty_filters(catalog_client):
    client, _ = catalog_client
    response = client.get("/components?brand=nonexistent-brand")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


@pytest.mark.parametrize("category", list(Category))
def test_detail_specs_and_offers_for_every_category(catalog_client, category):
    client, db = catalog_client
    component = db.scalar(select(Component).where(Component.category == category).order_by(Component.id))
    assert component is not None, "Integration database must contain the catalog seed"
    response = client.get(f"/components/{component.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == category.value
    spec = db.get(SPEC_MODELS[category], component.id)
    assert spec is not None
    expected_keys = set(SPEC_MODELS[category].__table__.columns.keys()) - {"component_id"}
    assert set(body["specs"]) == expected_keys
    prices = [Decimal(offer["price_mdl"]) for offer in body["offers"]]
    assert prices == sorted(prices)
    for offer in body["offers"]:
        assert isinstance(offer["price_mdl"], str)
        assert offer["store"]["slug"]
        assert offer["checked_on"]
        assert offer["availability"] in {"in_stock", "on_order", "out_of_stock"}
        assert offer["stock_qty"] is None or offer["stock_qty"] >= 0


def test_unknown_component(catalog_client):
    client, db = catalog_client
    missing_id = db.scalar(select(func.max(Component.id))) + 1
    response = client.get(f"/components/{missing_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Component not found"}


def test_component_without_spec_or_offers(catalog_client):
    client, db = catalog_client
    component = Component(
        slug="test-incomplete-cpu", category=Category.CPU, tier="low",
        brand="Test", model="Incomplete CPU", power_draw_w=0,
    )
    db.add(component)
    db.flush()
    response = client.get(f"/components/{component.id}")
    assert response.status_code == 200
    assert response.json()["specs"] is None
    assert response.json()["offers"] == []


def test_stores_and_database_health(catalog_client):
    client, db = catalog_client
    response = client.get("/stores")
    assert response.status_code == 200
    stores = response.json()
    assert len(stores) == db.scalar(select(func.count()).select_from(Store))
    assert [store["name"] for store in stores] == sorted(store["name"] for store in stores)
    assert {store["slug"] for store in stores} >= {"darwin", "xstore", "neocomputer"}
    assert client.get("/health/db").json() == {"status": "ok"}
