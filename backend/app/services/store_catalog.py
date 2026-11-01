"""Read store category listings and product spec tables, for scripts.import_catalog.

Independent of HTTP and the database: every function takes HTML and returns data.
Prices and stock come from store_pages.parse_product_page, like the offer checker.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.db.models import Category
from app.services.store_pages import PageData, PageParseError, parse_product_page

# Category listing pages of each store, paged with ?page=N (allowed by their robots.txt).
# Neocomputer forbids ?page=, so its products come from its product sitemap instead.
LISTINGS: dict[str, dict[Category, list[str]]] = {
    "xstore": {
        Category.CPU: ["https://xstore.md/componente-pc/procesoare"],
        Category.MOTHERBOARD: ["https://xstore.md/componente-pc/placi-de-baza"],
        Category.RAM: ["https://xstore.md/componente-pc/memorii-ram"],
        Category.GPU: ["https://xstore.md/componente-pc/placi-video"],
        Category.STORAGE: ["https://xstore.md/componente-pc/stocare"],
        Category.PSU: ["https://xstore.md/componente-pc/surse"],
        Category.CASE: ["https://xstore.md/componente-pc/carcase"],
        Category.COOLER: ["https://xstore.md/componente-pc/racire"],
    },
    "darwin": {
        Category.CPU: ["https://darwin.md/componente-pc/cpu"],
        Category.MOTHERBOARD: ["https://darwin.md/componente-pc/motherboard"],
        Category.RAM: ["https://darwin.md/componente-pc/ram"],
        Category.GPU: ["https://darwin.md/componente-pc/placi-video"],
        Category.STORAGE: ["https://darwin.md/componente-pc/dispozitive-de-stocare/ssd",
                           "https://darwin.md/componente-pc/dispozitive-de-stocare/hdd"],
        Category.PSU: ["https://darwin.md/componente-pc/power-supply"],
        Category.CASE: ["https://darwin.md/componente-pc/carcase"],
        Category.COOLER: ["https://darwin.md/componente-pc/coolere"],
    },
    "ultra": {
        Category.CPU: ["https://ultra.md/componente-pc/procesoare"],
        Category.MOTHERBOARD: ["https://ultra.md/componente-pc/placi-de-baza"],
        Category.RAM: ["https://ultra.md/componente-pc/memorie-ram"],
        Category.GPU: ["https://ultra.md/componente-pc/placi-video"],
        Category.STORAGE: ["https://ultra.md/componente-pc/unitate-ssd", "https://ultra.md/componente-pc/unitate-hdd"],
        Category.PSU: ["https://ultra.md/componente-pc/surse-de-alimentare"],
        Category.CASE: ["https://ultra.md/componente-pc/carcase-pc"],
        Category.COOLER: ["https://ultra.md/componente-pc/coolere-procesor"],
    },
    "primepc": {
        Category.CPU: ["https://prime-pc.md/catalog/protsessory-amd", "https://prime-pc.md/catalog/protsessory-intel"],
        Category.MOTHERBOARD: ["https://prime-pc.md/catalog/materinskie-platy-pod-amd",
                               "https://prime-pc.md/catalog/materinskie-platy-pod-intel"],
        Category.RAM: ["https://prime-pc.md/catalog/operativnaya-pamyat"],
        Category.GPU: ["https://prime-pc.md/catalog/videokarty"],
        Category.STORAGE: ["https://prime-pc.md/catalog/ssd", "https://prime-pc.md/catalog/vnutrennie-hdd"],
        Category.PSU: ["https://prime-pc.md/catalog/bloki-pitaniya"],
        Category.CASE: ["https://prime-pc.md/catalog/korpusa"],
        Category.COOLER: ["https://prime-pc.md/catalog/kulery-dlya-protsessora", "https://prime-pc.md/catalog/sistemy-ohlazhdeniya"],
    },
}

# Product links inside the listing's product cards (not "related" or menu links).
_CARD_LINKS = {
    "xstore": ".card-product a[href]",
    "darwin": ".product-card a[href$='.html']",
    "ultra": ".product-card a[href*='/product/']",
    "primepc": ".catalog_tab .product > a[href*='products/']",
}

# Neocomputer sitemap slugs that may be PC components; the breadcrumb decides.
NEOCOMPUTER_SITEMAP = "https://neocomputer.md/sitemap-products.xml"
_NEO_SLUG = re.compile(
    r"(?:^|-)(?:procesor|cpu|placa-de-baza|placa-baza|memorie|ddr4|ddr5|placa-video|geforce|radeon|rtx|ssd|nvme|hdd"
    r"|sursa|psu|power-supply|carcasa|case|cooler|racire|aio)(?:-|$)", re.I)
_NEO_SKIP = re.compile(
    r"laptop|notebook|sodimm|so-dimm|extern|portabil|usb|ups|monitor|cartridge|rivacase|caselogic|datatraveler"
    r"|synology|server|xeon|hot-plug|tx\d00|dvd|cd-rw|card-reader|adapter", re.I)
# Neocomputer breadcrumb (last category level) -> our category.
NEOCOMPUTER_CATEGORIES = {
    "procesoare": Category.CPU, "placi de baza": Category.MOTHERBOARD, "memorii ram": Category.RAM,
    "placi video": Category.GPU, "storage ssd": Category.STORAGE, "storage hdd": Category.STORAGE,
    "ssd": Category.STORAGE, "hdd": Category.STORAGE, "surse de alimentare": Category.PSU,
    "carcase": Category.CASE, "cooler procesoare": Category.COOLER,
}


def page_url(listing: str, page: int) -> str:
    return listing if page == 1 else f"{listing}?page={page}"


def listing_products(store: str, html: str, base: str) -> list[str]:
    """Absolute product URLs on one listing page, in page order, without duplicates."""
    soup = BeautifulSoup(html, "html.parser")
    urls = [urljoin(base, a["href"]).split("#")[0].split("?")[0] for a in soup.select(_CARD_LINKS[store])]
    return list(dict.fromkeys(u for u in urls if u.startswith(("https://", "http://"))))


def neocomputer_candidates(sitemap_xml: str) -> list[str]:
    """Romanian product pages whose slug looks like a PC component (/ru/ pages are the same products)."""
    urls = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap_xml)
    return [u for u in urls if "/ru/" not in u
            and _NEO_SLUG.search(u.rsplit("/", 1)[-1]) and not _NEO_SKIP.search(u.rsplit("/", 1)[-1])]


@dataclass
class ProductPage:
    title: str
    breadcrumb: list[str]
    specs: dict[str, str] = field(default_factory=dict)  # label -> value, as shown by the store
    offer: PageData | None = None  # None when price/stock couldn't be read


def _text(element) -> str:
    return re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()


def _pairs(soup: BeautifulSoup, store: str) -> list[tuple[str, str]]:
    if store == "xstore":
        return [(_text(r.select_one(".char-label")), _text(r.select_one(".char-value")))
                for r in soup.select(".char-row") if r.select_one(".char-label") and r.select_one(".char-value")]
    if store == "darwin":
        rows = [r.find_all("td") for r in soup.select("table tr")]
        return [(_text(r[0]), _text(r[1])) for r in rows if len(r) == 2]
    if store == "ultra":
        # The full table ("spec-card" rows); the short summary above it repeats some rows.
        out = []
        for row in soup.select(".spec-card__row"):
            key = row.select_one("[class*=spec-card__key]")
            value = row.select_one("[class*=spec-card__value]")
            if key is None:
                continue
            if value is None:
                parts = [s for s in row.find_all(recursive=False) if s is not key and _text(s)]
                value = parts[-1] if parts else None
            if value is not None:
                out.append((_text(key), _text(value)))
        return out
    if store == "primepc":
        return [(_text(c[0]), _text(c[1])) for c in
                (r.select(".table_cell") for r in soup.select(".table_char .table_row")) if len(c) >= 2]
    if store == "neocomputer":
        return [(_text(s.select_one(".spec__name")), _text(s.select_one(".spec__value")))
                for s in soup.select("#specs li.spec") if s.select_one(".spec__name") and s.select_one(".spec__value")]
    raise PageParseError(f"No spec parser for store {store!r}")


def _breadcrumb(soup: BeautifulSoup) -> list[str]:
    for selector in ["ol.breadcrumb li", ".breadcrumb li", ".breadcrumbs li", "[class*=breadcrumb] a", "nav[aria-label*=read] a"]:
        items = [_text(x) for x in soup.select(selector) if _text(x)]
        if items:
            return items
    return []


def parse_product(store: str, html: str) -> ProductPage:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = _text(h1) if h1 else (soup.title.get_text(strip=True) if soup.title else "")
    specs: dict[str, str] = {}
    for label, value in _pairs(soup, store):
        label = label.rstrip(":").strip()
        if label and value and label not in specs:
            specs[label] = value
    try:
        offer = parse_product_page(store, html)
    except PageParseError:
        offer = None
    return ProductPage(title=title, breadcrumb=_breadcrumb(soup), specs=specs, offer=offer)
