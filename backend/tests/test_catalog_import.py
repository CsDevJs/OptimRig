import json
import random
import re
from decimal import Decimal

import pytest

from app.db.models import Category, Component, CpuSpec
from app.services.ac3 import filter_catalog, filter_domains
from app.services.catalog_merge import Offer, Product, cpu_facts, gpu_from_chip, merge, merge_conflicts
from app.services.catalog_normalize import _mpn, Labels, cpu_chip, gpu_chip, kingston_part, normalize
from app.services.compatibility import SelectedPart
from app.services.recommend import Candidate, OPTIONAL, _dominates, _strict_fit, pareto, prefilter, signature
from app.services.store_catalog import listing_products, neocomputer_candidates
from scripts.crawl import Robots
from tests.test_topsis import random_catalog

D = Decimal


# ---------- robots.txt ----------

def test_robots_wildcards_and_longest_match():
    rules = Robots("""
User-agent: Googlebot
Disallow: /

User-agent: *
Disallow: /*?p=*
Disallow: /search
Disallow: /*.pdf$
Allow: /search/help
""")
    assert rules.allowed("https://x.md/componente-pc/procesoare?page=2")
    assert not rules.allowed("https://x.md/componente-pc/procesoare?p=2")
    assert not rules.allowed("https://x.md/search?q=ryzen")
    assert rules.allowed("https://x.md/search/help")  # longer Allow wins
    assert not rules.allowed("https://x.md/manual.pdf")
    assert rules.allowed("https://x.md/manual.pdf?download=1")  # $ anchors the end
    assert Robots("").allowed("https://x.md/anything")


# ---------- store pages ----------

def test_listing_links_are_absolute_and_unique():
    html = """<div class="card-product"><a href="/componente-pc/procesoare/ryzen-5">x</a>
              <a href="/componente-pc/procesoare/ryzen-5#reviews">y</a><a href="javascript:void(0)">z</a></div>"""
    assert listing_products("xstore", html, "https://xstore.md/componente-pc/procesoare") == [
        "https://xstore.md/componente-pc/procesoare/ryzen-5"]


def test_neocomputer_sitemap_filter():
    xml = "".join(f"<loc>https://neocomputer.md/{s}</loc>" for s in [
        "procesor-amd-ryzen-7-5800x-box", "ru/procesor-amd-ryzen-7-5800x-box", "rivacase-8803-aqua",
        "128gb-kingston-datatraveler-micro-metal-case", "carcasa-deepcool-cc560", "laptop-asus-x515"])
    assert neocomputer_candidates(xml) == ["https://neocomputer.md/procesor-amd-ryzen-7-5800x-box",
                                           "https://neocomputer.md/carcasa-deepcool-cc560"]


# ---------- normalizing spec tables ----------

def test_cpu_from_romanian_table():
    s = normalize(Category.CPU, "Procesor AMD Ryzen 7 5800X, Box", {
        "Socket procesor": "AM4", "Frecvența de bază": "3.8 GHz", "Frecvență turbo": "4.7 GHz",
        "Numărul de nuclee": "8", "Numărul threads": "16", "Degajarea de căldură (TDP)": "105 W",
        "Grafică integrată in procesor": "Nu", "Tipul de memorie susținut": "2 channel, DDR4 (Up to 3200 MHz)",
        "Cooler procesor": "Nu"})
    assert (s.brand, s.chip, s.skip) == ("AMD", "Ryzen 7 5800X", None)
    assert s.fields == {"socket": "AM4", "cores": 8, "threads": 16, "base_clock_ghz": 3.8, "boost_clock_ghz": 4.7,
                        "tdp_w": 105, "integrated_graphics": False, "memory_types": ["DDR4"], "includes_cooler": False}


def test_box_and_tray_are_different_products():
    box = normalize(Category.CPU, "Procesor AMD Ryzen 5 7600 Box", {})
    tray = normalize(Category.CPU, "Процессор AMD Ryzen 5 7600 Tray", {})
    again = normalize(Category.CPU, "AMD Ryzen 5 7600, Tray", {})
    assert box.key != tray.key and tray.key == again.key
    assert tray.fields["includes_cooler"] is False


