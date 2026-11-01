"""Import every in-stock PC component from the stores into the catalog.

Usage (from backend/):
    python -m scripts.import_catalog crawl [store ...]   # store pages -> .crawl-cache/products.json
    python -m scripts.import_catalog load    # products.json -> specs, perf scores -> database

`crawl` uses Crawlee: one crawler per store, all stores at once. It reads each store's
category listings (Neocomputer: its product sitemap, because its robots.txt forbids
?page=), then every product page, and saves title, breadcrumb, spec table, price and
stock of the in-stock ones. It follows robots.txt (with wildcards), sends at most one
request every 0.5 s to each store (Neocomputer: every 3 s), and names the project in its User-Agent. Product
pages are cached in .crawl-cache/, so a rerun only asks for pages it hasn't seen.
"""

import asyncio
import gzip
import subprocess
import hashlib
import json
import sys
import unicodedata
from dataclasses import asdict

from crawlee import ConcurrencySettings, Request
from crawlee.crawlers import HttpCrawler, HttpCrawlingContext
from crawlee.http_clients import ImpitHttpClient
from crawlee.storage_clients import MemoryStorageClient

from app.db.models import Availability, Category
from app.services.store_catalog import (
    LISTINGS, NEOCOMPUTER_CATEGORIES, NEOCOMPUTER_SITEMAP, ProductPage, listing_products,
    neocomputer_candidates, page_url, parse_product,
)
from scripts.crawl import CACHE, USER_AGENT

PRODUCTS = CACHE / "products.json"
MAX_PAGES = 80
REQUESTS_PER_MINUTE_PER_STORE = 120  # one request every 0.5 s
# Neocomputer stopped answering at that rate, so it gets one request every 3 s, one at a time.
SLOWER = {"neocomputer": 20}
HEADERS = {"User-Agent": USER_AGENT}


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()


def _cache_path(url: str):
    return CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.html.gz"


def _cached(url: str) -> str | None:
    path = _cache_path(url)
    return gzip.decompress(path.read_bytes()).decode("utf-8", "replace") if path.exists() else None


class StoreCrawl:
    """Listings -> product pages for one store; in-stock products end up in `records`."""

    def __init__(self, store: str):
        self.store = store
        self.records: list[dict] = []
        self.seen: set[str] = set()
        self.read = 0
        self.crawler = HttpCrawler(
            http_client=ImpitHttpClient(browser=None, headers=HEADERS),
            storage_client=MemoryStorageClient(),
            concurrency_settings=ConcurrencySettings(
                min_concurrency=1, desired_concurrency=1 if store in SLOWER else 2,
                max_concurrency=1 if store in SLOWER else 2,
                max_tasks_per_minute=SLOWER.get(store, REQUESTS_PER_MINUTE_PER_STORE)),
            respect_robots_txt_file=True,
            max_request_retries=2,
            configure_logging=False,
        )
        self.crawler.router.default_handler(self._handle)

    def _product(self, url: str, category: Category | None, html: str) -> None:
        page: ProductPage = parse_product(self.store, html)
        self.read += 1
        if self.read % 200 == 0:
            print(f"  {self.store:12} {self.read} product pages read, {len(self.records)} in stock", flush=True)
        if category is None:  # Neocomputer: the breadcrumb's last category level decides
            levels = [_plain(b) for b in page.breadcrumb[:-1]]
            category = next((NEOCOMPUTER_CATEGORIES[l] for l in reversed(levels) if l in NEOCOMPUTER_CATEGORIES), None)
            if category is None:
                return
        if page.offer is None or page.offer.availability != Availability.IN_STOCK:
            return
        record = asdict(page)
        record["offer"] = {"price": str(page.offer.price),
                           "regular_price": None if page.offer.regular_price is None else str(page.offer.regular_price)}
        record.update(store=self.store, category=category.value, url=url)
        self.records.append(record)

    async def _queue_products(self, context: HttpCrawlingContext, category: Category | None, urls: list[str]) -> None:
        fresh = []
        for url in urls:
            if url in self.seen:
                continue
            self.seen.add(url)
            html = _cached(url)
            if html is not None:
                self._product(url, category, html)
            else:
                fresh.append(Request.from_url(url, headers=HEADERS, label="product",
                                              user_data={"category": category and category.value}))
        if fresh:
            await context.add_requests(fresh)

    async def _handle(self, context: HttpCrawlingContext) -> None:
        request = context.request
        body = await context.http_response.read()
        html = body.decode("utf-8", "replace")
        data = request.user_data
        if request.label == "product":
            _cache_path(request.url).write_bytes(gzip.compress(body))
            category = data.get("category")
            self._product(request.url, category and Category(category), html)
        elif request.label == "sitemap":
            await self._queue_products(context, None, neocomputer_candidates(html))
        else:  # a listing page: queue its products and, if it had new ones, the next page
            category, listing, page = Category(data["category"]), data["listing"], data["page"]
            urls = listing_products(self.store, html, listing)
            new = [u for u in urls if u not in self.seen]
            await self._queue_products(context, category, urls)
            if new and page < MAX_PAGES:
                await context.add_requests([self._listing(category, listing, page + 1)])

    def _listing(self, category: Category, listing: str, page: int) -> Request:
        return Request.from_url(page_url(listing, page), headers=HEADERS, label="listing",
                                user_data={"category": category.value, "listing": listing, "page": page})

    async def run(self) -> None:
        if self.store == "neocomputer":
            start = [Request.from_url(NEOCOMPUTER_SITEMAP, headers=HEADERS, label="sitemap")]
        else:
            start = [self._listing(c, url, 1) for c, urls in LISTINGS[self.store].items() for url in urls]
        await self.crawler.run(start)
        print(f"  {self.store:12} done: {self.read} product pages, {len(self.records)} in stock", flush=True)


STORES = [*LISTINGS, "neocomputer"]


def _store_file(store: str):
    return CACHE / f"products-{store}.json"


async def crawl_store(store: str) -> None:
    crawl = StoreCrawl(store)
    await crawl.run()
    _store_file(store).write_text(json.dumps(crawl.records, ensure_ascii=False, indent=0), encoding="utf-8")


def crawl(stores: list[str]) -> None:
    """Crawl `stores` at the same time, each in its own process (Crawlee crawlers in one
    process share global state and stop each other), then merge every store's file."""
    processes = [subprocess.Popen([sys.executable, "-m", "scripts.import_catalog", "crawl-store", s]) for s in stores]
    failed = [s for s, p in zip(stores, processes) if p.wait() != 0]
    records = [r for s in STORES if _store_file(s).exists()
               for r in json.loads(_store_file(s).read_text(encoding="utf-8"))]
    PRODUCTS.write_text(json.dumps(records, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Saved {len(records)} in-stock products to {PRODUCTS}" + (f"; failed: {', '.join(failed)}" if failed else ""))


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    CACHE.mkdir(exist_ok=True)
    if command == "crawl":
        stores = sys.argv[2:] or STORES
        if unknown := set(stores) - set(STORES):
            sys.exit(f"Unknown stores: {', '.join(sorted(unknown))}. Known: {', '.join(STORES)}")
        crawl(stores)
    elif command == "crawl-store":
        asyncio.run(crawl_store(sys.argv[2]))
    elif command == "load":
        from scripts.catalog_load import load
        load(PRODUCTS)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
