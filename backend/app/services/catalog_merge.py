"""Merge store pages of the same product and fill the specs the pages leave out.

Independent of HTTP and the database. Order of sources for each spec field:
1. the product's own pages (the value most stores agree on);
2. facts that follow from the chip or platform (an AM5 CPU uses DDR5, an "F" Intel CPU
   has no graphics, a Tray CPU has no cooler);
3. the values other products with the same chip state (GPU TDP and recommended PSU);
4. PassMark's page for the chip (CPU cores/threads/clocks/TDP, GPU TDP);
5. the manufacturer's product page linked by the store (case maximum GPU length).
Every filled value is recorded in `Product.filled` with its source.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median

from app.db.models import Category
from app.services.catalog_normalize import Specs

REQUIRED: dict[Category, tuple[str, ...]] = {
    Category.CPU: ("socket", "cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w",
                   "integrated_graphics", "memory_types", "includes_cooler"),
    Category.MOTHERBOARD: ("socket", "chipset", "form_factor", "memory_type", "memory_slots", "max_memory_gb",
                           "m2_slots", "sata_ports", "wifi"),
    Category.RAM: ("memory_type", "capacity_gb", "modules", "speed_mts", "cas_latency"),
    Category.GPU: ("chipset", "vram_gb", "length_mm", "slot_width", "tdp_w", "recommended_psu_w"),
    Category.STORAGE: ("storage_type", "interface", "form_factor", "capacity_gb"),
    Category.PSU: ("wattage", "efficiency", "modular", "form_factor", "has_16pin"),
    Category.CASE: ("supported_board_form_factors", "max_gpu_length_mm", "max_cooler_height_mm",
                    "psu_form_factor", "included_fans"),
    Category.COOLER: ("cooler_type", "supported_sockets"),
}
OPTIONAL = {
    Category.GPU: ("power_connectors",), Category.STORAGE: ("read_mbps", "write_mbps"),
    Category.CASE: ("max_radiator_mm",), Category.COOLER: ("height_mm", "radiator_mm", "max_tdp_w"),
}

SOCKET_MEMORY = {"AM4": ["DDR4"], "AM5": ["DDR5"], "LGA1851": ["DDR5"], "LGA1700": ["DDR4", "DDR5"],
                 "LGA1200": ["DDR4"], "LGA1151": ["DDR4"]}


@dataclass
class Offer:
    store: str
    url: str
    price: Decimal
    regular_price: Decimal | None


@dataclass
class Product:
    category: Category
    key: str
    brand: str
    model: str
    chip: str | None
    fields: dict
    offers: list[Offer]
    filled: dict[str, str] = field(default_factory=dict)  # field -> where the value came from
    perf_score: float | None = None
    perf_source: str | None = None
    maker_url: str | None = None
    pages: list[Specs] = field(default_factory=list)  # what each store page said, in offer order

    @property
    def missing(self) -> list[str]:
        return [f for f in REQUIRED[self.category] if self.fields.get(f) in (None, [])]

    def fill(self, name: str, value, source: str) -> None:
        if self.fields.get(name) in (None, []) and value not in (None, []):
            self.fields[name] = value
            self.filled[name] = source


def _mode(values: list):
    values = [v for v in values if v not in (None, [])]
    if not values:
        return None
    counts = Counter(tuple(v) if isinstance(v, list) else v for v in values)
    best = counts.most_common(1)[0][0]
    return list(best) if isinstance(best, tuple) else best


# Specs that tell products apart: pages under one identity key that disagree on one of these
# are different products (a part number guessed wrong, a series name shared by several sizes).
KEY_SPECS: dict[Category, tuple[str, ...]] = {
    Category.CPU: ("integrated_graphics",),
    Category.MOTHERBOARD: ("chipset", "memory_type"),
    Category.RAM: ("capacity_gb", "modules", "speed_mts", "cas_latency"),
    Category.GPU: ("vram_gb",),
    Category.STORAGE: ("capacity_gb",),
    Category.PSU: ("wattage",),
}


def key_specs(specs: Specs) -> dict:
    """The page's key specs that it states. Drive sizes are compared in 100 GB steps, so "1 TB"
    (1000) and "1024 GB" agree; chipsets without the letter after the number, which stores
    write differently for the same board (A620 / A620A, B650 / B650E)."""
    out = {}
    for name in KEY_SPECS.get(specs.category, ()):
        value = specs.fields.get(name)
        if value is None:
            continue
        if specs.category == Category.STORAGE:
            value = round(value / 100)
        elif name == "chipset":
            value = re.match(r"[A-Z]+\d*", value).group()
        out[name] = value
    return out


def _disagree(a: dict, b: dict) -> list[str]:
    return [n for n in a.keys() & b.keys() if a[n] != b[n]]


def _split(items: list[tuple[Specs, Offer]]) -> list[list[tuple[Specs, Offer]]]:
    """Pages of one identity key, grouped so no group holds two pages of one store or pages
    whose key specs disagree. Pages stating more key specs are placed first."""
    clusters: list[list[tuple[Specs, Offer]]] = []
    for specs, offer in sorted(items, key=lambda i: (-len(key_specs(i[0])), i[1].store, i[1].url)):
        mine = key_specs(specs)
        for cluster in clusters:
            if all(o.store != offer.store and not _disagree(mine, key_specs(s)) for s, o in cluster):
                cluster.append((specs, offer))
                break
        else:
            clusters.append([(specs, offer)])
    return clusters


def merge(pages: list[tuple[Specs, Offer]]) -> list[Product]:
    """One Product per identity key and set of agreeing pages: two pages of one store, or pages
    whose key specs disagree, are different products."""
    groups: dict[str, list[tuple[Specs, Offer]]] = {}
    for specs, offer in pages:
        groups.setdefault(specs.key, []).append((specs, offer))
    products = []
    for key, items in groups.items():
        for n, cluster in enumerate(_split(items), start=1):
            specs_list = [s for s, _ in cluster]
            names = set().union(*(s.fields for s in specs_list))
            fields = {f: _mode([s.fields.get(f) for s in specs_list]) for f in names}
            first = specs_list[0]
            products.append(Product(
                category=first.category, key=key if n == 1 else f"{key}#{n}",
                brand=_mode([s.brand for s in specs_list]) or "Unknown",
                model=min((s.model for s in specs_list), key=len), chip=_mode([s.chip for s in specs_list]),
                fields=fields, offers=[o for _, o in cluster], maker_url=_mode([s.maker_url for s in specs_list]),
                pages=specs_list,
            ))
    return products


def merge_conflicts(products: list[Product]) -> list[str]:
    """Every product whose pages are not one product: two pages of one store, pages whose key
    specs or brands disagree. The import stops when this is not empty."""
    out = []
    for p in products:
        stores = Counter(o.store for o in p.offers)
        urls = ", ".join(o.url for o in p.offers)
        for store, count in stores.items():
            if count > 1:
                out.append(f"{p.key}: {count} pages of {store} ({urls})")
        stated = [key_specs(s) for s in p.pages]
        for name in KEY_SPECS.get(p.category, ()):
            values = {s[name] for s in stated if name in s}
            if len(values) > 1:
                out.append(f"{p.key}: pages disagree on {name} {sorted(values)} ({urls})")
    return out


def cpu_facts(product: Product) -> None:
    """What the CPU's name and platform settle."""
    chip = (product.chip or "").upper()
    socket = product.fields.get("socket")
    if socket is None:
        if re.search(r"RYZEN \d (PRO )?(7|8|9)\d{3}", chip):
            product.fill("socket", "AM5", "Ryzen 7000/8000/9000 desktop CPUs use AM5")
        elif re.search(r"RYZEN \d (PRO )?[1-5]\d{3}", chip):
            product.fill("socket", "AM4", "Ryzen 1000-5000 desktop CPUs use AM4")
        elif re.search(r"CORE ULTRA \d 2\d{2}", chip):
            product.fill("socket", "LGA1851", "Core Ultra 200S CPUs use LGA1851")
        elif re.search(r"I\d-1[234]\d{3}|PENTIUM G7|CORE \d 1\d{2}", chip):
            product.fill("socket", "LGA1700", "12th-14th gen Core CPUs use LGA1700")
        elif re.search(r"I\d-1[01]\d{3}|PENTIUM G6|CELERON G5", chip):
            product.fill("socket", "LGA1200", "10th/11th gen Core CPUs use LGA1200")
        socket = product.fields.get("socket")
    if socket in SOCKET_MEMORY:
        # The platform's memory support is a fact of the socket; a store listing only one type is incomplete.
        if sorted(product.fields.get("memory_types") or []) != SOCKET_MEMORY[socket]:
            product.fields["memory_types"] = []
        product.fill("memory_types", SOCKET_MEMORY[socket], f"{socket} platform memory support")
    if product.fields.get("integrated_graphics") is None and chip:
        intel = "CORE" in chip or "PENTIUM" in chip or "CELERON" in chip
        if intel:
            has = not re.search(r"\d[A-Z]*F\b|KF\b", chip)
            product.fill("integrated_graphics", has, "Intel F-models have no graphics, others do")
        elif socket == "AM5":
            product.fill("integrated_graphics", not re.search(r"\d{4}F\b", chip), "AM5 Ryzen have graphics except F-models")
        elif socket == "AM4":
            product.fill("integrated_graphics", bool(re.search(r"\d{4}G", chip)), "AM4 Ryzen have graphics only in G-models")
    if product.fields.get("includes_cooler") is None:
        # Without a stated cooler, assume none: the build then asks for a cooler instead of
        # possibly leaving the CPU without one.
        product.fill("includes_cooler", False, "not stated; assumed no bundled cooler")


