"""Check every offer's product page and update price, sale price and stock.

Usage (from backend/):  python -m scripts.check_offers

Run it whenever you want fresh data; nothing runs automatically. It is polite to
the stores: it follows their robots.txt, sends at most one request every
2 seconds to each store, and identifies itself in the User-Agent.

If a page can't be read, that offer keeps its previous values and is marked
'failed' ('page_gone' for 404/410), so a broken page never erases good data.
"""

import time
from datetime import date
from itertools import zip_longest
from decimal import Decimal
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.models import Offer
from app.db.session import SessionLocal
from app.services.store_pages import PageParseError, parse_product_page

USER_AGENT = "PC-Configurator-student-project/0.1 (+https://github.com/CsDevJs/OptimRig)"
SECONDS_BETWEEN_REQUESTS_PER_STORE = 2.0


def _robots(client: httpx.Client, site: str) -> RobotFileParser:
    parser = RobotFileParser()
    try:
        response = client.get(f"{site}/robots.txt")
        # No robots.txt (4xx) means everything is allowed.
        parser.parse(response.text.splitlines() if response.status_code == 200 else [])
    except httpx.HTTPError:
        parser.parse([])
    return parser


def _fetch(client: httpx.Client, url: str) -> httpx.Response:
    """GET with one retry on network errors and server errors."""
    for attempt in range(2):
        try:
            response = client.get(url)
            if response.status_code < 500 or attempt == 1:
                return response
        except httpx.HTTPError:
            if attempt == 1:
                raise
        time.sleep(3)
    raise AssertionError("unreachable")


def _fmt(value: Decimal | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _same_page(a: str, b: str) -> bool:
    """Same host and path; ignores http/https, a trailing slash and the query string."""
    a_parts, b_parts = urlsplit(a), urlsplit(b)
    return (a_parts.netloc.lower().removeprefix("www."), a_parts.path.rstrip("/")) == (
        b_parts.netloc.lower().removeprefix("www."), b_parts.path.rstrip("/"))


def check_offer(client: httpx.Client, offer: Offer) -> tuple[str, list[str]]:
    """Check one offer in place. Returns (status, human-readable changes or the failure reason)."""
    try:
        response = _fetch(client, offer.url)
    except httpx.HTTPError as error:
        return "failed", [f"network error: {error.__class__.__name__}"]
    if response.status_code in (404, 410):
        return "page_gone", [f"HTTP {response.status_code}"]
    if response.status_code != 200:
        return "failed", [f"HTTP {response.status_code}"]
    # Stores redirect discontinued products to other pages, often a different product.
    # Reading that page would save the wrong product's price, so stop and let a person decide.
    if not _same_page(str(response.url), offer.url):
        return "failed", [f"redirected to {response.url}; update the offer URL if it's the same product"]
    try:
        page = parse_product_page(offer.store.slug, response.text)
    except PageParseError as error:
        return "failed", [str(error)]

    changes = []
    if page.price != offer.price_mdl:
        changes.append(f"price {_fmt(offer.price_mdl)} -> {_fmt(page.price)}")
    if page.regular_price != offer.regular_price_mdl:
        if page.regular_price is None:
            changes.append("sale ended")
        else:
            changes.append(f"on sale (regular {_fmt(page.regular_price)})")
    if page.availability != offer.availability:
        changes.append(f"{offer.availability.value} -> {page.availability.value}")

    offer.price_mdl = page.price
    offer.regular_price_mdl = page.regular_price
    offer.availability = page.availability
    offer.checked_on = date.today()
    return "ok", changes


def check_offer_safely(client: httpx.Client, offer: Offer) -> tuple[str, list[str]]:
    """Like check_offer, but an unexpected error fails this offer instead of stopping the run."""
    before = (offer.price_mdl, offer.regular_price_mdl, offer.availability, offer.checked_on)
    try:
        return check_offer(client, offer)
    except Exception as error:  # noqa: BLE001 - one odd page must not stop the other 170 checks
        offer.price_mdl, offer.regular_price_mdl, offer.availability, offer.checked_on = before
        return "failed", [f"unexpected error: {error.__class__.__name__}: {error}"]


def main() -> None:
    with SessionLocal() as db, httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True
    ) as client:
        offers = list(db.scalars(
            select(Offer).options(joinedload(Offer.store), joinedload(Offer.component)).order_by(Offer.id)
        ))
        robots = {}
        last_request: dict[str, float] = {}
        counts = {"ok": 0, "failed": 0, "page_gone": 0, "changed": 0}
        report: list[str] = []
        print(f"Checking {len(offers)} offers...")

        # Interleave stores so the per-store pause doesn't make the whole run slow.
        by_store: dict[str, list[Offer]] = {}
        for offer in offers:
            by_store.setdefault(offer.store.slug, []).append(offer)
        queue = [o for group in zip_longest(*by_store.values()) for o in group if o is not None]

        for offer in queue:
            store = offer.store.slug
            site = "{0.scheme}://{0.netloc}".format(urlsplit(offer.url))
            if site not in robots:
                robots[site] = _robots(client, site)
            if not robots[site].can_fetch(USER_AGENT, offer.url):
                status, details = "failed", ["robots.txt disallows this page"]
            else:
                wait = SECONDS_BETWEEN_REQUESTS_PER_STORE - (time.monotonic() - last_request.get(store, 0))
                if wait > 0:
                    time.sleep(wait)
                last_request[store] = time.monotonic()
                status, details = check_offer_safely(client, offer)

            offer.last_check_status = status
            db.commit()
            counts[status] += 1
            label = f"{offer.store.name:12} {offer.component.slug}"
            if status != "ok":
                report.append(f"  FAILED  {label}: {'; '.join(details)}")
            elif details:
                counts["changed"] += 1
                report.append(f"  changed {label}: {', '.join(details)}")

        print("\n".join(report) if report else "  no changes")
        print(f"Done: {counts['ok']} ok ({counts['changed']} changed), "
              f"{counts['failed']} failed, {counts['page_gone']} page gone.")


if __name__ == "__main__":
    main()