def test_motherboard_from_russian_table():
    s = normalize(Category.MOTHERBOARD, "Материнская плата ASUS PRIME B850M-A WIFI", {
        "Тип сокета": "Socket AM5", "Формфактор": "Micro-ATX", "Чипсет": "AMD B850", "Поддержка памяти": "DDR5",
        "Количество планок памяти": "4", "Максимальный объем памяти": "256 ГБ", "Количество разъемов SATA": "4",
        "Количество разъемов M.2": "2"})
    assert s.fields == {"socket": "AM5", "chipset": "B850", "form_factor": "Micro-ATX", "memory_type": "DDR5",
                        "memory_slots": 4, "max_memory_gb": 256, "m2_slots": 2, "sata_ports": 4, "wifi": True}


def test_ram_kit_and_laptop_memory():
    s = normalize(Category.RAM, "Memorie RAM Kingston FURY Beast 32GB", {
        "Standard memorie operativă": "DDR5", "Capacitatea totală a memoriei": "32 GB", "Numărul de plăci în set": "2 x 16 GB",
        "Frecvență memorie": "6 000 MHz", "CAS Latency (CL)": "36", "Articol": "KF560C36BBEK2-32"})
    assert s.fields == {"memory_type": "DDR5", "capacity_gb": 32, "modules": 2, "speed_mts": 6000, "cas_latency": 36}
    assert normalize(Category.RAM, "SODIMM DDR4 8GB Kingston", {"Вид": "Для ноутбука"}).skip == "laptop memory"


def test_gpu_chip_names():
    assert gpu_chip("Видеокарта GIGABYTE GV-N507TWF3OCV2-16GD") == "GeForce RTX 5070 Ti"
    assert gpu_chip("GV-R9070XTGAMING OC-16GD") == "Radeon RX 9070 XT"
    assert gpu_chip("ASUS Dual GeForce RTX 5060 Ti OC") == "GeForce RTX 5060 Ti"
    assert gpu_chip("Sapphire PULSE Radeon RX 9060 XT 16GB") == "Radeon RX 9060 XT"
    assert cpu_chip("Intel Core i5-14400F Box") == "Core i5-14400F"


def test_case_and_cooler_rows():
    case = normalize(Category.CASE, "Carcasă ASUS Prime AP202", {
        "Compatibilitate form factor placă de bază": "mATX, Mini-ITX", "Lungimea max. a plăcii video instalate": "42 cm",
        "Înălțimea maximă a coolerului CPU": "17.5 cm", "Ventilatoare incluse": "3", "Sursa de alimentare integrată": "Nu"})
    assert case.fields == {"supported_board_form_factors": ["Micro-ATX", "Mini-ITX"], "max_gpu_length_mm": 420,
                           "max_cooler_height_mm": 175, "psu_form_factor": "ATX", "included_fans": 3}
    cooler = normalize(Category.COOLER, "Cooler DeepCool AK400", {
        "Tip răcire": "Cu aer", "AMD AM4": "Da", "AMD AM5": "Da", "Intel LGA 1700": "Da", "Intel LGA 1200": "Nu",
        "Înălțime": "15.5 cm", "TDP": "220 W"})
    assert cooler.fields == {"cooler_type": "air", "supported_sockets": ["AM4", "AM5", "LGA1700"], "height_mm": 155,
                             "max_tdp_w": 220}
    assert normalize(Category.COOLER, "Ventilator Arctic P12", {"Tip": "Ventilator carcasa"}).skip


def test_storage_kinds():
    hdd = normalize(Category.STORAGE, "Жесткий диск Western Digital Blue 2TB", {"Объем HDD": "2000 ГБ"})
    assert hdd.fields["storage_type"] == "hdd" and hdd.fields["capacity_gb"] == 2000
    nvme = normalize(Category.STORAGE, "SSD Kingston NV3 1TB", {"Interfață": "PCI-E 4.0 x4", "Form Factor": "M.2 2280"})
    assert (nvme.fields["storage_type"], nvme.fields["interface"], nvme.fields["capacity_gb"]) == ("nvme", "PCIe 4.0 x4", 1000)
    assert normalize(Category.STORAGE, "SSD extern Samsung T9 2TB", {"Form Factor": "SSD Extern"}).skip


