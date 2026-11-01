import itertools
import random
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.compatibility_schemas import CompatibilityRequest
from app.db.models import (
    Category, Component, CoolerSpec, CpuSpec, GpuSpec, MotherboardSpec, PsuSpec, RamSpec, Slot, StorageSpec,
)
from app.services.compatibility import SelectedPart, check_build
from app.services.recommend import Candidate, compatible_builds
from app.services.tiers import may_be_empty, pair_allowed, part_allowed
from tests.test_topsis import random_catalog

D = Decimal
_ids = itertools.count(1)


def part(category, spec, model="Part", price="1000", perf=None, power=10):
    component = Component(id=next(_ids), category=category, model=model, power_draw_w=power,
                          perf_score=None if perf is None else D(perf))
    return Candidate(SelectedPart(component, spec), D(price))


def cpu(cores, threads, igpu=True, model="Ryzen 5 7600", tdp=65):
    return part(Category.CPU, CpuSpec(socket="AM5", cores=cores, threads=threads, tdp_w=tdp, integrated_graphics=igpu,
                                      memory_types=["DDR5"], includes_cooler=False), model=model)


def drive(kind, gb, form="M.2 2280", interface="PCIe 4.0 x4"):
    return part(Category.STORAGE, StorageSpec(storage_type=kind, form_factor=form, interface=interface, capacity_gb=gb))


def gpu(vram):
    return part(Category.GPU, GpuSpec(chipset="X", vram_gb=vram, length_mm=250, recommended_psu_w=550))


def ram(gb):
    return part(Category.RAM, RamSpec(memory_type="DDR5", capacity_gb=gb, modules=2))


def psu(watts, efficiency="80+ Gold"):
    return part(Category.PSU, PsuSpec(wattage=watts, efficiency=efficiency, form_factor="ATX"))


def cooler(rating):
    return part(Category.COOLER, CoolerSpec(cooler_type="air", supported_sockets=["AM5"], height_mm=150, max_tdp_w=rating))


# ---------- each purpose's part rules ----------

def test_office():
    assert part_allowed("office", Slot.CPU, cpu(4, 8))
    assert not part_allowed("office", Slot.CPU, cpu(4, 4))  # needs 8 threads
    assert not part_allowed("office", Slot.CPU, cpu(6, 12, igpu=False))  # needs integrated graphics
    assert not part_allowed("office", Slot.CPU, cpu(16, 32, model="Ryzen 9 9950X"))  # above the Ryzen 7 class
    assert part_allowed("office", Slot.CPU, cpu(8, 16, model="Ryzen 7 8700G"))
    assert not part_allowed("office", Slot.GPU, gpu(8)) and may_be_empty("office", Slot.GPU)
    assert [part_allowed("office", Slot.RAM, ram(gb)) for gb in (4, 8, 16, 32)] == [False, True, True, False]
    assert part_allowed("office", Slot.STORAGE, drive("nvme", 512))
    assert part_allowed("office", Slot.STORAGE, drive("sata_ssd", 256))
    assert not part_allowed("office", Slot.STORAGE, drive("sata_ssd", 480, form="2.5"))  # M.2 only
    assert not part_allowed("office", Slot.STORAGE, drive("nvme", 1000))
    assert not part_allowed("office", Slot.STORAGE2, drive("hdd", 1000, form="3.5"))


def test_gaming():
    assert part_allowed("gaming", Slot.CPU, cpu(6, 12)) and not part_allowed("gaming", Slot.CPU, cpu(4, 8))
    assert part_allowed("gaming", Slot.GPU, gpu(6)) and not part_allowed("gaming", Slot.GPU, gpu(4))
    assert not may_be_empty("gaming", Slot.GPU)
    assert [part_allowed("gaming", Slot.RAM, ram(gb)) for gb in (8, 16, 32, 64)] == [False, True, True, False]
    assert part_allowed("gaming", Slot.PSU, psu(650, "80+ Bronze")) and not part_allowed("gaming", Slot.PSU, psu(550))
    # 500 GB SSD + 500 GB-1 TB HDD, or one fast NVMe of at least 1 TB.
    ssd, hdd = drive("sata_ssd", 500, form="2.5", interface="SATA III"), drive("hdd", 1000, form="3.5", interface="SATA III")
    assert part_allowed("gaming", Slot.STORAGE, ssd) and part_allowed("gaming", Slot.STORAGE2, hdd)
    assert not part_allowed("gaming", Slot.STORAGE2, drive("hdd", 2000, form="3.5"))
    assert pair_allowed("gaming", Slot.STORAGE, ssd, Slot.STORAGE2, hdd)
    assert not pair_allowed("gaming", Slot.STORAGE, ssd, Slot.STORAGE2, None)
    assert pair_allowed("gaming", Slot.STORAGE2, None, Slot.STORAGE, drive("nvme", 1000))
    assert not pair_allowed("gaming", Slot.STORAGE, drive("nvme", 1000, interface="PCIe 3.0 x4"), Slot.STORAGE2, None)


