"""What a recommended build must have for each purpose (the baseline tier reference).

Independent of FastAPI and the database. The rules are hard filters on the TOPSIS
alternatives, applied on top of compatibility:

| Purpose | CPU | GPU | RAM | Storage | PSU |
|---|---|---|---|---|---|
| office | >= 4 cores / 8 threads, integrated graphics, up to Ryzen 7 / Core i7 / Core Ultra 7 | none (integrated) | 8-16 GB | one 256-512 GB M.2 SSD (NVMe or SATA) | by load |
| gaming | >= 6 cores / 12 threads | >= 6 GB VRAM | 16-32 GB | SSD >= 500 GB + HDD 500 GB-1 TB, or one fast NVMe >= 1 TB | >= 650 W |
| editing | 8-16 cores | >= 12 GB VRAM | 32-64 GB | NVMe >= 512 GB + fast NVMe >= 2 TB (board with 2 M.2 slots) | 80+ Gold or better |
| workstation | >= 8 cores / 16 threads | >= 8 GB VRAM | >= 32 GB (>= 64 GB with a 24 GB+ GPU) | one fast NVMe 1-2 TB | >= 850 W, 80+ Gold or better |

"Fast" NVMe = PCIe 4.0 or newer. Every purpose gets a dedicated cooler rated for at
least 1.3x the CPU's TDP (rated coolers only; a bundled stock cooler has no rating).
"By load" means the compatibility rules: PSU >= peak draw (and a warning below +20%).
A PSU whose efficiency the stores don't state still counts for "80+ Gold or better";
only a stated lower rating (Bronze, White, ...) excludes it.
"""

import re

from app.db.models import CoolerSpec, CpuSpec, GpuSpec, MotherboardSpec, PsuSpec, RamSpec, Slot, StorageSpec
from app.services.recommend import Candidate, Purpose

COOLER_HEADROOM = 1.3
GOLD_OR_BETTER = ("80+ Gold", "80+ Platinum", "80+ Titanium")
# What catalog_merge stores when no store lists the efficiency; not proof of a lower rating.
NOT_STATED = "not stated"
# Office CPUs go up to the "7" class; these model lines are above it.
_ABOVE_CLASS_7 = re.compile(r"ryzen\s*9|threadripper|\bi9\b|i9-|ultra\s*9", re.I)


def _spec(x: Candidate | None, cls):
    return x.part.spec if x is not None and isinstance(x.part.spec, cls) else None


def fast_nvme(s: StorageSpec) -> bool:
    gen = re.search(r"PCIe\s*(\d)", s.interface or "")
    return s.storage_type == "nvme" and gen is not None and int(gen.group(1)) >= 4


def _ssd(s: StorageSpec) -> bool:
    return s.storage_type in ("nvme", "sata_ssd")


def part_allowed(purpose: Purpose, slot: Slot, x: Candidate) -> bool:
    """Whether this part may fill `slot` in a build for `purpose`."""
    cpu, gpu, ram = _spec(x, CpuSpec), _spec(x, GpuSpec), _spec(x, RamSpec)
    drive, psu, cooler = _spec(x, StorageSpec), _spec(x, PsuSpec), _spec(x, CoolerSpec)
    if slot == Slot.CPU and cpu:
        if purpose == "office":
            return (cpu.cores >= 4 and cpu.threads >= 8 and cpu.integrated_graphics
                    and not _ABOVE_CLASS_7.search(x.part.component.model))
        if purpose == "gaming":
            return cpu.cores >= 6 and cpu.threads >= 12
        if purpose == "editing":
            return 8 <= cpu.cores <= 16
        return cpu.cores >= 8 and cpu.threads >= 16
    if slot == Slot.GPU and gpu:
        return {"office": False, "gaming": gpu.vram_gb >= 6, "editing": gpu.vram_gb >= 12,
                "workstation": gpu.vram_gb >= 8}[purpose]
    if slot == Slot.RAM and ram:
        low, high = {"office": (8, 16), "gaming": (16, 32), "editing": (32, 64), "workstation": (32, None)}[purpose]
        return ram.capacity_gb >= low and (high is None or ram.capacity_gb <= high)
    if slot == Slot.STORAGE and drive:
        if purpose == "office":
            return _ssd(drive) and drive.form_factor.startswith("M.2") and 256 <= drive.capacity_gb <= 512
        if purpose == "gaming":
            return _ssd(drive) and drive.capacity_gb >= 500
        if purpose == "editing":
            return drive.storage_type == "nvme" and drive.capacity_gb >= 512
        return fast_nvme(drive) and 1000 <= drive.capacity_gb <= 2000
    if slot == Slot.STORAGE2 and drive:
        if purpose == "gaming":
            return drive.storage_type == "hdd" and 500 <= drive.capacity_gb <= 1000
        if purpose == "editing":
            return fast_nvme(drive) and drive.capacity_gb >= 2000
        return False  # office and workstation use one drive
    if slot == Slot.PSU and psu:
        if purpose == "gaming":
            return psu.wattage >= 650
        if purpose == "editing":
            return psu.efficiency in GOLD_OR_BETTER + (NOT_STATED,)
        if purpose == "workstation":
            return psu.wattage >= 850 and psu.efficiency in GOLD_OR_BETTER + (NOT_STATED,)
        return True
    if slot == Slot.COOLER and cooler:
        return cooler.max_tdp_w is not None
    board = _spec(x, MotherboardSpec)
    if slot == Slot.MOTHERBOARD and board and purpose == "editing":
        # Both editing drives are M.2 NVMe, so the board needs two M.2 slots.
        return board.m2_slots >= 2
    return slot in (Slot.MOTHERBOARD, Slot.CASE)


def may_be_empty(purpose: Purpose, slot: Slot) -> bool:
    """Whether the build may leave `slot` empty. Office uses integrated graphics (GPU stays
    empty, and the compatibility rules then need a CPU with graphics); gaming may use one
    NVMe drive instead of SSD + HDD; every purpose needs a rated cooler."""
    if slot == Slot.GPU:
        return purpose == "office"
    if slot == Slot.STORAGE2:
        return purpose != "editing"
    return False


def pair_allowed(purpose: Purpose, a: Slot, x: Candidate | None, b: Slot, y: Candidate | None) -> bool:
    """Rules between two slots (either order)."""
    if (a, b) in ((Slot.COOLER, Slot.CPU), (Slot.RAM, Slot.GPU), (Slot.STORAGE2, Slot.STORAGE)):
        a, x, b, y = b, y, a, x
    if (a, b) == (Slot.CPU, Slot.COOLER):
        cpu, cooler = _spec(x, CpuSpec), _spec(y, CoolerSpec)
        return not (cpu and cooler) or (cooler.max_tdp_w or 0) >= COOLER_HEADROOM * cpu.tdp_w
    if (a, b) == (Slot.GPU, Slot.RAM) and purpose == "workstation":
        gpu, ram = _spec(x, GpuSpec), _spec(y, RamSpec)
        return not (gpu and ram) or gpu.vram_gb < 24 or ram.capacity_gb >= 64
    if (a, b) == (Slot.STORAGE, Slot.STORAGE2) and purpose == "gaming":
        first = _spec(x, StorageSpec)
        # Without an HDD, the one drive has to be a fast NVMe of at least 1 TB.
        return y is not None or first is None or (fast_nvme(first) and first.capacity_gb >= 1000)
    return True
