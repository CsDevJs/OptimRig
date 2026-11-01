"""Turn a store's product page (title + spec table) into our typed specs.

Independent of HTTP and the database. Each store names its specs differently and in
Romanian or Russian, so a field is found by label keywords and then by the title.
A value that can't be read is left out; scripts.catalog_load fills it from another
store's page for the same product or from the chip's data, or reports it missing.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from app.db.models import Category


def plain(text: str) -> str:
    """Lowercase without Romanian diacritics: 'Frecvența' -> 'frecventa'. Cyrillic is kept as is
    (stripping its marks would turn 'й' into 'и')."""
    out = []
    for ch in text.lower().replace("ё", "е"):
        if "Ѐ" <= ch <= "ӿ":
            out.append(ch)
        else:
            out.append("".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)))
    return "".join(out).strip()


def _num(text: str | None) -> float | None:
    """First number: '3 600 MHz' -> 3600, '4.7 GHz' -> 4.7, '30,5 cm' -> 30.5."""
    if not text:
        return None
    m = re.search(r"\d[\d  ]*(?:[.,]\d+)?", text)
    if not m:
        return None
    raw = re.sub(r"[\s  ]", "", m.group())
    # "3 600" is a thousands group; "30,5" is a decimal comma.
    return float(raw.replace(",", "."))


def _int(text: str | None) -> int | None:
    n = _num(text)
    return None if n is None else int(round(n))


YES = ("da", "yes", "есть", "да", "+", "true")
NO = ("nu", "no", "нет", "fara", "без", "-", "false")


def _bool(text: str | None) -> bool | None:
    if text is None:
        return None
    t = plain(text)
    if t.startswith(NO) or "fara" in t or "без" in t or "not " in t or t.startswith("non"):
        return False
    if t.startswith(YES) or t:
        return True
    return None


@dataclass
class Specs:
    """What one page says about a product. `fields` uses our spec column names."""
    category: Category
    brand: str | None
    model: str  # human-readable name for components.model
    key: str  # identity used to match the same product across stores
    fields: dict = field(default_factory=dict)
    power_w: int | None = None  # peak draw for components.power_draw_w, when the page says it
    chip: str | None = None  # CPU model / GPU chipset, for benchmarks and chip-level fallbacks
    skip: str | None = None  # why this isn't a desktop PC part of the category (laptop RAM, fan, ...)
    maker_url: str | None = None  # the manufacturer's product page, when the store links it


class Labels:
    """Spec table lookup by keywords in the (plain) label."""

    def __init__(self, specs: dict[str, str]):
        self.items = [(plain(k), v.strip()) for k, v in specs.items()]

    def get(self, *keywords: str, exclude: tuple[str, ...] = ()) -> str | None:
        for words in keywords:
            parts = words.split("&")
            for label, value in self.items:
                if all(p in label for p in parts) and not any(x in label for x in exclude):
                    return value
        return None


BRANDS = [
    "AMD", "Intel", "ASUS", "ASRock", "Gigabyte", "MSI", "Biostar", "NZXT", "Kingston", "Corsair", "G.Skill", "GOODRAM",
    "Patriot", "Crucial", "Micron", "Samsung", "Western Digital", "WD", "Seagate", "Toshiba", "Transcend", "Apacer",
    "ADATA", "XPG", "Team", "TeamGroup", "Lexar", "Netac", "Hikvision", "Silicon Power", "Verbatim", "PNY", "Sapphire",
    "PowerColor", "XFX", "Palit", "Gainward", "Zotac", "Inno3D", "Colorful", "KFA2", "Galax", "be quiet!", "Seasonic",
    "Chieftec", "Cougar", "DeepCool", "Thermaltake", "Cooler Master", "FSP", "Gamemax", "Zalman", "Aerocool", "Fractal Design",
    "Lian Li", "Phanteks", "Montech", "Arctic", "Noctua", "ID-Cooling", "Thermalright", "Scythe", "Sohoo", "Spire",
    "Segotep", "1stPlayer", "Darkflash", "Xilence", "Endorfy", "Formula", "Frime", "Gembird", "Sven", "Logic", "Super Flower",
    "Hiksemi", "Kioxia", "SanDisk", "Solidigm", "Dell", "HP", "Lenovo", "Fujitsu", "Supermicro", "Asrock", "Vinga", "Qube",
    "Raijintek", "Jonsbo", "Enermax", "Antec", "SilverStone", "Montech", "Ocypus", "Kolink", "Golden Field", "Xigmatek",
    "KingSpec", "Synology", "HPC", "Spacer", "SK hynix", "Hynix", "Intenso", "Natec", "Sharkoon", "Hitachi", "Indilinx",
]
_BRAND_RE = sorted(BRANDS, key=len, reverse=True)

# Words stores put in front of the product name.
_PREFIX = re.compile(
    r"^(procesor|cpu|placa de baza|placă de bază|placa video|placă video|vga card|video card|memorie ram|memorie|"
    r"memorii ram|ram|ssd|hdd|disc dur|unitate ssd|sursa de alimentare|sursă de alimentare|sursa|sursă|psu|"
    r"carcasa|carcasă|case|cooler procesor|cooler|racire|răcire|sistem de racire|unitate hdd|unitate ssd|"
    r"жесткий диск|процессор|материнская плата|"
    r"видеокарта|оперативная память|блок питания|корпус|кулер|система охлаждения|накопитель)\s+", re.I)


def brand_of(title: str, labels: Labels) -> str | None:
    named = labels.get("brand", "producator", "производитель")
    for b in _BRAND_RE:
        if named and plain(named).startswith(plain(b)):
            return b
    t = plain(title)
    for b in _BRAND_RE:
        if re.search(rf"(^|[\s(]){re.escape(plain(b))}([\s,)]|$)", t):
            return b
    return named.strip() if named else None


def clean_model(title: str, brand: str | None) -> str:
    name = _PREFIX.sub("", title.strip())
    name = _PREFIX.sub("", name)
    if brand:
        name = re.sub(rf"^{re.escape(brand)}\s+", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip(" ,-")[:200]


def _mpn(labels: Labels, title: str) -> str | None:
    """Manufacturer part number, when the page states one."""
    value = labels.get("articol", "cod model", "part number", "код производителя", "артикул")
    if value and re.search(r"\d", value) and re.search(r"[A-Za-z]", value) and len(value) >= 5:
        return value
    # PrimePC puts it in the full name: "SSD 500GB Kingston NV3 SNV3S/500G (M.2 ...)".
    full = labels.get("полное название")
    for text in (full, title):
        if not text:
            continue
        for token in re.findall(r"\b[A-Z0-9][A-Z0-9\-/.]{6,}[A-Z0-9]\b", text):
            if re.search(r"\d", token) and re.search(r"[A-Z]", token) and not re.fullmatch(r"(DDR\d|PC\d-?\d+|\d+(GB|TB|MHZ|W))", token):
                return token
    return None


def _key(category: Category, *parts: str | None) -> str:
    text = " ".join(p for p in parts if p)
    return f"{category.value}:" + re.sub(r"[^a-z0-9]+", "", plain(text))


# ---------- CPU ----------

_CPU_MODEL = re.compile(
    r"(ryzen\s*(?:threadripper\s*)?(?:\d\s*)?(?:pro\s*)?\d{4}[a-z0-9]*(?:\s*x3d)?|"
    r"athlon\s*(?:gold\s*|silver\s*)?\w*\d{3,4}\w*|"
    r"core\s*ultra\s*\d\s*\d{3}[a-z]*(?:\s*plus)?|core\s*i\d[\s-]*\d{4,5}[a-z]*|"
    r"pentium\s*(?:gold\s*)?g?\d{4}\w*|celeron\s*g?\d{4}\w*|core\s*\d\s*\d{3}[a-z]*)", re.I)


def cpu_chip(title: str) -> str | None:
    """'procesor amd ryzen 7 9800x3d tray' -> 'Ryzen 7 9800X3D'; 'Core Ultra 5 250KF Plus'."""
    m = _CPU_MODEL.search(title)
    if not m:
        return None
    words = re.sub(r"\s+", " ", m.group(1)).strip().split(" ")
    out = []
    for w in words:
        low = w.lower()
        if low in ("ryzen", "threadripper", "athlon", "core", "ultra", "pentium", "celeron", "gold", "silver", "plus"):
            out.append(low.title())
        elif low == "pro":
            out.append("PRO")
        elif re.fullmatch(r"i\d(-\d+\w*)?", low):
            out.append("i" + w[1:].upper())
        else:
            out.append(w.upper())
    chip = " ".join(out)
    return re.sub(r"(Core i\d)[\s-]*(\d)", r"\1-\2", chip)


def socket_name(text: str | None) -> str | None:
    if not text:
        return None
    t = plain(text).replace(" ", "")
    for s in ("am5", "am4", "am3"):
        if s in t:
            return s.upper()
    m = re.search(r"(?:lga|s|socket)?(1851|1700|1200|1151|1150|1155|2066|4677|3647)", t)
    return f"LGA{m.group(1)}" if m else None


def _memory_types(text: str | None) -> list[str]:
    if not text:
        return []
    t = text.upper()
    return [m for m in ("DDR4", "DDR5") if m in t]


def cpu(title: str, labels: Labels) -> dict:
    f = {}
    f["socket"] = socket_name(labels.get("socket", "сокет") or title)
    f["cores"] = _int(labels.get("nuclee", "ядер", "cores", exclude=("grafic",)))
    f["threads"] = _int(labels.get("thread", "поток", "fire de executie"))
    f["base_clock_ghz"] = _num(labels.get("frecventa de baza", "frecventa baza", "frecventa procesor", "базовая частота",
                                          exclude=("grafic", "memorie", "magistral")))
    f["boost_clock_ghz"] = _num(labels.get("turbo", "maximala", "максимальная частота", "frecventa maxima",
                                           exclude=("grafic", "memorie")))
    for k in ("base_clock_ghz", "boost_clock_ghz"):
        if f[k] and f[k] > 100:  # "3900 MHz"
            f[k] = f[k] / 1000
    f["tdp_w"] = _int(labels.get("tdp", "puterea", "degajarea de caldura"))
    graphics = labels.get("grafica integrata", "placa video integrata", "интегрированная графика", "procesor grafic",
                          "grafic integrat")
    f["integrated_graphics"] = None if graphics is None else not plain(graphics).startswith(("nu", "fara", "нет", "no"))
    f["memory_types"] = _memory_types(labels.get("tip memorie", "tipul de memorie", "tip ram", "memorie suportat", "тип памяти"))
    cooler = labels.get("cooler", "set sistem de racire", "кулер", "система охлаждения")
    package = plain(labels.get("ambalaj", "упаковк") or title)
    if cooler is not None:
        f["includes_cooler"] = not plain(cooler).startswith(("nu", "fara", "нет", "no"))
    elif "tray" in package or "oem" in package or "mpk" in package:
        f["includes_cooler"] = False
    return {k: v for k, v in f.items() if v not in (None, [])}


# ---------- Motherboard ----------

def board_form_factor(text: str | None) -> str | None:
    if not text:
        return None
    t = plain(text).replace("-", " ").replace("_", " ")
    if "e atx" in t or "eatx" in t or "extended" in t:
        return "E-ATX"
    if "mini itx" in t or "mini-itx" in t or "itx" in t:
        return "Mini-ITX"
    if "micro" in t or "matx" in t or "m atx" in t or "uatx" in t or "μatx" in t:
        return "Micro-ATX"
    if "atx" in t:
        return "ATX"
    return None


_CHIPSET = re.compile(r"\b([ABHXZW]\d{3}[A-Z]?|TRX\d{2}|X\d{3}E)\b")


def motherboard(title: str, labels: Labels) -> dict:
    f = {}
    memory = plain(" ".join(filter(None, [labels.get("tip memorie", "tip ram", "поддержка памяти"), title])))
    if re.search(r"ddr3|ddr2", memory) and not re.search(r"ddr4|ddr5", memory):
        return {"_skip": "DDR3 or older platform"}
    f["socket"] = socket_name(labels.get("socket", "сокет") or title)
    chipset = labels.get("chipset", "чипсет", exclude=("audio", "аудио", "retea"))
    m = _CHIPSET.search((chipset or "") + " " + title.upper())
    f["chipset"] = m.group(1) if m else None
    f["form_factor"] = board_form_factor(labels.get("form factor placa", "factor de forma a placii", "form factor",
                                                    "формфактор", "форм-фактор", exclude=("memorie", "m.2")) or title)
    mem = _memory_types(labels.get("tip memorie", "tip ram", "поддержка памяти", "form-factor memorie", "standard memorie")
                        or title)
    f["memory_type"] = mem[0] if len(mem) == 1 else None
    f["memory_slots"] = _int(labels.get("sloturi memorie", "numar sloturi ram", "sloturi ram", "количество планок",
                                        "слотов памяти", "sloturi memorie operativa"))
    f["max_memory_gb"] = _int(labels.get("capacitatea maxima", "capacitate max", "memorie maxima", "максимальный объем",
                                         "dimensiune maxima ram"))
    f["m2_slots"] = _int(labels.get("numarul de sloturi m.2", "sloturi de expansiune m.2", "разъемов m.2", "m.2",
                                    exclude=("form factor", "suport slot", "#")))
    if f["m2_slots"] is None:  # Ultra: one "Suport slot M2 # n" row per slot
        rows = [label for label, _ in labels.items if re.search(r"slot m\.?2\s*#\s*\d", label)]
        f["m2_slots"] = len(rows) or None
    f["sata_ports"] = _int(labels.get("conectori sata", "разъемов sata", "porturi sata", "sata"))
    wifi = labels.get("wi-fi", "wifi", "controler wi-fi")
    f["wifi"] = _bool(wifi) if wifi is not None else ("wifi" in plain(title).replace("-", "") or "wi-fi" in plain(title))
    return {k: v for k, v in f.items() if v is not None}


# ---------- RAM ----------

def ram(title: str, labels: Labels) -> tuple[dict, str | None]:
    use = plain(" ".join(filter(None, [labels.get("destinatie", "aplicare", "вид", "compatibilitate platforma", "segment"),
                                      labels.get("form factor", "format", "module de form", "тип оперативной"), title])))
    if any(w in use for w in ("laptop", "ноутбук", "so-dimm", "sodimm", "so dimm", "260-pin", "262-pin")):
        return {}, "laptop memory"
    if any(w in use for w in ("ecc registered", "rdimm", "registered", "server")):
        return {}, "server memory"
    if re.search(r"ddr3|ddr2", use):
        return {}, "DDR3 or older memory"
    f = {}
    mem = _memory_types(labels.get("tip memorie", "tip ram", "standard memorie", "тип оперативной памяти", "tip") or title)
    f["memory_type"] = mem[0] if mem else None
    f["capacity_gb"] = _int(labels.get("capacitatea totala", "capacitate totala", "capacitatea memoriei", "объем оперативной"))
    kit = labels.get("numarul de placi", "kit", "ambalaj /set", "количество планок", "numarul de placi in set")
    m = re.search(r"(\d)\s*[x×х]\s*(\d+)", kit or "") or re.search(r"(\d)\s*[x×х]\s*(\d+)\s*gb", title, re.I)
    if m:
        f["modules"] = int(m.group(1))
        f.setdefault("capacity_gb", int(m.group(1)) * int(m.group(2)))
        if not f.get("capacity_gb"):
            f["capacity_gb"] = int(m.group(1)) * int(m.group(2))
    else:
        f["modules"] = _int(kit)
    if not f.get("capacity_gb"):
        m = re.search(r"(\d+)\s*gb", title, re.I)
        f["capacity_gb"] = int(m.group(1)) if m else None
    f["speed_mts"] = _int(labels.get("frecventa", "частота памяти", "frecventa memorie", exclude=("oc",)))
    if not f["speed_mts"]:
        m = re.search(r"(?:ddr\d[- ]?)(\d{4})", title, re.I)
        f["speed_mts"] = int(m.group(1)) if m else None
    if not f.get("memory_type") and f.get("speed_mts") and f["speed_mts"] <= 1866:
        return {}, "DDR3 or older memory"
    f["cas_latency"] = _int(labels.get("cas", "latenta", "латентность", "sincronizare", "timing"))
    if not f["cas_latency"]:
        m = re.search(r"\bCL\s?(\d{2})\b", title, re.I)
        f["cas_latency"] = int(m.group(1)) if m else None
    return {k: v for k, v in f.items() if v is not None}, None


# ---------- GPU ----------

_GPU_CHIP = re.compile(
    r"((?:geforce\s*)?(?:rtx|gtx|gt)\s*\d{3,4}\s*(?:ti\s*super|ti|super)?|(?:radeon\s*)?rx\s*\d{3,4}\s*(?:xtx|xt|gre)?|"
    r"(?:intel\s*)?arc\s*[ab]\d{3})", re.I)


_GIGABYTE_CODE = re.compile(r"(?<![A-Z0-9])GV-([NR])(\d{3})(\d?)(XT|T|S)?", re.I)


def gpu_chip(text: str) -> str | None:
    code = _GIGABYTE_CODE.search(text)  # GV-N507TWF3OC -> RTX 5070 Ti, GV-R9070XT -> RX 9070 XT
    if code and not _GPU_CHIP.search(text):
        vendor, digits, last, tail = code.group(1).upper(), code.group(2), code.group(3), (code.group(4) or "").upper()
        number = digits + (last or "0")
        suffix = {"T": " Ti", "S": " Super", "XT": " XT"}.get(tail, "")
        text = f"{'RTX' if vendor == 'N' else 'RX'} {number}{suffix}"
    m = _GPU_CHIP.search(text)
    if not m:
        return None
    c = re.sub(r"\s+", " ", m.group(1).upper()).strip()
    c = re.sub(r"^(GEFORCE |RADEON |INTEL )", "", c)
    c = re.sub(r"(RTX|GTX|GT|RX)\s*(\d)", r"\1 \2", c)
    c = re.sub(r"(\d)(TI|SUPER|XTX|XT|GRE)", r"\1 \2", c)
    c = c.replace(" TI", " Ti").replace(" SUPER", " Super")
    if c.startswith(("RTX", "GTX", "GT ")):
        return f"GeForce {c}"
    if c.startswith("RX"):
        return f"Radeon {c}"
    if c.startswith("ARC"):
        return f"Arc {c[3:].strip()}"
    return c


def _dims(text: str | None) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", text or "")]


def gpu(title: str, labels: Labels) -> dict:
    f = {}
    f["chipset"] = gpu_chip(" ".join(filter(None, [labels.get("procesor video", "графический чип", "chipset video", "gpu", "model"), title])))
    f["vram_gb"] = _int(labels.get("memorie video", "объем видеопамяти", "capacitate memorie", "memoria video",
                                   exclude=("tip", "frecvent", "bus", "latime")))
    if not f["vram_gb"]:
        m = re.search(r"(\d{1,2})\s*G(?:B|D)?\b", title, re.I)
        f["vram_gb"] = int(m.group(1)) if m else None
    length = labels.get("lungime", "length", "длина")
    if length:
        n = _num(length)
        f["length_mm"] = int(round(n * 10)) if n and n < 60 else _int(length)
    dims = _dims(labels.get("размеры", "dimensiuni", "dimensions"))
    if not f.get("length_mm") and len(dims) >= 2:
        f["length_mm"] = int(round(max(dims) * (10 if max(dims) < 60 else 1)))
    thick = labels.get("inaltime", "grosime", "latime slot", "sloturi ocupate", "slot")
    if thick and "slot" in plain(" ".join(k for k, _ in labels.items if "slot" in k)):
        f["slot_width"] = _num(thick)
    elif len(dims) >= 3:
        mm = min(dims) * (10 if min(dims) < 10 else 1)
        f["slot_width"] = round(mm / 20.32 * 2) / 2
    elif thick:
        n = _num(thick)
        if n:
            mm = n * 10 if n < 10 else n
            f["slot_width"] = round(mm / 20.32 * 2) / 2
    f["tdp_w"] = _int(labels.get("tdp", "consum", "энергопотребление", "putere consumata", exclude=("sursa", "psu", "recomand")))
    f["recommended_psu_w"] = _int(labels.get("psu recomandata", "sursa recomandata", "минимальная мощность бп",
                                             "puterea sursei", "recommended"))
    connectors = labels.get("tip conectare", "conector alimentare", "разъем питания", "alimentare suplimentara", "power connector")
    if connectors and re.search(r"pin", connectors, re.I):
        f["power_connectors"] = re.sub(r"\s+", " ", connectors)[:40]
    return {k: v for k, v in f.items() if v is not None}


# ---------- Storage ----------

def storage(title: str, labels: Labels) -> tuple[dict, str | None]:
    form = labels.get("form factor", "формфактор", "format", "форм-фактор")
    iface = labels.get("interfata", "интерфейс", "interface", exclude=("grafic",))
    text = plain(" ".join(filter(None, [form, iface, title])))
    if any(w in text for w in ("extern", "usb", "microsd", "card", "portabil", "msata")):
        return {}, "external or card storage"
    if re.search(r"\bsas\b|savvio", text):
        return {}, "SAS server drive (no SAS port on desktop boards)"
    f = {}
    if any(w in text for w in ("hdd", "rpm", "об/мин", "3.5\"", "3,5", "жесткий диск", "hard disk", "disc dur")) and "ssd" not in text:
        f["storage_type"], f["form_factor"], f["interface"] = "hdd", "3.5" if "2.5" not in text else "2.5", "SATA III"
    elif "nvme" in text or "pcie" in text or "pci-e" in text or "pci express" in text:
        f["storage_type"], f["form_factor"] = "nvme", "M.2 2280"
        m = re.search(r"(?:pcie|pci-e|pci express|gen)\s*(\d)(?:\.\d)?", text)
        f["interface"] = f"PCIe {m.group(1)}.0 x4" if m else "PCIe x4"
    elif "m.2" in text and "sata" in text:
        f["storage_type"], f["form_factor"], f["interface"] = "sata_ssd", "M.2 2280", "SATA III"
    elif "ssd" in text or "sata" in text:
        f["storage_type"], f["form_factor"], f["interface"] = "sata_ssd", "2.5", "SATA III"
    capacity = labels.get("capacitate", "объем ssd", "объем hdd", "capacitatea totala", "capacitate stocare")
    n = _num(capacity)
    if n and capacity and re.search(r"tb|тб", capacity, re.I):
        n *= 1000
    if not n:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(tb|gb|тб|гб)", title, re.I)
        if m:
            n = float(m.group(1).replace(",", ".")) * (1000 if m.group(2).lower() in ("tb", "тб") else 1)
    f["capacity_gb"] = int(round(n)) if n else None
    f["read_mbps"] = _int(labels.get("citire", "чтения", "read", exclude=("aleator", "random", "4k", "4 kb")))
    f["write_mbps"] = _int(labels.get("scriere", "записи", "write", exclude=("aleator", "random", "4k", "4 kb", "rescriere")))
    return {k: v for k, v in f.items() if v is not None}, None


# ---------- PSU ----------

def psu(title: str, labels: Labels) -> tuple[dict, str | None]:
    t = plain(title)
    if any(w in t for w in ("adapter", "adaptor", "laptop", "notebook", "ups", "server", "hot-plug", "hot plug")):
        return {}, "not an ATX/SFX PC power supply"
    f = {}
    f["wattage"] = _int(labels.get("putere", "мощность бп", "мощность", "wattage", exclude=("consum",)))
    if not f["wattage"]:
        m = re.search(r"(\d{3,4})\s*w\b", title, re.I)
        f["wattage"] = int(m.group(1)) if m else None
    eff = labels.get("certificat", "сертификат", "eficienta", "80 plus", "80+") or title
    m = re.search(r"(?:80\s*\+|80\s*plus)\s*(titanium|platinum|gold|silver|bronze|white|standard)?", eff, re.I)
    f["efficiency"] = (f"80+ {m.group(1).title()}" if m and m.group(1) else "80+") if m else None
    mod = plain(labels.get("modular", "модульн", "cabluri detasabile") or "")
    if "semi" in mod or "полу" in mod:
        f["modular"] = "semi"
    elif mod.startswith(("da", "full", "есть", "yes", "complet", "modular")):
        f["modular"] = "full"
    elif mod.startswith(("nu", "нет", "no", "non")):
        f["modular"] = "none"
    elif re.search(r"semi[- ]?modular", t):
        f["modular"] = "semi"
    elif re.search(r"(full[- ]?)?modular", t) and "non" not in t:
        f["modular"] = "full"
    form = plain(labels.get("form factor", "форм-фактор", "formfactor", "standard") or title)
    if "tfx" in form or "flex" in form:
        return {}, "TFX/Flex power supply"
    f["form_factor"] = "SFX" if "sfx" in form else "ATX"
    ports = plain(" ".join(filter(None, [labels.get("порты", "conector", "cabluri", "12vhpwr", "16-pin", "16 pin"), title])))
    f["has_16pin"] = bool(re.search(r"16[- ]?pin|12vhpwr|12v-2x6|12v 2x6|atx\s*3", ports))
    return {k: v for k, v in f.items() if v is not None}, None


# ---------- Case ----------

def _mm(text: str | None, cm_below: float) -> int | None:
    """'42 cm' / '17.5 cm' / '320' / '170 мм' -> mm; numbers below `cm_below` are centimetres."""
    n = _num(text)
    if n is None:
        return None
    if re.search(r"\bcm\b|см", text or "", re.I) or n < cm_below:
        n *= 10
    return int(round(n))


def case(title: str, labels: Labels) -> dict:
    f = {}
    boards = plain(" ".join(filter(None, [
        labels.get("compatibilitate form factor placa", "factor de forma a placii", "placii de baza", "placa de baza",
                   "dimensiune maxima placa", "форм-фактор", "form factor", exclude=("psu", "sursa", "carcasa")), title])))
    boards = boards.replace("μatx", "matx")
    ffs = set()
    if re.search(r"e-?atx|extended", boards):
        ffs.add("E-ATX")
    if re.search(r"micro|m-?atx|uatx", boards):
        ffs.add("Micro-ATX")
    if "itx" in boards:
        ffs.add("Mini-ITX")
    if re.search(r"(?<![a-z-])atx", re.sub(r"e-?atx|micro[- ]?atx|m-?atx|mini[- ]?itx", " ", boards)):
        ffs.add("ATX")
    # A case for a board size takes the smaller sizes too (ATX -> Micro-ATX, Mini-ITX).
    order = ["E-ATX", "ATX", "Micro-ATX", "Mini-ITX"]
    if ffs:
        f["supported_board_form_factors"] = order[min(order.index(x) for x in ffs):]
    f["max_gpu_length_mm"] = _mm(labels.get("placii video", "placa video", "видеокарт", "gpu", "lungime maxima"), 60)
    f["max_cooler_height_mm"] = _mm(labels.get("coolerului", "cooler-ului", "кулера", "racitor"), 30)
    rad = labels.get("radiator", "радиатор", "racire lichida", "racire cu lichid", "жидкост")
    sizes = [int(x) for x in re.findall(r"(120|140|240|280|360|420)", rad or "")]
    if sizes:
        f["max_radiator_mm"] = max(sizes)
    psu_ff = plain(labels.get("form factor psu", "compatibilitate form factor psu", "standard sursa") or "")
    f["psu_form_factor"] = "SFX" if "sfx" in psu_ff and "atx" not in psu_ff else "ATX"
    fans = labels.get("ventilatoare incluse", "total ventilatoare preinstalate", "количество вентиляторов в комплекте",
                      "ventilatoare preinstalate", "ventilatoare in set", "numarul de ventilatoare")
    if fans is not None:
        f["included_fans"] = _int(fans) if re.search(r"\d", fans) else 0
    with_psu = labels.get("sursa de alimentare integrata", "блок питания", "sursa inclusa")
    if (with_psu and _bool(with_psu)) or labels.get("мощность бп"):
        return {"_skip": "case with a power supply"}
    if re.search(r"\bcu sursa\b|with psu|\bpsu\s*\d{3}\s*w|\d{3}\s*w\b", plain(title)) and not re.search(r"w/o|fara psu|без бп|fără", plain(title)):
        return {"_skip": "case with a power supply"}
    return {k: v for k, v in f.items() if v is not None}


# ---------- Cooler ----------

_SOCKETS = ("AM5", "AM4", "LGA1851", "LGA1700", "LGA1200", "LGA1151", "LGA1150", "LGA1155")


def cooler(title: str, labels: Labels) -> tuple[dict, str | None]:
    kind = plain(" ".join(filter(None, [labels.get("tip cooler", "tip racire", "sistem de racire", "tip", "тип"),
                                        labels.get("назначение", "destinatie"), title])))
    if any(w in kind for w in ("ventilator carcasa", "case fan", "pasta", "thermal", "термопаст", "вентилятор для корпуса",
                               "fan hub", "controller", "kit de montare", "kit montaj", "bracket", "laptop", "ноутбук",
                               "chipset", "ssd", "m.2", "ram", "vga", "video", "ventilator pentru carcasa")):
        return {}, "not a CPU cooler"
    f = {}
    aio = any(w in kind for w in ("lichid", "liquid", "aio", "жидкост", "water", "cu apa", "водян"))
    f["cooler_type"] = "aio" if aio else "air"
    found = set()
    # Xstore lists one row per socket ("AMD AM4": "Da").
    for label, value in labels.items:
        sock = socket_name(label) if re.search(r"am\d|lga|socket", label) else None
        if sock and _bool(value):
            found.add(sock)
    text = plain(" ".join(filter(None, [labels.get("socket", "сокет", "compatibilitate"), title]))).replace(" ", "")
    for s_ in _SOCKETS:
        if s_.lower().replace("lga", "") in text.replace("lga", ""):
            found.add(s_)
    if "115x" in text:
        found.update({"LGA1150", "LGA1151", "LGA1155"})
    f["supported_sockets"] = sorted(found & set(_SOCKETS)) or None
    if aio:
        m = re.search(r"\b(120|140|240|280|360|420)\b", " ".join(filter(None, [labels.get("radiator", "радиатор"), title])))
        if not m:
            dims = _dims(labels.get("размеры", "dimensiuni radiator", "lungime"))
            long = max(dims) if dims else 0
            long = long * 10 if long < 60 else long
            m_size = next((s_ for s_ in (420, 360, 280, 240, 140, 120) if long >= s_ + 15), None)
            f["radiator_mm"] = m_size
        else:
            f["radiator_mm"] = int(m.group(1))
    else:
        f["height_mm"] = _mm(labels.get("inaltimea racitorului", "inaltime cooler", "высота", "inaltime", "height"), 30)
        if not f["height_mm"] or f["height_mm"] < 30:
            dims = _dims(labels.get("размеры", "dimensiuni"))
            f["height_mm"] = int(max(dims)) if dims and 30 <= max(dims) < 200 else None
    f["max_tdp_w"] = _int(labels.get("tdp", "уровень tdp", "putere disipata", "disipare"))
    if not f["supported_sockets"]:
        return {}, "no CPU socket list (case fan or accessory)"
    return {k: v for k, v in f.items() if v is not None}, None


# ---------- Entry point ----------

# Plausible values; anything outside is a misread label and is dropped (a fallback may fill it).
RANGES = {
    "cores": (1, 128), "threads": (1, 256), "base_clock_ghz": (0.5, 7), "boost_clock_ghz": (0.5, 7), "tdp_w": (5, 1000),
    "memory_slots": (1, 8), "max_memory_gb": (4, 2048), "m2_slots": (0, 10), "sata_ports": (0, 16),
    "capacity_gb": (1, 100000), "modules": (1, 8), "speed_mts": (1000, 12000), "cas_latency": (5, 80),
    "vram_gb": (1, 48), "length_mm": (100, 500), "slot_width": (1, 4.5), "recommended_psu_w": (200, 2000),
    "read_mbps": (50, 20000), "write_mbps": (50, 20000), "wattage": (150, 3000),
    "max_gpu_length_mm": (150, 600), "max_cooler_height_mm": (30, 250), "max_radiator_mm": (120, 480),
    "included_fans": (0, 12), "height_mm": (20, 200), "radiator_mm": (120, 480), "max_tdp_w": (20, 500),
}


def _plausible(fields: dict) -> dict:
    out = {}
    for name, value in fields.items():
        bounds = RANGES.get(name)
        if bounds and isinstance(value, (int, float)) and not isinstance(value, bool) and not bounds[0] <= value <= bounds[1]:
            continue
        out[name] = value
    return out


def normalize(category: Category, title: str, specs: dict[str, str]) -> Specs:
    labels = Labels(specs)
    brand = brand_of(title, labels)
    model = clean_model(title, brand)
    mpn = _mpn(labels, title)
    skip, chip, power = None, None, None
    if category == Category.CPU:
        fields = cpu(title, labels)
        chip = cpu_chip(" ".join(filter(None, [labels.get("model", "procesor", "полное название"), title])))
        if chip is None:
            skip = "unknown CPU model"
        elif fields.get("socket") in ("LGA1150", "LGA1155", "AM3") or re.search(r"(?i)i\d-[2-4]\d{3}", chip):
            skip = "DDR3 or older platform"
        package = "tray" if re.search(r"\b(tray|oem|mpk)\b", plain(title + " " + (labels.get("ambalaj", "упаковк") or ""))) else "box"
        key = _key(category, chip, package)
        power = fields.get("tdp_w")
    elif category == Category.MOTHERBOARD:
        fields = motherboard(title, labels)
        skip = fields.pop("_skip", None)
        key = _key(category, mpn or model)
    elif category == Category.RAM:
        fields, skip = ram(title, labels)
        key = _key(category, mpn or model)
    # Some "part numbers" are a series shared by several sizes (Apacer "AS2280P4", Gigabyte
    # "GV-R9060XTGAMING OC" for 8 and 16 GB), so the size is part of the identity.
    elif category == Category.GPU:
        fields = gpu(title, labels)
        chip = fields.get("chipset")
        key = _key(category, mpn or model, f"{fields.get('vram_gb')}gb")
        power = fields.get("tdp_w")
    elif category == Category.STORAGE:
        fields, skip = storage(title, labels)
        # Rounded to 100 GB so "1 TB" (1000) and "1024G" stay one drive.
        size = round(fields["capacity_gb"] / 100) if fields.get("capacity_gb") else None
        key = _key(category, mpn or model, f"{size}x100gb")
    elif category == Category.PSU:
        fields, skip = psu(title, labels)
        key = _key(category, mpn or model, f"{fields.get('wattage')}w")
    elif category == Category.CASE:
        fields = case(title, labels)
        skip = fields.pop("_skip", None)
        key = _key(category, mpn or model)
    else:
        fields, skip = cooler(title, labels)
        key = _key(category, mpn or model)
    fields = _plausible(fields)
    maker = labels.get("на сайте производителя", "site producator", "pagina producatorului")
    maker = maker if maker and maker.startswith(("http://", "https://")) else None
    return Specs(category=category, brand=brand, model=model, key=key, fields=fields, power_w=power, chip=chip,
                 skip=skip, maker_url=maker)