def other_facts(product: Product) -> None:
    """Fields the compatibility rules don't read, or that follow from the platform."""
    f = product.fields
    if product.category == Category.MOTHERBOARD and f.get("memory_type") and f.get("memory_slots"):
        # Largest desktop module sold today: 32 GB DDR4, 64 GB DDR5.
        per_slot = 64 if f["memory_type"] == "DDR5" else 32
        product.fill("max_memory_gb", per_slot * f["memory_slots"], f"{f['memory_slots']} slots x {per_slot} GB modules")
    if product.category == Category.CASE:
        product.fill("included_fans", 0, "not stated; assumed none")
    if product.category == Category.PSU:
        product.fill("efficiency", "not stated", "not stated by the stores")
        product.fill("modular", "none", "not stated; assumed non-modular")


def chip_values(products: list[Product], category: Category, fields: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """Median of each field over the products of the same chip that state it."""
    values: dict[str, dict[str, list]] = {}
    for p in products:
        if p.category != category or not p.chip:
            continue
        for f in fields:
            v = p.fields.get(f)
            if v is not None and f not in p.filled:
                values.setdefault(p.chip, {}).setdefault(f, []).append(v)
    return {chip: {f: median(vs) for f, vs in by.items()} for chip, by in values.items()}


def gpu_from_chip(products: list[Product]) -> None:
    by_chip = chip_values(products, Category.GPU, ("tdp_w", "recommended_psu_w", "slot_width"))
    longest: dict[str, int] = {}
    for p in products:
        if p.category == Category.GPU and p.chip and p.fields.get("length_mm") and "length_mm" not in p.filled:
            longest[p.chip] = max(longest.get(p.chip, 0), p.fields["length_mm"])
    for p in products:
        if p.category != Category.GPU or not p.chip:
            continue
        for f in ("tdp_w", "recommended_psu_w", "slot_width"):
            v = by_chip.get(p.chip, {}).get(f)
            if v is not None:
                v = round(v * 2) / 2 if f == "slot_width" else int(round(v / 10) * 10 if f == "recommended_psu_w" else round(v))
                p.fill(f, v, f"median of other {p.chip} cards")
        if p.chip in longest:
            # The longest card with this chip: a case that fits it fits this card too.
            p.fill("length_mm", longest[p.chip], f"longest {p.chip} card in the catalog")


def power_draw(p: Product) -> int:
    """Peak draw in W, like the hand-entered seed: CPU package power, GPU board power, small fixed values."""
    f = p.fields
    if p.category == Category.CPU:
        tdp = f.get("tdp_w") or 65
        chip = (p.chip or "").upper()
        if "RYZEN" in chip or "ATHLON" in chip:
            return int(round(tdp * 1.35))  # AMD PPT = 1.35 x TDP
        # Intel maximum turbo power (PL2) by base power class.
        return {35: 106, 58: 89, 60: 89, 65: 154, 125: 253}.get(tdp, int(round(tdp * 1.8)))
    if p.category == Category.GPU:
        return f.get("tdp_w") or 0
    if p.category == Category.MOTHERBOARD:
        chipset = (f.get("chipset") or "").upper()
        return 60 if chipset[:1] in ("X", "Z") else 45 if chipset[:1] == "B" else 40
    if p.category == Category.RAM:
        per = 4 if f.get("memory_type") == "DDR5" else 3
        return per * (f.get("modules") or 1) + 2 * max(0, (f.get("capacity_gb") or 0) // 32 - 1)
    if p.category == Category.STORAGE:
        return {"hdd": 8, "sata_ssd": 3}.get(f.get("storage_type"), 6)
    if p.category == Category.CASE:
        return max(3, 3 * (f.get("included_fans") or 0))
    if p.category == Category.COOLER:
        return 12 if f.get("cooler_type") == "aio" else 4
    return 0


def tiers(products: list[Product]) -> dict[str, str]:
    """low / mid / high by price thirds within each category."""
    out = {}
    for category in Category:
        items = sorted((p for p in products if p.category == category), key=lambda p: min(o.price for o in p.offers))
        for i, p in enumerate(items):
            out[p.key] = ("low", "mid", "high")[min(2, 3 * i // max(1, len(items)))]
    return out


def _bench_key(name: str) -> str:
    name = re.sub(r"@.*", "", name)
    name = re.sub(r"\b(AMD|Intel|NVIDIA|GeForce|Radeon|Processor|Graphics|Gold|Silver)\b", "", name, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_mark(marks: dict[str, tuple[int, str]], chip: str, vram_gb: int | None) -> tuple[int, str] | None:
    """PassMark entry for a chip. PassMark splits some GPUs by memory ("GeForce RTX 3050 8GB"):
    the entry with the card's VRAM is used, otherwise the slowest desktop variant."""
    table = {_bench_key(n): v for n, v in marks.items() if "laptop" not in n.lower() and "mobile" not in n.lower()}
    key = _bench_key(chip)
    if key in table:
        return table[key]
    if vram_gb and f"{key}{vram_gb}gb" in table:
        return table[f"{key}{vram_gb}gb"]
    variants = [v for k, v in table.items() if re.fullmatch(rf"{re.escape(key)}\d+gb", k)]
    return min(variants) if variants else None


def benchmark_scores(products: list[Product], category: Category, marks: dict[str, tuple[int, str]], source: str) -> list[str]:
    """perf_score = PassMark mark / best mark in the catalog x 100. Returns chips not found."""
    found, missing = {}, []
    for p in products:
        if p.category != category or not p.chip:
            continue
        hit = find_mark(marks, p.chip, p.fields.get("vram_gb"))
        if hit is None:
            missing.append(p.chip)
        else:
            found[p.key] = hit[0]
    best = max(found.values(), default=0)
    for p in products:
        if p.key in found and best:
            p.perf_score = round(found[p.key] / best * 100, 1)
            p.perf_source = f"{source}: {found[p.key]} / {best} (best in catalog) x 100"
    return sorted(set(missing))


_GPU_CLEARANCE = re.compile(
    r"(?:gpu|vga|graphics? cards?|video cards?)[^.\n]{0,50}?(?:length|up to|max|support|clearance|long)[^.\n]{0,25}?(\d{3})\s*mm"
    r"|(?:max(?:imum)?\.?\s*)?(?:gpu|vga|graphics? card)\s*(?:length|clearance)\s*[:：]?\s*(?:up to\s*)?(\d{3})\s*mm"
    r"|(?:длина|длиной)?[^.\n]{0,20}?видеокарт[^.\n]{0,40}?(\d{3})\s*мм", re.I)


def gpu_clearance(text: str) -> int | None:
    """'Supports graphics cards up to 380 mm' -> 380, from a manufacturer page's text."""
    for m in _GPU_CLEARANCE.finditer(text):
        mm = int(next(g for g in m.groups() if g))
        if 170 <= mm <= 500:
            return mm
    return None
