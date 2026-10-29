"""Deterministic catalog rules, independent of FastAPI and database queries.

Pairwise checks can later be reused by AC-3. Total power and build completeness
are build-wide checks and must also be run after selecting a configuration.
"""

from dataclasses import dataclass
from itertools import combinations
from typing import TypeVar

from app.compatibility_schemas import CompatibilityIssue, CompatibilityResult
from app.db.models import (
    Base, CaseSpec, Category, Component, CoolerSpec, CpuSpec, GpuSpec,
    MotherboardSpec, PsuSpec, RamSpec, StorageSpec,
)


@dataclass(frozen=True)
class SelectedPart:
    component: Component
    spec: Base | None


Spec = TypeVar("Spec", bound=Base)


def _spec(parts: dict[Category, SelectedPart], category: Category, cls: type[Spec]) -> Spec | None:
    part = parts.get(category)
    return part.spec if part is not None and isinstance(part.spec, cls) else None


LIMITATIONS = [
    "Results cover the rules supported by the manually entered catalog, not a guarantee of assembly.",
    "Motherboard CPU support lists and BIOS versions are not modeled; matching sockets alone are insufficient.",
    "Exact radiator mounts, radiator/GPU interference, RAM/cooler clearance, drive bays, and GPU slot clearance are not modeled.",
    "PSU cable counts, adapters, motherboard display outputs, and exact M.2 protocols/lengths are not fully modeled.",
    "Power uses selected parts' recorded peak draw; 20% headroom is an MVP policy, not a measurement or hardware standard.",
]


class RuleReport:
    def __init__(self, parts: dict[Category, SelectedPart]):
        self.parts = parts
        self.issues: list[CompatibilityIssue] = []
        self.checked: list[str] = []
        self.unknown = False

    def issue(self, code: str, message: str, *categories: Category, severity="error"):
        self.issues.append(CompatibilityIssue(
            code=code, severity=severity, message=message,
            component_ids=[self.parts[c].component.id for c in categories if c in self.parts],
        ))

    def check(self, code: str, condition: bool, message: str, *categories: Category):
        self.checked.append(code)
        if not condition:
            self.issue(code, message, *categories)

    def unverified(self, code: str, message: str, *categories: Category):
        self.unknown = True
        self.issue(code, message, *categories, severity="warning")


