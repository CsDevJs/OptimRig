from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.db.models import Availability, Offer, Store
from app.services.store_pages import PageParseError, parse_product_page
from scripts import check_offers

FIXTURES = Path(__file__).parent / "fixtures" / "store_pages"
D = Decimal


def page(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


# ---------- Parsers, on trimmed copies of real store pages ----------

@pytest.mark.parametrize("fixture, price, regular, availability", [
    ("xstore_sale", "3799", "3979", Availability.IN_STOCK),
    ("xstore_oos", "7690", None, Availability.OUT_OF_STOCK),
    ("neocomputer_sale", "4175", "4524", Availability.IN_STOCK),
    ("darwin_regular", "3979", None, Availability.IN_STOCK),
    ("darwin_sale", "4499", "6999", Availability.IN_STOCK),
    ("darwin_oos", "1339", None, Availability.OUT_OF_STOCK),
    ("ultra_regular", "3979", None, Availability.IN_STOCK),
    ("ultra_oos", "1989", None, Availability.OUT_OF_STOCK),
    ("primepc_regular", "20692", None, Availability.IN_STOCK),
    ("primepc_sale", "2890", "3199", Availability.IN_STOCK),
    ("primepc_oos", "14464", None, Availability.OUT_OF_STOCK),
])
def test_real_store_pages(fixture, price, regular, availability):
    data = parse_product_page(fixture.split("_")[0], page(fixture))
    assert data.price == D(price)
    assert data.regular_price == (D(regular) if regular else None)
    assert data.availability == availability


def test_ultra_sale_price_block():
    # No Ultra component was on sale on 2026-10-23, so this block is built from
    # Ultra's real class names (product-purchase-card__old-price is crossed out in their CSS).
    html = page("ultra_regular").replace(
        '<div class="product-purchase-card__price-section">',
        '<div class="product-purchase-card__price-section">'
        '<p class="product-purchase-card__old-price">4 299 lei</p>', 1)
    assert parse_product_page("ultra", html).regular_price == D("4299")


def test_crossed_out_price_not_above_current_is_not_a_sale():
    html = page("darwin_sale").replace("6 999", "4 499", 1)
    assert parse_product_page("darwin", html).regular_price is None


@pytest.mark.parametrize("html, message", [
    ("<html><body>No data here</body></html>", "No schema.org Product"),
    ('<script type="application/ld+json">{"@type":"Product","offers":{"availability":"https://schema.org/InStock"}}</script>', "no price"),
    ('<script type="application/ld+json">{"@type":"Product","offers":{"price":"10","availability":"https://schema.org/Maybe"}}</script>', "Unknown availability"),
])
def test_unexpected_pages_raise(html, message):
    with pytest.raises(PageParseError, match=message):
        parse_product_page("darwin", html)


def test_primepc_reads_only_the_main_price_block():
    # The quick-order dialog repeats the prices outside .product_desc. A different copy of it,
    # moved before the main block, must not be read.
    main, quick = page("primepc_sale").split("<!-- Quick-order modal")
    quick = quick.replace("3199", "9999").replace('data-price="2890"', 'data-price="1"')
    data = parse_product_page("primepc", quick + main)
    assert (data.price, data.regular_price) == (D("2890"), D("3199"))


@pytest.mark.parametrize("html, message", [
    ("<html><body>No data here</body></html>", "No PrimePC price block"),
    ('<div class="product_desc"><div class="productPrice"><b data-price=""></b></div></div>', "No number"),
    ('<div class="product_desc"><div class="productPrice"><b data-price="0"></b></div></div>', "not positive"),
])
def test_unexpected_primepc_pages_raise(html, message):
    with pytest.raises(PageParseError, match=message):
        parse_product_page("primepc", html)


def test_unknown_store():
    with pytest.raises(PageParseError):
        parse_product_page("emag", page("darwin_regular"))


# ---------- The checker's update logic, with faked HTTP responses ----------

def make_offer(**overrides):
    values = dict(price_mdl=D("4000.00"), regular_price_mdl=None, availability=Availability.IN_STOCK,
                  url="https://xstore.md/p", checked_on=date(2026, 10, 21), store=Store(slug="xstore", name="Xstore"))
    values.update(overrides)
    return Offer(**values)


def client_returning(status: int, body: str = "") -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, text=body)))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(check_offers.time, "sleep", lambda seconds: None)


