"""products.json (from `import_catalog crawl`) -> components, specs and offers in the database.

Run through `python -m scripts.import_catalog load`. Steps:
1. normalize every store page into our specs and skip what isn't a desktop PC part;
2. merge pages of the same product (part number, or CPU model + Box/Tray); pages whose key specs
   disagree, or two pages of one store, stay separate products. The load stops on any merge conflict (merge_conflicts);
3. fill missing specs (catalog_merge: platform facts, same-chip cards, PassMark chip pages);
4. perf_score for CPUs and GPUs from PassMark, for imported and hand-entered parts alike;
5. upsert components, specs and in-stock offers. A product whose page URL is already an
   offer of a component is that component: it gets the new offers. Components from
   seed/seed.sql keep their hand-checked specs; imported ones get today's specs.
   Imported components that this run no longer produces are deleted, unless a saved
   build uses them.
A product that still lacks a required spec is saved without specs (it is listed in the
report and shows as "specifications missing", so TOPSIS skips it).
"""

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import SPEC_MODELS, Availability, BuildItem, Category, Component, Offer as OfferRow, Store, Tier
from app.db.session import SessionLocal
from app.services.catalog_merge import (
    OPTIONAL, REQUIRED, Offer, Product, benchmark_scores, cpu_facts, gpu_clearance, gpu_from_chip, merge, merge_conflicts, other_facts,
    power_draw, tiers,
)
from app.services.catalog_normalize import cpu_chip, normalize
from scripts.crawl import CACHE, Fetcher

REPORT = CACHE / "import-report.json"
SEED = Path(__file__).resolve().parent.parent / "seed" / "seed.sql"
PASSMARK_CPU = ["https://www.cpubenchmark.net/desktop.html", "https://www.cpubenchmark.net/high_end_cpus.html",
                "https://www.cpubenchmark.net/mid_range_cpus.html", "https://www.cpubenchmark.net/low_end_cpus.html",
                "https://www.cpubenchmark.net/cpu_list.php"]
PASSMARK_GPU = ["https://www.videocardbenchmark.net/gpu_list.php", "https://www.videocardbenchmark.net/high_end_gpus.html",
                "https://www.videocardbenchmark.net/mid_range_gpus.html"]


def _marks(fetcher: Fetcher, urls: list[str]) -> dict[str, tuple[int, str]]:
    """Chip name -> (PassMark mark, chip page URL) from PassMark's charts and lists."""
    marks: dict[str, tuple[int, str]] = {}
    for url in urls:
        html = fetcher.get(url) or ""
        soup = BeautifulSoup(html, "html.parser")
        for row in soup.select("table#cputable tbody tr"):  # the *_list.php tables
            cells = row.find_all("td")
            link = row.find("a")
            if len(cells) >= 2 and link and re.sub(r"\D", "", cells[1].get_text()):
                marks.setdefault(cells[0].get_text(strip=True), (int(re.sub(r"\D", "", cells[1].get_text())),
                                                                 requests_url(url, link["href"])))
        for item in soup.select("ul.chartlist li"):  # the charts
            name, count, link = item.select_one(".prdname"), item.select_one(".count"), item.find("a")
            if name and count and link and re.sub(r"\D", "", count.get_text()):
                marks.setdefault(name.get_text(strip=True), (int(re.sub(r"\D", "", count.get_text())),
                                                             requests_url(url, link["href"])))
    return marks


def requests_url(base: str, href: str) -> str:
    """List links go to *_lookup.php; the chip pages are cpu.php / gpu.php."""
    from urllib.parse import urljoin
    return urljoin(base, href.replace("cpu_lookup.php", "cpu.php").replace("video_lookup.php", "gpu.php"))