# ---------- merging and filling ----------

def _page(store, title, specs, price, category=Category.CPU):
    return normalize(category, title, specs), Offer(store, f"https://{store}/{price}", D(price), None)


def test_merge_joins_stores_keeps_two_pages_of_one_store_apart_and_fills_platform_facts():
    products = merge([
        _page("xstore", "Procesor AMD Ryzen 5 7600 Tray", {"Numărul de nuclee": "6"}, "2500"),
        _page("darwin", "Procesor AMD Ryzen 5 7600 Tray", {"Numărul de nuclee": "6"}, "2400"),
        _page("darwin", "Procesor AMD Ryzen 5 7600, Tray", {}, "2450"),
    ])
    assert len(products) == 2 and not merge_conflicts(products)
    p = next(p for p in products if len(p.offers) == 2)
    assert sorted((o.store, o.price) for o in p.offers) == [("darwin", D("2400")), ("xstore", D("2500"))]
    cpu_facts(p)
    assert (p.fields["socket"], p.fields["memory_types"], p.fields["integrated_graphics"]) == ("AM5", ["DDR5"], True)
    assert "socket" in p.filled and "cores" not in p.filled


def test_gpu_fills_from_other_cards_with_the_same_chip():
    stated = Product(Category.GPU, "a", "ASUS", "A", "GeForce RTX 5060", {"tdp_w": 145, "recommended_psu_w": 550,
                                                                          "slot_width": 2.0, "length_mm": 230}, [])
    other = Product(Category.GPU, "b", "MSI", "B", "GeForce RTX 5060", {"length_mm": 250}, [])
    silent = Product(Category.GPU, "c", "Palit", "C", "GeForce RTX 5060", {}, [])
    gpu_from_chip([stated, other, silent])
    assert silent.fields == {"tdp_w": 145, "recommended_psu_w": 550, "slot_width": 2.0, "length_mm": 250}
    assert other.fields["length_mm"] == 250 and "length_mm" not in other.filled


# ---------- AC-3 on spec groups, pre-filter ----------

def _with_twins(domains, rng):
    """Copy some parts with new ids and prices but the same specs, so signature groups have members."""
    next_id = 1000
    for category, values in domains.items():
        for x in list(values):
            if rng.random() < 0.6:
                c = x.part.component
                twin = Component(id=next_id, category=category, power_draw_w=c.power_draw_w + rng.choice([-5, 0, 5]),
                                 perf_score=c.perf_score)
                values.append(Candidate(SelectedPart(twin, x.part.spec), x.price + rng.choice([-200, 0, 300])))
                next_id += 1
    return domains


def test_filter_catalog_matches_plain_ac3():
    rng = random.Random(11)
    for _ in range(40):
        domains = _with_twins(random_catalog(rng), rng)
        plain = {c: [x.part for x in xs] + ([None] if c in OPTIONAL else []) for c, xs in domains.items()}
        ids = lambda result: {c: sorted((p.component.id if p else 0) for p in ps) for c, ps in result.items()}
        assert ids(filter_catalog(plain)) == ids(filter_domains(plain))


def test_pareto_keeps_a_dominating_twin_for_every_dropped_part():
    rng = random.Random(4)
    for _ in range(30):
        for values in _with_twins(random_catalog(rng), rng).values():
            kept = pareto(values)
            for x in values:
                if x not in kept:
                    assert any(signature(y.part) == signature(x.part) and _dominates(y, x) for y in kept)