def _pair_report(parts: dict[Category, SelectedPart]) -> RuleReport:
    report = RuleReport(parts)
    cpu = _spec(parts, Category.CPU, CpuSpec)
    board = _spec(parts, Category.MOTHERBOARD, MotherboardSpec)
    ram = _spec(parts, Category.RAM, RamSpec)
    gpu = _spec(parts, Category.GPU, GpuSpec)
    storage = _spec(parts, Category.STORAGE, StorageSpec)
    psu = _spec(parts, Category.PSU, PsuSpec)
    case = _spec(parts, Category.CASE, CaseSpec)
    cooler = _spec(parts, Category.COOLER, CoolerSpec)

    if cpu and board:
        if not cpu.socket.strip() or not board.socket.strip():
            report.unverified("platform_socket_unknown", "Socket-ul procesorului sau al plăcii de bază lipsește din catalog.",
                              Category.CPU, Category.MOTHERBOARD)
        else:
            report.check("cpu_socket", cpu.socket == board.socket,
                         f"Socket-ul procesorului ({cpu.socket}) nu se potrivește cu cel al plăcii de bază ({board.socket}).",
                         Category.CPU, Category.MOTHERBOARD)
        if cpu.memory_types:
            report.check("cpu_board_memory", board.memory_type in cpu.memory_types,
                         f"Procesorul suportă {', '.join(cpu.memory_types)}, dar placa de bază folosește {board.memory_type}.",
                         Category.CPU, Category.MOTHERBOARD)
        else:
            report.unverified("cpu_memory_unknown", "Tipurile de memorie suportate de procesor lipsesc din catalog.", Category.CPU)

    if cpu and ram:
        if cpu.memory_types:
            report.check("cpu_ram_memory", ram.memory_type in cpu.memory_types,
                         f"Procesorul suportă {', '.join(cpu.memory_types)}, dar memoria RAM este {ram.memory_type}.",
                         Category.CPU, Category.RAM)
        else:
            report.unverified("cpu_memory_unknown", "Tipurile de memorie suportate de procesor lipsesc din catalog.", Category.CPU)

    if board and ram:
        report.check("board_ram_memory", board.memory_type == ram.memory_type,
                     f"Placa de bază folosește {board.memory_type}, dar memoria RAM este {ram.memory_type}.",
                     Category.MOTHERBOARD, Category.RAM)
        report.check("ram_slots", ram.modules <= board.memory_slots,
                     f"Kitul RAM are nevoie de {ram.modules} sloturi; placa de bază are {board.memory_slots}.",
                     Category.MOTHERBOARD, Category.RAM)
        report.check("ram_capacity", ram.capacity_gb <= board.max_memory_gb,
                     f"Kitul RAM are {ram.capacity_gb} GB; placa de bază suportă cel mult {board.max_memory_gb} GB.",
                     Category.MOTHERBOARD, Category.RAM)

    if board and case:
        if case.supported_board_form_factors:
            report.check("board_case_size", board.form_factor in case.supported_board_form_factors,
                         f"Carcasa nu suportă plăci de bază {board.form_factor}.",
                         Category.MOTHERBOARD, Category.CASE)
        else:
            report.unverified("case_board_sizes_unknown", "Formatele de placă de bază suportate de carcasă lipsesc din catalog.", Category.CASE)

    if gpu and case:
        report.check("gpu_length", gpu.length_mm <= case.max_gpu_length_mm,
                     f"Placa video are {gpu.length_mm} mm lungime; carcasa permite cel mult {case.max_gpu_length_mm} mm.",
                     Category.GPU, Category.CASE)

    if psu and case:
        if psu.form_factor != case.psu_form_factor:
            # An adapter may make a smaller PSU fit; do not invent a hard conflict.
            report.unverified("psu_case_size", f"Sursa este {psu.form_factor}, iar carcasa e pentru {case.psu_form_factor}. Verifică dacă încape și dacă e nevoie de adaptor.",
                              Category.PSU, Category.CASE)
        else:
            report.checked.append("psu_case_size")

    if cpu and cooler:
        if not cpu.socket.strip():
            report.unverified("cpu_socket_unknown", "Socket-ul procesorului lipsește; compatibilitatea cooler-ului nu poate fi verificată.", Category.CPU)
        elif cooler.supported_sockets:
            report.check("cooler_socket", cpu.socket in cooler.supported_sockets,
                         f"Cooler-ul nu suportă socket-ul procesorului ({cpu.socket}).",
                         Category.CPU, Category.COOLER)
        else:
            report.unverified("cooler_sockets_unknown", "Socket-urile suportate de cooler lipsesc din catalog.", Category.COOLER)
        if cooler.max_tdp_w is None:
            report.issue("cooler_rating_unknown", "Puterea de răcire a cooler-ului lipsește; verifică manual dacă răcește suficient.",
                         Category.CPU, Category.COOLER, severity="warning")
        elif cooler.max_tdp_w < cpu.tdp_w:
            report.issue("cooler_thermal_rating", f"Cooler-ul e dat pentru {cooler.max_tdp_w} W, iar procesorul are TDP {cpu.tdp_w} W. Verifică răcirea; valorile sunt aproximative.",
                         Category.CPU, Category.COOLER, severity="warning")

    if cooler and case:
        if cooler.cooler_type == "air":
            if cooler.height_mm is None:
                report.unverified("cooler_height_unknown", "Înălțimea cooler-ului lipsește din catalog.", Category.COOLER)
            else:
                report.check("cooler_height", cooler.height_mm <= case.max_cooler_height_mm,
                             f"Cooler-ul are {cooler.height_mm} mm înălțime; carcasa permite cel mult {case.max_cooler_height_mm} mm.",
                             Category.COOLER, Category.CASE)
        elif cooler.cooler_type == "aio":
            if cooler.radiator_mm is None:
                report.unverified("radiator_size_unknown", "Dimensiunea radiatorului AIO lipsește din catalog.", Category.COOLER)
            elif case.max_radiator_mm is None:
                # The existing catalog defines NULL as no radiator support.
                report.check("case_radiator_unsupported", False,
                             "Carcasa nu are loc pentru radiator AIO.",
                             Category.COOLER, Category.CASE)
            elif cooler.radiator_mm > case.max_radiator_mm:
                report.check("radiator_size", False,
                             f"Radiatorul are {cooler.radiator_mm} mm; carcasa permite cel mult {case.max_radiator_mm} mm.",
                             Category.COOLER, Category.CASE)
            else:
                report.unverified("radiator_mounts_unverified", "Radiatorul se încadrează în dimensiunea maximă a carcasei, dar pozițiile exacte de montare nu sunt în catalog; verifică-le.",
                                  Category.COOLER, Category.CASE)

    if board and storage:
        if storage.storage_type == "nvme" and storage.form_factor.startswith("M.2"):
            report.check("storage_m2_slot", board.m2_slots >= 1,
                         "SSD-ul NVMe are nevoie de un slot M.2, iar placa de bază nu are.",
                         Category.MOTHERBOARD, Category.STORAGE)
        elif storage.storage_type == "nvme":
            report.unverified("storage_interface_unknown", "Nu se știe dacă placa de bază suportă acest tip de conectare NVMe (non-M.2).",
                              Category.MOTHERBOARD, Category.STORAGE)
        elif storage.form_factor.startswith("M.2"):
            report.check("storage_m2_slot", board.m2_slots >= 1,
                         "SSD-ul M.2 are nevoie de un slot M.2, iar placa de bază nu are.",
                         Category.MOTHERBOARD, Category.STORAGE)
            report.unverified("storage_m2_sata_protocol", "Un SSD M.2 SATA cere suport SATA pe slotul M.2; acest lucru nu e în catalog, verifică-l.",
                              Category.MOTHERBOARD, Category.STORAGE)
        else:
            report.check("storage_sata_port", board.sata_ports >= 1,
                         "Stocarea SATA are nevoie de un port SATA, iar placa de bază nu are.",
                         Category.MOTHERBOARD, Category.STORAGE)

    if gpu and psu:
        report.issue("gpu_power_cables_unverified", "Verifică dacă sursa are conectorii de alimentare necesari plăcii video (tip și număr de cabluri); catalogul nu are destule date pentru această verificare.",
                     Category.GPU, Category.PSU, severity="warning")

    return report