def _chip_page(fetcher: Fetcher, url: str) -> dict[str, str]:
    """Label -> value from a PassMark chip page (cores, threads, clocks, TDP)."""
    soup = BeautifulSoup(fetcher.get(url) or "", "html.parser")
    out = {}
    for strong in soup.select(".desc strong, .desc-body strong, p strong"):
        label = strong.get_text(strip=True).rstrip(":")
        value = (strong.next_sibling or "")
        value = value.get_text(" ", strip=True) if hasattr(value, "get_text") else str(value).strip()
        if label and value:
            out.setdefault(label, value)
    return out


def _num(text: str | None) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group()) if m else None


def fill_from_passmark(products: list[Product], fetcher: Fetcher, cpu_marks, gpu_marks) -> None:
    from app.services.catalog_merge import find_mark
    for p in products:
        if p.category == Category.CPU and p.chip and {"cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w"} & set(p.missing):
            hit = find_mark(cpu_marks, p.chip, None)
            if not hit:
                continue
            page = _chip_page(fetcher, hit[1])
            cores = page.get("Cores") or page.get("Total Cores")
            m = re.search(r"(\d+)\s*Cores?,\s*(\d+)\s*Threads", " ".join(page.values()))
            p.fill("cores", int(m.group(1)) if m else (int(_num(cores)) if _num(cores) else None), "PassMark chip page")
            p.fill("threads", int(m.group(2)) if m else (int(_num(page.get("Threads"))) if _num(page.get("Threads")) else None), "PassMark chip page")
            p.fill("base_clock_ghz", _num(page.get("Clockspeed")), "PassMark chip page")
            p.fill("boost_clock_ghz", _num(page.get("Turbo Speed")), "PassMark chip page")
            tdp = _num(page.get("Typical TDP"))
            p.fill("tdp_w", int(tdp) if tdp else None, "PassMark chip page")
        if p.category == Category.GPU and p.chip and "tdp_w" in p.missing:
            hit = find_mark(gpu_marks, p.chip, p.fields.get("vram_gb"))
            if hit:
                tdp = _num(_chip_page(fetcher, hit[1]).get("Max TDP"))
                p.fill("tdp_w", int(tdp) if tdp else None, "PassMark chip page")


def fill_from_makers(products: list[Product], fetcher: Fetcher) -> None:
    """Case GPU clearance from the manufacturer page the store links (PrimePC doesn't list it)."""
    for p in products:
        if p.category == Category.CASE and "max_gpu_length_mm" in p.missing and p.maker_url:
            html = fetcher.get(p.maker_url)
            if html:
                text = BeautifulSoup(html, "html.parser").get_text(" ")
                p.fill("max_gpu_length_mm", gpu_clearance(text), f"manufacturer page {p.maker_url}")


