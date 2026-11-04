"""Compare random merged products with their stores' live pages.

    python -m scripts.spot_check [per_store]

For every store, `per_store` (default 10) random components that have offers from two or more
stores and one from this store. The store's live page is fetched (not the crawl cache) and
compared with the database:
- name: the live page's identity key equals the key of the component's other store pages;
- capacity: the live page's key specs (RAM size/sticks/speed/CL, drive size, VRAM, wattage,
  board chipset/memory, CPU graphics) agree with the component's specs;
- price: the live price equals the saved offer price (a difference may be a price change
  since the crawl, which the next crawl picks up).
Prints one line per product and the totals; exits with 1 when a name or capacity differs.
"""

import gzip
import hashlib
import random
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import SPEC_MODELS, Category, Component, Offer, Store
from app.db.session import SessionLocal
from app.services.catalog_merge import KEY_SPECS, key_specs
from app.services.catalog_normalize import Specs, normalize
from app.services.store_catalog import parse_product
from scripts.crawl import CACHE, Fetcher


def _cached(url: str) -> str | None:
    path = CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.html.gz"
    return gzip.decompress(path.read_bytes()).decode("utf-8", "replace") if path.exists() else None


def _specs(store: str, category: Category, html: str) -> tuple[Specs, object]:
    page = parse_product(store, html)
    return normalize(category, page.title, page.specs), page


def main() -> None:
    per_store = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    fetcher = Fetcher(use_cache=False)
    bad = price_changed = checked = 0
    with SessionLocal() as db:
        stores = {s.id: s.slug for s in db.scalars(select(Store))}
        merged = [c for c in db.scalars(select(Component).options(selectinload(Component.offers)))
                  if len({o.store_id for o in c.offers}) >= 2]
        for store_id, store in sorted(stores.items(), key=lambda s: s[1]):
            pool = [c for c in merged if any(o.store_id == store_id for o in c.offers)]
            print(f"\n== {store}: {min(per_store, len(pool))} of {len(pool)} merged products")
            for c in random.sample(pool, min(per_store, len(pool))):
                offer: Offer = next(o for o in c.offers if o.store_id == store_id)
                html = fetcher.get(offer.url)
                if html is None:
                    print(f"  ?  {c.brand} {c.model}: live page did not load ({offer.url})")
                    continue
                checked += 1
                live, page = _specs(store, c.category, html)
                others = [_specs(stores[o.store_id], c.category, h)[0] for o in c.offers
                          if o.store_id != store_id and (h := _cached(o.url))]
                spec = db.get(SPEC_MODELS[c.category], c.id)
                saved = {n: getattr(spec, n) for n in KEY_SPECS.get(c.category, ())} if spec else {}
                saved = key_specs(Specs(c.category, c.brand, c.model, "", {k: v for k, v in saved.items() if v is not None}))
                stated = key_specs(live)
                problems = []
                if others and all(o.key.split("#")[0] != live.key.split("#")[0] for o in others):
                    problems.append(f"name: key {live.key} vs {sorted({o.key for o in others})}")
                if differ := [n for n in stated.keys() & saved.keys() if stated[n] != saved[n]]:
                    problems.append("capacity: " + ", ".join(f"{n} live {stated[n]} saved {saved[n]}" for n in differ))
                price = page.offer.price if page.offer else None
                note = "" if price == offer.price_mdl else f"  (price {offer.price_mdl} saved, {price} live)"
                price_changed += bool(note)
                bad += bool(problems)
                print(f"  {'X ' if problems else 'ok'} {c.brand} {c.model} | live: {page.title}{note}")
                for p in problems:
                    print(f"       {p}")
    fetcher.close()
    print(f"\n{checked} live pages checked: {bad} name/capacity mismatches, {price_changed} price differences")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