def test_editing():
    assert part_allowed("editing", Slot.CPU, cpu(8, 16)) and part_allowed("editing", Slot.CPU, cpu(16, 32))
    assert not part_allowed("editing", Slot.CPU, cpu(6, 12)) and not part_allowed("editing", Slot.CPU, cpu(24, 32))
    assert part_allowed("editing", Slot.GPU, gpu(12)) and not part_allowed("editing", Slot.GPU, gpu(8))
    assert [part_allowed("editing", Slot.RAM, ram(gb)) for gb in (16, 32, 64, 128)] == [False, True, True, False]
    assert part_allowed("editing", Slot.STORAGE, drive("nvme", 512, interface="PCIe 3.0 x4"))
    assert part_allowed("editing", Slot.STORAGE2, drive("nvme", 2000))
    assert not part_allowed("editing", Slot.STORAGE2, drive("nvme", 2000, interface="PCIe 3.0 x4"))  # must be fast
    assert not may_be_empty("editing", Slot.STORAGE2)
    assert part_allowed("editing", Slot.PSU, psu(750, "80+ Platinum"))
    assert not part_allowed("editing", Slot.PSU, psu(1000, "80+ Bronze"))


def test_workstation():
    assert part_allowed("workstation", Slot.CPU, cpu(8, 16)) and not part_allowed("workstation", Slot.CPU, cpu(8, 8))
    assert part_allowed("workstation", Slot.GPU, gpu(8)) and not part_allowed("workstation", Slot.GPU, gpu(6))
    assert part_allowed("workstation", Slot.RAM, ram(32)) and not part_allowed("workstation", Slot.RAM, ram(16))
    # A 24 GB+ GPU needs at least 64 GB of RAM.
    assert not pair_allowed("workstation", Slot.RAM, ram(32), Slot.GPU, gpu(24))
    assert pair_allowed("workstation", Slot.GPU, gpu(24), Slot.RAM, ram(64))
    assert pair_allowed("workstation", Slot.GPU, gpu(16), Slot.RAM, ram(32))
    assert part_allowed("workstation", Slot.STORAGE, drive("nvme", 2000))
    assert not part_allowed("workstation", Slot.STORAGE, drive("nvme", 4000))
    assert not part_allowed("workstation", Slot.PSU, psu(750)) and part_allowed("workstation", Slot.PSU, psu(850))
    assert part_allowed("workstation", Slot.PSU, psu(1000, "not stated"))  # unknown is not a lower rating
    assert not part_allowed("workstation", Slot.PSU, psu(1000, "80+ Bronze"))


def test_cooler_needs_rating_and_headroom():
    for purpose in ("office", "gaming", "editing", "workstation"):
        assert not may_be_empty(purpose, Slot.COOLER)
    assert not part_allowed("office", Slot.COOLER, cooler(None))
    assert pair_allowed("gaming", Slot.CPU, cpu(6, 12, tdp=100), Slot.COOLER, cooler(130))
    assert not pair_allowed("gaming", Slot.COOLER, cooler(129), Slot.CPU, cpu(6, 12, tdp=100))


# ---------- second drive: compatibility ----------

BOARD = MotherboardSpec(socket="AM5", chipset="B650", form_factor="ATX", memory_type="DDR5", memory_slots=4,
                        max_memory_gb=192, m2_slots=1, sata_ports=1, wifi=False)


def test_two_drives_need_two_connectors():
    board = SelectedPart(Component(id=900, category=Category.MOTHERBOARD, power_draw_w=40), BOARD)
    m2 = lambda i: SelectedPart(Component(id=i, category=Category.STORAGE, power_draw_w=6),
                                StorageSpec(storage_type="nvme", form_factor="M.2 2280", interface="PCIe 4.0 x4", capacity_gb=1000))
    sata = lambda i: SelectedPart(Component(id=i, category=Category.STORAGE, power_draw_w=8),
                                  StorageSpec(storage_type="hdd", form_factor="3.5", interface="SATA III", capacity_gb=1000))
    codes = lambda r: {i.code for i in r.issues if i.severity == "error"}
    assert "storage_m2_count" in codes(check_build({Slot.MOTHERBOARD: board, Slot.STORAGE: m2(1), Slot.STORAGE2: m2(2)}))
    assert "storage_sata_count" in codes(check_build({Slot.MOTHERBOARD: board, Slot.STORAGE: sata(1), Slot.STORAGE2: sata(2)}))
    mixed = check_build({Slot.MOTHERBOARD: board, Slot.STORAGE: m2(1), Slot.STORAGE2: sata(2)})
    assert not codes(mixed) & {"storage_m2_count", "storage_sata_count"}


def test_the_same_drive_may_fill_both_slots():
    assert CompatibilityRequest(components={"storage": 5, "storage2": 5}).components[Slot.STORAGE2] == 5
    with pytest.raises(ValidationError):
        CompatibilityRequest(components={"cpu": 5, "storage": 5})


def test_builds_with_a_second_drive_match_brute_force():
    rng = random.Random(21)
    for _ in range(10):
        domains = {Slot(c.value): xs for c, xs in random_catalog(rng).items()}
        domains[Slot.STORAGE2] = list(domains[Slot.STORAGE])
        budget = D(rng.randint(10000, 40000))
        found = {tuple(b[s].part.component.id if b.get(s) else None for s in Slot) for b in compatible_builds(domains, budget)}
        expected = set()
        options = [domains[s] + ([None] if s in (Slot.GPU, Slot.COOLER, Slot.STORAGE2) else []) for s in Slot]
        for combo in itertools.product(*options):
            build = {s: x for s, x in zip(Slot, combo) if x is not None}
            if sum(x.price for x in build.values()) <= budget and \
                    check_build({s: x.part for s, x in build.items()}).status == "compatible":
                expected.add(tuple(x.part.component.id if x else None for x in combo))
        assert found == expected