def _slug(brand: str, model: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{brand} {model}".lower()).strip("-")[:110]
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


def _spec_values(p: Product) -> dict:
    names = REQUIRED[p.category] + OPTIONAL.get(p.category, ())
    values = {n: p.fields.get(n) for n in names}
    if p.category == Category.CPU:
        values["base_clock_ghz"] = Decimal(str(round(values["base_clock_ghz"], 1)))
        values["boost_clock_ghz"] = Decimal(str(round(values["boost_clock_ghz"], 1)))
    if p.category == Category.GPU:
        values["slot_width"] = Decimal(str(values["slot_width"]))
        values["chipset"] = values["chipset"][:60]
    if p.category == Category.COOLER:
        if values["cooler_type"] == "air" and not values.get("height_mm"):
            return {}
        if values["cooler_type"] == "aio" and not values.get("radiator_mm"):
            return {}
    return values


def load(products_file: Path) -> None:
    records = json.loads(products_file.read_text(encoding="utf-8"))
    skipped: dict[str, int] = {}
    pages = []
    for r in records:
        if r["title"].startswith("Купить") or not r["title"]:
            continue
        specs = normalize(Category(r["category"]), r["title"], r["specs"])
        if specs.skip:
            skipped[specs.skip] = skipped.get(specs.skip, 0) + 1
            continue
        regular = r["offer"]["regular_price"]
        pages.append((specs, Offer(r["store"], r["url"], Decimal(r["offer"]["price"]),
                                   None if regular is None else Decimal(regular))))
    products = merge(pages)
    print(f"{len(records)} in-stock pages -> {len(products)} products ({sum(skipped.values())} pages skipped: {skipped})")
    conflicts = merge_conflicts(products)
    if conflicts:
        # Nothing is written: a product made of pages that are not one product would reach the database.
        REPORT.write_text(json.dumps({"merge_conflicts": conflicts}, ensure_ascii=False, indent=1), encoding="utf-8")
        raise SystemExit(f"Load stopped: {len(conflicts)} merge conflicts (also in {REPORT}):\n" + "\n".join(conflicts))

    fetcher = Fetcher()
    cpu_marks, gpu_marks = _marks(fetcher, PASSMARK_CPU), _marks(fetcher, PASSMARK_GPU)
    for p in products:
        if p.category == Category.CPU:
            cpu_facts(p)
        other_facts(p)
    fill_from_passmark(products, fetcher, cpu_marks, gpu_marks)
    gpu_from_chip(products)
    fill_from_makers(products, fetcher)
    fetcher.close()

    with SessionLocal() as db:
        stores = {s.slug: s for s in db.scalars(select(Store))}
        missing_stores = {o.store for p in products for o in p.offers} - stores.keys()
        if missing_stores:
            raise SystemExit(f"Stores missing from the database: {missing_stores}. Run `python -m scripts.seed` first.")
        existing = list(db.scalars(select(Component).options(selectinload(Component.offers))))
        hand_entered = set(re.findall(r"^\s*\('([a-z0-9-]+)', '(?:cpu|motherboard|ram|gpu|storage|psu|case|cooler)'",
                                      SEED.read_text(encoding="utf-8"), re.M))
        by_url = {o.url: c for c in existing for o in c.offers}
        claimed: set[int] = set()
        used_slugs = {c.slug for c in existing}
        used_names = {(c.brand.lower(), c.model.lower()) for c in existing}

        # Hand-entered CPUs and GPUs get PassMark scores too, so all scores share one scale.
        scored = list(products)
        for c in existing:
            if c.category in (Category.CPU, Category.GPU) and not any(by_url.get(o.url) is c for p in products for o in p.offers):
                spec = db.get(SPEC_MODELS[c.category], c.id)
                chip = cpu_chip(c.model) if c.category == Category.CPU else (spec.chipset if spec else None)
                fields = {"vram_gb": spec.vram_gb} if c.category == Category.GPU and spec else {}
                scored.append(Product(c.category, f"existing:{c.id}", c.brand, c.model, chip, fields, []))
        unscored = {category.value: benchmark_scores(scored, category, marks,
                                                     "PassMark " + ("CPU Mark" if category == Category.CPU else "G3D Mark"))
                    for category, marks in ((Category.CPU, cpu_marks), (Category.GPU, gpu_marks))}
        tier_of = tiers(products)
        today = date.today()
        report = {"skipped_pages": skipped, "unscored_chips": unscored, "without_specs": [], "filled": {}}
        created = updated = offers_written = 0
        assigned: list[tuple[Component, Product]] = []

        for p in scored:
            if p.key.startswith("existing:"):
                c = db.get(Component, int(p.key.split(":")[1]))
                if p.perf_score is not None:
                    c.perf_score, c.perf_source = Decimal(str(p.perf_score)), p.perf_source
                continue
            # A component already claimed in this run was one product in an earlier run that is
            # now two (e.g. 512 GB and 1 TB pages merged by a series name): this one gets its own.
            component = next((by_url[o.url] for o in p.offers
                              if o.url in by_url and by_url[o.url].id not in claimed), None)
            if component is None:
                brand, model = p.brand[:60], p.model[:160]
                while (brand.lower(), model.lower()) in used_names:
                    model = f"{model} ({p.offers[0].store})"[:160]
                used_names.add((brand.lower(), model.lower()))
                component = Component(slug=_slug(brand, model, used_slugs), category=p.category, brand=brand,
                                      model=model, tier=Tier(tier_of[p.key]), power_draw_w=power_draw(p))
                db.add(component)
                db.flush()
                created += 1
            else:
                updated += 1
            claimed.add(component.id)
            if component.slug not in hand_entered:
                # Imported earlier or just now: today's pages decide its name, specs, tier and power.
                name_key = (p.brand[:60].lower(), p.model[:160].lower())
                if (component.brand.lower(), component.model.lower()) != name_key and name_key not in used_names:
                    used_names.discard((component.brand.lower(), component.model.lower()))
                    component.brand, component.model = p.brand[:60], p.model[:160]
                    used_names.add(name_key)
                component.tier, component.power_draw_w = Tier(tier_of[p.key]), power_draw(p)
                old = db.get(SPEC_MODELS[p.category], component.id)
                if old is not None:
                    db.delete(old)
                    db.flush()
                values = _spec_values(p) if not p.missing else {}
                name = f"{component.brand} {component.model}"
                if values:
                    db.add(SPEC_MODELS[p.category](component_id=component.id, **values))
                else:
                    report["without_specs"].append({"category": p.category.value, "name": name,
                                                    "missing": p.missing or ["cooler size"], "url": p.offers[0].url})
                if p.filled:
                    report["filled"][name] = p.filled
            if p.perf_score is not None and p.category in (Category.CPU, Category.GPU):
                component.perf_score, component.perf_source = Decimal(str(p.perf_score)), p.perf_source
            assigned.append((component, p))

        # Offers are rewritten from today's pages: a page's offer belongs to the component its
        # product went to, wherever an earlier (possibly wrong) merge had put it. First every offer
        # of an updated component and every offer of a page seen today is removed (through the
        # relationship, so deleting a stale component later can't take a moved offer with it);
        # a hand-entered component keeps the offers of stores that sell it no more today.
        run_urls = {o.url for _, p in assigned for o in p.offers}
        run_stores = {component.id: {stores[o.store].id for o in p.offers} for component, p in assigned}
        for c in existing:
            for row in list(c.offers):
                if row.url in run_urls or (c.id in claimed and (c.slug not in hand_entered
                                                                 or row.store_id in run_stores[c.id])):
                    c.offers.remove(row)
        db.flush()
        for component, p in assigned:
            for o in p.offers:
                component.offers.append(OfferRow(
                    store_id=stores[o.store].id, url=o.url, price_mdl=o.price, regular_price_mdl=o.regular_price,
                    availability=Availability.IN_STOCK, checked_on=today, last_check_status="ok"))
                offers_written += 1

        # Imported components this run no longer produces (now skipped, e.g. SAS drives, or
        # gone from the stores) are removed, unless a saved build uses them.
        in_builds = set(db.scalars(select(BuildItem.component_id)))
        stale = [c for c in existing if c.slug not in hand_entered and c.id not in claimed]
        removed = [c for c in stale if c.id not in in_builds]
        for c in removed:
            db.delete(c)
        report["removed"] = [f"{c.brand} {c.model}" for c in removed]
        report["kept_in_saved_builds"] = [f"{c.brand} {c.model}" for c in stale if c.id in in_builds]
        db.commit()

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Created {created} components, added offers to {updated} existing ones, wrote {offers_written} offers.")
    print(f"{len(report['without_specs'])} products saved without specs (missing data); details in {REPORT}")
    print(f"Removed {len(report['removed'])} imported components no longer found; "
          f"kept {len(report['kept_in_saved_builds'])} that saved builds use.")
    for category, chips in unscored.items():
        if chips:
            print(f"No PassMark score for {len(chips)} {category} chips: {', '.join(chips[:15])}")
