"""Check every offer's product page and update price, sale price and stock.

Usage (from backend/):  python -m scripts.check_offers

Run it whenever you want fresh data; .github/workflows/check-offers.yml also runs it
twice a day. It is polite to the stores: it follows their robots.txt, sends at most
one request every 2 seconds to each store, and identifies itself in the User-Agent.

If a page can't be read, that offer keeps its previous values and is marked
'failed' ('page_gone' for 404/410), so a broken page never erases good data.

A few failed pages are normal and the run still exits with 0. It exits with 1 when a
store looks broken (see broken_stores): the sign that the store changed its page
layout or is blocking the checker, which a person has to look at.
"""

import sys
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
# A full run takes an hour or more; a line every this many offers shows it is alive.
PROGRESS_EVERY = 100
# A store is "broken" when more than this share of its offers failed or disappeared
# (404/410) in this run. Pages that were already gone at the previous check don't count:
# discontinued products are expected and pile up over time, but many pages vanishing
# at once means the store changed its addresses.
MAX_FAILED_SHARE_PER_STORE = 0.20
# ...but never on fewer failures than this, so a store with a handful of offers
# doesn't raise the alarm over one or two odd pages.
MIN_FAILED_TO_ALARM = 5


def broken_stores(by_store: dict[str, dict[str, int]]) -> list[str]:
    """One line per store whose failures pass both limits above. `by_store` maps a store's
    name to its counts per status: 'ok', 'failed', 'page_gone' (was already gone at the
    previous check) and 'newly_gone' (gone since this run)."""
    lines = []
    for store, counts in by_store.items():
        failed, checked = counts.get("failed", 0) + counts.get("newly_gone", 0), sum(counts.values())
        if failed >= MIN_FAILED_TO_ALARM and failed > MAX_FAILED_SHARE_PER_STORE * checked:
            lines.append(f"{store}: {failed} of {checked} offers failed or disappeared ({failed / checked:.0%})")
    return lines


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
        per_store: dict[str, dict[str, int]] = {}
        report: list[str] = []
        print(f"Checking {len(offers)} offers...")

        # Interleave stores so the per-store pause doesn't make the whole run slow.
        by_store: dict[str, list[Offer]] = {}
        for offer in offers:
            by_store.setdefault(offer.store.slug, []).append(offer)
        queue = [o for group in zip_longest(*by_store.values()) for o in group if o is not None]

        started = time.monotonic()
        for done, offer in enumerate(queue, start=1):
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

            tally = "newly_gone" if status == "page_gone" and offer.last_check_status != "page_gone" else status
            store_counts = per_store.setdefault(offer.store.name, {})
            store_counts[tally] = store_counts.get(tally, 0) + 1
            offer.last_check_status = status
            db.commit()
            counts[status] += 1
            if done % PROGRESS_EVERY == 0 and done < len(queue):
                print(f"  {done} / {len(queue)} checked after {(time.monotonic() - started) / 60:.0f} min "
                      f"({counts['failed']} failed, {counts['page_gone']} page gone)", flush=True)
            label = f"{offer.store.name:12} {offer.component.slug}"
            if status != "ok":
                report.append(f"  FAILED  {label}: {'; '.join(details)}")
            elif details:
                counts["changed"] += 1
                report.append(f"  changed {label}: {', '.join(details)}")

        print("\nChanges and failures:")
        print("\n".join(report) if report else "  no changes")
        print(f"Done: {counts['ok']} ok ({counts['changed']} changed), "
              f"{counts['failed']} failed, {counts['page_gone']} page gone.")

    broken = broken_stores(per_store)
    if broken:
        print("\nToo many failures; the store changed its page layout or addresses, or it is blocking the checker:")
        print("\n".join(f"  {line}" for line in broken))
        sys.exit(1)


if __name__ == "__main__":
    main()