def test_check_updates_price_sale_and_date():
    offer = make_offer()
    status, changes = check_offers.check_offer(client_returning(200, page("xstore_sale")), offer)
    assert status == "ok"
    assert changes == ["price 4000.00 -> 3799.00", "on sale (regular 3979.00)"]
    assert (offer.price_mdl, offer.regular_price_mdl) == (D("3799.00"), D("3979"))
    assert offer.checked_on == date.today()


def test_check_reports_stock_change_and_sale_end():
    offer = make_offer(price_mdl=D("7690.00"), regular_price_mdl=D("8000.00"))
    status, changes = check_offers.check_offer(client_returning(200, page("xstore_oos")), offer)
    assert status == "ok"
    assert changes == ["sale ended", "in_stock -> out_of_stock"]


def test_unchanged_page_reports_nothing():
    offer = make_offer(price_mdl=D("3979"), url="https://darwin.md/p", store=Store(slug="darwin", name="Darwin"))
    assert check_offers.check_offer(client_returning(200, page("darwin_regular")), offer) == ("ok", [])


@pytest.mark.parametrize("http_status, body, expected", [
    (404, "", "page_gone"),
    (410, "", "page_gone"),
    (503, "", "failed"),
    (403, "", "failed"),
    (200, "<html>redesigned page</html>", "failed"),
])
def test_failures_keep_previous_values(http_status, body, expected):
    offer = make_offer()
    status, details = check_offers.check_offer(client_returning(http_status, body), offer)
    assert status == expected and details
    assert (offer.price_mdl, offer.availability, offer.checked_on) == (
        D("4000.00"), Availability.IN_STOCK, date(2026, 10, 21))


def test_network_error_is_a_failure():
    def broken(request):
        raise httpx.ConnectError("no route")
    offer = make_offer()
    status, details = check_offers.check_offer(httpx.Client(transport=httpx.MockTransport(broken)), offer)
    assert status == "failed" and "ConnectError" in details[0]


# ---------- API shows sales ----------

def test_component_offers_show_sales(catalog_client):
    client, db = catalog_client
    offer = db.scalar(select(Offer).order_by(Offer.id))
    offer.regular_price_mdl = offer.price_mdl + 200
    offer.last_check_status = "ok"
    db.flush()
    body = client.get(f"/components/{offer.component_id}").json()
    shown = next(o for o in body["offers"] if o["id"] == offer.id)
    assert shown["on_sale"] is True
    assert D(shown["regular_price_mdl"]) == offer.price_mdl + 200
    assert shown["last_check_status"] == "ok"
    others = [o for o in body["offers"] if o["id"] != offer.id]
    assert all(o["on_sale"] is False and o["regular_price_mdl"] is None for o in others)


# ---------- Review fixes ----------

def redirecting_client(final_url: str, body: str) -> httpx.Client:
    def handler(request):
        if str(request.url) != final_url:
            return httpx.Response(301, headers={"Location": final_url})
        return httpx.Response(200, text=body)
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_redirect_to_another_product_is_not_saved():
    # Xstore sends a discontinued Ryzen page to a motherboard: its price must not become ours.
    offer = make_offer(url="https://xstore.md/componente-pc/procesoare/procesor-amd-ryzen-5-7600-tray")
    client = redirecting_client("https://xstore.md/componente-pc/placi-de-baza/gigabyte-z790-aorus-elite-x-wifi7",
                                page("xstore_oos"))
    status, details = check_offers.check_offer(client, offer)
    assert status == "failed" and "redirected to" in details[0] and "z790" in details[0]
    assert (offer.price_mdl, offer.availability) == (D("4000.00"), Availability.IN_STOCK)