def test_prefilter_caps_and_keeps_parts_that_fit_earlier_picks():
    rng = random.Random(9)
    for _ in range(20):
        domains = _with_twins(random_catalog(rng), rng)
        picked = prefilter(domains, D(10**6), "gaming", cap=3)
        order = list(picked)
        for i, category in enumerate(order):
            assert len(picked[category]) <= 3
            for x in picked[category]:
                for earlier in order[:i]:
                    options = picked[earlier] + ([None] if earlier in OPTIONAL else [])
                    assert any(_strict_fit(earlier, y, category, x) for y in options)


def test_gpu_clearance_from_manufacturer_text():
    from app.services.catalog_merge import gpu_clearance
    assert gpu_clearance("Supports graphics cards up to 380mm in length") == 380
    assert gpu_clearance("VGA Card (Length):370mm • Max CPU cooler 160mm") == 370
    assert gpu_clearance("Поддержка видеокарт длиной до 400 мм") == 400
    assert gpu_clearance("GPU installation with a 160 mm riser") is None  # not a length limit


# ---------- Pages that are not desktop PC parts ----------

def test_accessories_external_and_server_parts_are_skipped():
    skipped = [
        (Category.STORAGE, "Carcasă externă ASUS TUF Gaming A1 M.2 NVMe", {"Tip unitate de stocare": "Carcasă externă"}),
        (Category.STORAGE, "M.2 NVMe/SATA SSD Enclosure Asus TUF Gaming A2", {"Format": "M.2 2280"}),
        (Category.STORAGE, "Cartelă de memorie GoodRAM 128GB", {"Form Factor": "micro-SD"}),
        (Category.STORAGE, "SSD Synology SNV3510-800G", {"Form Factor": "M.2 22110"}),
        (Category.STORAGE, "Unitate HDD Fujitsu S26361-F3297-L500 500 GB", {"Aplicare (Utilizare)": "Server"}),
        (Category.PSU, "Xilence SATA Cable x4 for Modular Power Supply", {}),
        (Category.PSU, "Fujitsu S26113-F574-L13", {}),
        (Category.GPU, "Placă video externă Asus ROG XG Mobile GC31R-037 8 GB", {}),
        (Category.RAM, "Memorie RAM 16 GB Synology D4EC-2666-16G", {}),
        (Category.RAM, "Memorie RAM 32GB DDR4-3200 Samsung Reg. ECC M393A4K40EB3-CWE", {}),
        (Category.RAM, "Memorie RAM 16 GB Dell AC958788", {"Form Factor": "ECC"}),
        (Category.MOTHERBOARD, "Placă de bază BIOSTAR H61MHV3", {}),
        (Category.MOTHERBOARD, "Материнская плата с процессором Biostar A68N-2100K", {}),
    ]
    for category, title, specs in skipped:
        assert normalize(category, title, specs).skip, title


def test_current_parts_are_not_mistaken_for_old_or_accessories():
    kept = [
        (Category.MOTHERBOARD, "Placă de bază Gigabyte B850M D3HP", {}),  # B850 is not B85
        (Category.MOTHERBOARD, "Placă de bază ASRock H610M-HDV/M.2 R2.0", {}),  # H610 is not H61
        (Category.MOTHERBOARD, "Placă de bază ASRock H810M-X", {}),
        (Category.RAM, "Memorie RAM Kingston FURY Beast 32GB", {"Verificarea și corectarea erorilor (ECC)": "Nu-(non-ECC)"}),
        (Category.STORAGE, "SSD Kingston NV3 1TB", {"Interfață": "PCI-E 4.0 x4", "Form Factor": "M.2 2280"}),
    ]
    for category, title, specs in kept:
        assert normalize(category, title, specs).skip is None, title
    # Darwin calls this CPU cooler a case fan; the name drops that word.
    cooler = normalize(Category.COOLER, "Ventilator de carcasă Gamemax Ice Force Black",
                       {"Sockets": "Intel: LGA1700, 1200, AMD: AM4, AM5", "Dimensiuni": "120 x 92 x 153 mm"})
    assert cooler.skip is None and not cooler.model.lower().startswith("ventilator")