def check_pair(left: SelectedPart, right: SelectedPart) -> tuple[list[str], list[CompatibilityIssue], bool]:
    """Evaluate binary constraints without I/O, suitable for later AC-3 filtering.

    The final bool indicates missing data: such a pair must not be pruned as if
    it were a proven conflict. The AC-3 service uses these binary checks.
    """
    report = _pair_report({left.component.category: left, right.component.category: right})
    report.unknown |= left.spec is None or right.spec is None
    return report.checked, report.issues, report.unknown


def check_build(parts: dict[Category, SelectedPart]) -> CompatibilityResult:
    report = RuleReport(parts)
    for category in Category:
        if category not in parts:
            continue
        part = parts[category]
        if part.spec is None:
            report.unverified("specifications_missing", f"Specificațiile pentru {category.value} lipsesc; regulile legate de ele nu au putut fi verificate.", category)

    # Fixed category order gives repeatable reports regardless of JSON key order.
    ordered = [parts[category] for category in Category if category in parts]
    for left, right in combinations(ordered, 2):
        checked, issues, unknown = check_pair(left, right)
        report.checked.extend(checked)
        report.issues.extend(issues)
        report.unknown |= unknown

    required = {Category.CPU, Category.MOTHERBOARD, Category.RAM,
                Category.STORAGE, Category.PSU, Category.CASE}
    cpu = _spec(parts, Category.CPU, CpuSpec)
    if cpu:
        if not cpu.integrated_graphics:
            required.add(Category.GPU)
        if not cpu.includes_cooler:
            required.add(Category.COOLER)
    missing = [category for category in Category if category in required and category not in parts]

    # PSU wattage is capacity, not consumption. Selected parts only: a partial
    # build's estimate is a lower bound, not an estimate for a finished PC.
    draw = sum(part.component.power_draw_w for category, part in parts.items() if category != Category.PSU)
    recommended = (draw * 120 + 99) // 100
    gpu = _spec(parts, Category.GPU, GpuSpec)
    psu = _spec(parts, Category.PSU, PsuSpec)
    if gpu:
        recommended = max(recommended, gpu.recommended_psu_w)
    if psu:
        report.check("psu_capacity", psu.wattage >= draw,
                     f"Piesele alese consumă {draw} W, dar sursa are doar {psu.wattage} W.",
                     *[category for category in Category if category in parts])
        if draw <= psu.wattage < recommended:
            report.issue("psu_headroom", f"Sursa are {psu.wattage} W; pentru piesele alese se recomandă cel puțin {recommended} W (20% rezervă și recomandarea producătorului plăcii video).",
                         Category.PSU, severity="warning")

    # A known conflict takes precedence even in a partial or uncertain build.
    if any(issue.severity == "error" for issue in report.issues):
        status = "incompatible"
    elif missing:
        status = "incomplete"
    elif report.unknown:
        status = "undetermined"
    else:
        status = "compatible"

    # The same unknown CPU-memory field may be encountered by two binary rules.
    unique_issues = list({(issue.code, tuple(issue.component_ids)): issue for issue in report.issues}.values())
    return CompatibilityResult(
        status=status, missing_categories=missing, issues=unique_issues,
        checked_rules=list(dict.fromkeys(report.checked)), estimated_power_w=draw,
        recommended_psu_w=recommended, limitations=list(LIMITATIONS),
    )