@pytest.mark.parametrize("final_url", [
    "https://xstore.md/p/",              # trailing slash added
    "https://www.xstore.md/p",           # www added
    "https://xstore.md/p?utm=x",         # query string added
])
def test_redirect_to_the_same_page_is_fine(final_url):
    offer = make_offer(url="http://xstore.md/p")
    status, _ = check_offers.check_offer(redirecting_client(final_url, page("xstore_sale")), offer)
    assert status == "ok" and offer.price_mdl == D("3799.00")


def test_json_ld_that_is_not_an_object_is_skipped():
    html = '<script type="application/ld+json">5</script>' + page("darwin_regular")
    assert parse_product_page("darwin", html).price == D("3979")
    with pytest.raises(PageParseError):
        parse_product_page("darwin", '<script type="application/ld+json">5</script>')


def test_unexpected_error_fails_one_offer_without_stopping_the_run(monkeypatch):
    def explode(store_slug, html):
        raise RuntimeError("store sent something strange")
    monkeypatch.setattr(check_offers, "parse_product_page", explode)
    offer = make_offer()
    status, details = check_offers.check_offer_safely(client_returning(200, "<html></html>"), offer)
    assert status == "failed" and "RuntimeError" in details[0]
    assert (offer.price_mdl, offer.availability, offer.checked_on) == (
        D("4000.00"), Availability.IN_STOCK, date(2026, 10, 21))


def test_rerunning_seed_keeps_checker_data():
    """seed.sql must not undo scripts.check_offers, nor fail because of a sale it doesn't know about."""
    import os
    import psycopg
    from sqlalchemy.engine import make_url

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated, seeded test PostgreSQL database")
    url = make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
    seed = (Path(__file__).parent.parent / "seed" / "seed.sql").read_text(encoding="utf-8")
    columns = "price_mdl, regular_price_mdl, availability::text, checked_on, last_check_status, url"
    find = ("SELECT o.id FROM offers o JOIN components c ON c.id = o.component_id JOIN stores s ON s.id = o.store_id "
            "WHERE c.slug = %s AND s.slug = %s")
    with psycopg.connect(url, autocommit=True) as conn:
        sale_id = conn.execute(find, ("intel-core-i5-14400f", "xstore")).fetchone()[0]
        moved_id = conn.execute(find, ("amd-ryzen-5-7600", "darwin")).fetchone()[0]
        originals = {i: conn.execute(f"SELECT {columns} FROM offers WHERE id = %s", (i,)).fetchone()
                     for i in (sale_id, moved_id)}
        try:
            # A checker result the seed doesn't know: price cut below the seed's 3709, on sale from 3600.
            conn.execute("UPDATE offers SET price_mdl = 3500, regular_price_mdl = 3600, availability = 'out_of_stock',"
                         " checked_on = DATE '2026-11-01', last_check_status = 'ok' WHERE id = %s", (sale_id,))
            # An offer whose URL in the database differs from seed.sql.
            conn.execute("UPDATE offers SET url = 'https://darwin.md/old-url.html', last_check_status = 'ok'"
                         " WHERE id = %s", (moved_id,))
            conn.execute(seed)  # used to fail with CheckViolation: regular_above_price
            kept = conn.execute(f"SELECT {columns} FROM offers WHERE id = %s", (sale_id,)).fetchone()
            assert kept[:5] == (D("3500.00"), D("3600.00"), "out_of_stock", date(2026, 11, 1), "ok")
            moved = conn.execute(f"SELECT {columns} FROM offers WHERE id = %s", (moved_id,)).fetchone()
            assert moved[5] == originals[moved_id][5] and moved[4] is None
        finally:
            for offer_id, (price, regular, availability, checked, status, offer_url) in originals.items():
                conn.execute("UPDATE offers SET price_mdl = %s, regular_price_mdl = %s, availability = %s,"
                             " checked_on = %s, last_check_status = %s, url = %s WHERE id = %s",
                             (price, regular, availability, checked, status, offer_url, offer_id))