def test_used_and_refurbished_parts_are_skipped():
    for category, title, specs in [
        (Category.GPU, "Видеокарта MSI GTX 1060 GAMING X 6G 6GB JetStream Used", {}),
        (Category.CPU, "Процессор Intel Celeron G3930 Tray б/у", {}),
        (Category.STORAGE, "HDD 1.0TB Western Digital WD10EURX AV-GP, Reconditionat", {}),
        (Category.STORAGE, "Unitate HDD Seagate Exos 24 TB 3.5\"", {"Stare": "Refurbished"}),
    ]:
        assert normalize(category, title, specs).skip == "used or refurbished part", title
    # "Fused" or a "Stare: Nou" (new) condition is not "used".
    assert normalize(Category.STORAGE, "SSD Kingston NV3 1TB", {"Stare": "Nou", "Form Factor": "M.2 2280",
                                                               "Interfață": "PCI-E 4.0 x4"}).skip is None


# ---------- product identity: part numbers, key specs, merge conflicts ----------

def test_specs_and_series_names_are_not_part_numbers():
    ram, board = Category.RAM, Category.MOTHERBOARD
    for title in ["Memorie RAM 32GB DDR5-5600 Kingston ValueRAM", "Memorie RAM 8GB PC4-25600 Kingston",
                  "Memorie RAM 16GB DDR4-3200MHZ Kingston"]:
        assert _mpn(Labels({}), title, ram) is None, title
    assert _mpn(Labels({}), "Sursă de alimentare Sohoo ATX-550W", Category.PSU) is None
    assert _mpn(Labels({}), "Placă de bază ASUS TUF GAMING B860-PLUS WIFI", board) is None
    assert _mpn(Labels({}), "Placă de bază ASRock H610M-HDV/M.2 R2.0", board) is None
    # The spec in front of the part number is passed over, not taken.
    assert _mpn(Labels({}), "Memorie RAM 8GB DDR5-5600 Transcend JetRam JM5600ALG-8G", ram) == "JM5600ALG-8G"
    assert _mpn(Labels({"Cod model": "DDR5-5600"}), "Memorie RAM 8GB DDR5-5600 Kingston Fury Beast, KF556C40BB-8",
                ram) == "KF556C40BB-8"


def test_neocomputer_ram_of_one_speed_is_not_one_product():
    key = lambda title: normalize(Category.RAM, title, {"Garantie": "60 Luni"}).key
    transcend = key("Memorie RAM 8GB DDR5-5600 Transcend JetRam JM5600ALG-8G")
    assert transcend == normalize(Category.RAM, "Memorie RAM Transcend JetRam, JM5600ALG-8G", {}).key
    others = {key("Memorie RAM 32GB DDR5-5600 Kingston ValueRAM"), key("Memorie RAM 16GB DDR5-5600 Apacer NOX"),
              key("Memorie RAM 16GB DDR5-5600 Kingston Fury Beast DDR5 White RGB Expo")}
    assert len(others) == 3 and transcend not in others


def test_board_names_keep_their_model_line_and_match_across_stores():
    key = lambda title: normalize(Category.MOTHERBOARD, title, {}).key
    prime = key("Placă de bază ASUS PRIME B860-PLUS WIFI")
    assert prime != key("Placă de bază ASUS TUF GAMING B860-PLUS WIFI")
    assert prime == key("Placă de bază Asus PRIME B860-PLUS WIFI ATX")
    assert prime == key("Placă de bază ASUS PRIME B860-PLUS WIFI LGA1851 ATX Intel B860 | DDR5 SDRAM | 4x DIMM")
    assert key("Sursă de alimentare HPC ATX-550W") != key("Sursă de alimentare Sohoo ATX-550W")
    # The M of "B860M-K" is the board size, not part of the chipset.
    assert normalize(Category.MOTHERBOARD, "Placă de bază ASUS PRIME B860M-K", {}).fields["chipset"] == "B860"


def test_kingston_part_number_states_the_specs():
    assert kingston_part("KF436C18BB2AK2/32") == {"speed_mts": 3600, "cas_latency": 18, "modules": 2, "capacity_gb": 32}
    assert kingston_part("KVR32N22S8/8") == {"speed_mts": 3200, "cas_latency": 22, "modules": 1, "capacity_gb": 8}
    assert kingston_part("KF556C36BBE-32") == {"speed_mts": 5600, "cas_latency": 36, "modules": 1, "capacity_gb": 32}
    # A store's wrong table (CL16) gives way to the part number.
    specs = normalize(Category.RAM, "Оперативная память Kingston FURY Beast RGB Kit DDR4 2x16GB 3600MHz "
                                    "KF436C18BB2AK2/32", {"Латентность": "CL16"})
    assert specs.fields["cas_latency"] == 18


def test_intel_f_models_have_no_graphics_whatever_the_table_says():
    f = normalize(Category.CPU, "Procesor Intel Core i5-14600KF 2.60 GHz - 5.30 GHz Tray", {"Grafica integrata": "Da"})
    plain = normalize(Category.CPU, "Procesor Intel Core Ultra 5 225, Tray", {"Grafica integrata": "Nu"})
    # Xstore's "Model" row says "Core Ultra 5 225" on the 225F page.
    xstore_f = normalize(Category.CPU, "Procesor Intel Core Ultra 5 225F, Tray", {"Model": "Intel Core Ultra 5 225"})
    assert f.fields["integrated_graphics"] is False and plain.fields["integrated_graphics"] is True
    assert xstore_f.chip == "Core Ultra 5 225F" and xstore_f.key != plain.key


def test_merge_splits_pages_whose_key_specs_disagree():
    ram = lambda store, title, specs, price: _page(store, title, specs, price, Category.RAM)
    products = merge([
        ram("xstore", "Memorie RAM Goodram, GR5600D564L46/32G", {"Capacitatea totală": "32 GB", "Latența": "CL46"}, "1"),
        ram("darwin", "Memorie RAM Goodram GR5600D564L46/32G", {"Capacitatea totală": "16 GB", "Latența": "CL46"}, "2"),
        ram("ultra", "Memorie RAM Goodram GR5600D564L46/32G", {"Capacitatea totală": "32 GB"}, "3"),
    ])
    assert sorted(sorted(o.store for o in p.offers) for p in products) == [["darwin"], ["ultra", "xstore"]]
    assert len({p.key for p in products}) == 2 and not merge_conflicts(products)


def test_merge_conflicts_lists_every_product_that_is_not_one_product():
    a = normalize(Category.RAM, "Memorie RAM 8GB DDR5-5600 Transcend JetRam JM5600ALG-8G", {})
    b = normalize(Category.RAM, "Memorie RAM 32GB DDR5-5600 Kingston ValueRAM", {})
    offers = [Offer("neocomputer", "https://neo/a", D("1"), None), Offer("neocomputer", "https://neo/b", D("2"), None)]
    bad = Product(Category.RAM, "ram:ddr55600", "Kingston", "x", None, {}, offers, pages=[a, b])
    conflicts = merge_conflicts([bad])
    assert any("2 pages of neocomputer" in c for c in conflicts)
    assert any("capacity_gb [8, 32]" in c for c in conflicts)


def test_whole_crawl_merges_without_conflicts():
    """Every page of the last crawl, normalized and merged: no product may hold two pages of one
    store or pages whose key specs disagree, and no identity key may be a spec."""
    from scripts.import_catalog import PRODUCTS
    if not PRODUCTS.exists():
        pytest.skip("no crawl in .crawl-cache (run `python -m scripts.import_catalog crawl`)")
    pages = []
    for r in json.loads(PRODUCTS.read_text(encoding="utf-8")):
        if not r["title"] or r["title"].startswith("Купить"):
            continue
        specs = normalize(Category(r["category"]), r["title"], r["specs"])
        if not specs.skip:
            pages.append((specs, Offer(r["store"], r["url"], D(r["offer"]["price"]), None)))
    products = merge(pages)
    assert merge_conflicts(products) == []
    spec_keys = [p.key for p in products if re.fullmatch(r"ram:(l?p?ddr\d+|pc\d+)\d*(#\d+)?", p.key)]
    assert spec_keys == []
