"""Smart recommendations: every compatible build within budget, ranked by TOPSIS.

Independent of FastAPI and the database. Alternatives are generated from the
catalog with AC-3 followed by backtracking; each one is a complete build that
`check_build` would call `compatible`. TOPSIS then ranks them on three criteria:
acquisition cost (min), performance (max) and estimated consumption (min).
"""
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.db.models import Category, CoolerSpec, Slot
from app.services.ac3 import filter_catalog, spec_signature as signature, supported
from app.services.compatibility import SelectedPart, check_pair
from app.services.topsis import TopsisScore, topsis

Purpose = Literal["gaming", "office", "workstation", "editing"]

CRITERIA = ("price", "performance", "power")
MAXIMIZE = [False, True, False]
# Relative importance of price / performance / consumption; each row sums to 1.
WEIGHTS: dict[Purpose, tuple[float, float, float]] = {
    "gaming": (0.35, 0.50, 0.15),
    "office": (0.60, 0.20, 0.20),
    "workstation": (0.25, 0.60, 0.15),
    "editing": (0.30, 0.55, 0.15),
}
# Performance = CPU share * CPU perf_score + GPU share * GPU perf_score.
PERFORMANCE_MIX: dict[Purpose, tuple[float, float]] = {
    "gaming": (0.5, 0.5),
    "office": (0.7, 0.3),
    "workstation": (0.5, 0.5),
    "editing": (0.6, 0.4),
}
# Slots that may be left empty (CPU with integrated graphics / a bundled cooler / one drive).
OPTIONAL = (Slot.GPU, Slot.COOLER, Slot.STORAGE2)


@dataclass(frozen=True)
class Candidate:
    part: SelectedPart
    price: Decimal  # cheapest in-stock offer, what the purchase plan pays
    # Read once from the ORM objects: the search visits each part many times.
    cents: int = field(init=False)
    power_w: int = field(init=False)
    perf_score: float = field(init=False)  # CPU/GPU benchmark; a cooler's rated TDP (more = cooler CPU)

    def __post_init__(self):
        component, spec = self.part.component, self.part.spec
        object.__setattr__(self, "cents", int(self.price * 100))
        object.__setattr__(self, "power_w", component.power_draw_w)
        perf = (spec.max_tdp_w or 0) if isinstance(spec, CoolerSpec) else component.perf_score
        object.__setattr__(self, "perf_score", float(perf or 0))


Build = dict[Slot, Candidate | None]
# A rule between two slots on top of compatibility (the purpose's tier rules).
PairRule = Callable[[Slot, Candidate | None, Slot, Candidate | None], bool]


def _drives_fit(build: Build) -> bool:
    """Two drives need two connectors of their kind on the board (check_build's storage_*_count)."""
    drives = [build[s].part.spec for s in (Slot.STORAGE, Slot.STORAGE2) if build.get(s)]
    if len(drives) < 2:
        return True
    board = build[Slot.MOTHERBOARD].part.spec
    m2 = sum(d.form_factor.startswith("M.2") for d in drives)
    return board.m2_slots >= m2 and board.sata_ports >= len(drives) - m2


def compatible_builds(domains: dict[Slot, list[Candidate]], budget: Decimal,
                      optional: tuple[Slot, ...] = OPTIONAL, extra: PairRule | None = None) -> Iterator[Build]:
    """Yield every complete, compatible build whose total price is within `budget`.

    `domains` holds the purchasable parts of each slot (the second drive's are storage
    parts). Slots in `optional` may also be empty (None); GPU and cooler only when the
    CPU allows it. A build is kept only when no pairwise rule fails or lacks data, the
    `extra` rules hold, two drives have two connectors, and the PSU covers the peak draw.
    """
    order = list(Slot)
    ac3_domains = {s: [x.part for x in domains.get(s, [])] + ([None] if s in optional else []) for s in order}
    filtered = filter_catalog(ac3_domains)
    by_id = {x.part.component.id: x for values in domains.values() for x in values}
    # A part without specs cannot be shown compatible.
    values = {s: [None if p is None else by_id[p.component.id] for p in filtered[s] if p is None or p.spec is not None]
              for s in order}
    if any(not values[s] for s in order):
        return

    def fits(a: Slot, x: Candidate | None, b: Slot, y: Candidate | None) -> bool:
        """Strict pairwise check: no failed rule and no rule left unresolved by missing data."""
        if extra is not None and not extra(a, x, b, y):
            return False
        if x is None or y is None:
            return supported(a, x and x.part, b, y and y.part)
        _, issues, unknown = check_pair(x.part, y.part)
        return not unknown and not any(i.severity == "error" for i in issues)

    # Every pair is checked once up front; the search then only looks up these sets.
    compatible = {
        (a, b): {(id(x), id(y)) for x in values[a] for y in values[b] if fits(a, x, b, y)}
        for i, a in enumerate(order) for b in order[i + 1:]
    }
    cents = lambda x: x.cents if x else 0
    power = lambda x: x.power_w if x else 0
    limit = int(budget * 100)
    build: Build = {}

    def extend(i: int, cost: int, draw: int, domains: list[list[Candidate | None]]) -> Iterator[Build]:
        """Backtracking with forward checking: `domains` holds the categories from
        position i on, already reduced to parts compatible with everything chosen.
        `cost` and `draw` are the chosen parts' price (bani) and peak draw, PSU excluded."""
        if i == len(order):
            if build[Slot.PSU].part.spec.wattage >= draw and _drives_fit(build):
                yield dict(build)
            return
        category, later = order[i], order[i + 1:]
        for x in domains[0]:
            total = cost + cents(x)
            reduced = [[y for y in domain if (id(x), id(y)) in compatible[category, c]]
                       for c, domain in zip(later, domains[1:])]
            # Prune when a later category is left empty or even its cheapest part exceeds the budget.
            if any(not d for d in reduced) or total + sum(min(map(cents, d)) for d in reduced) > limit:
                continue
            build[category] = x
            yield from extend(i + 1, total, draw + (0 if category == Slot.PSU else power(x)), reduced)
            del build[category]

    yield from extend(0, 0, 0, [values[c] for c in order])


def criteria(build: Build, purpose: Purpose) -> tuple[Decimal, float, int]:
    """Acquisition cost (MDL), performance, estimated consumption (W, PSU excluded)."""
    cpu_share, gpu_share = PERFORMANCE_MIX[purpose]
    score = lambda c: build[c].perf_score if build.get(c) else 0.0
    price = Decimal(sum(x.cents for x in build.values() if x)).scaleb(-2)
    power = sum(x.power_w for c, x in build.items() if x and c != Slot.PSU)
    return price, cpu_share * score(Slot.CPU) + gpu_share * score(Slot.GPU), power


def rank_builds(builds: list[Build], purpose: Purpose) -> list[TopsisScore]:
    """TOPSIS scores for `builds` (best first); `index` points into `builds`."""
    matrix = [[float(v) for v in criteria(b, purpose)] for b in builds]
    return topsis(matrix, list(WEIGHTS[purpose]), MAXIMIZE)


# ---------- Pre-filter: keep the build search small on a large catalog ----------

MAX_PARTS_PER_CATEGORY = 5
# Order in which slots get their parts; each later pick must fit an earlier pick.
PICK_ORDER = [Slot.CPU, Slot.MOTHERBOARD, Slot.RAM, Slot.GPU, Slot.PSU,
              Slot.CASE, Slot.COOLER, Slot.STORAGE, Slot.STORAGE2]


def _dominates(a: Candidate, b: Candidate) -> bool:
    """a is at least as good as b on price, performance and consumption, and better on one."""
    at_least = a.cents <= b.cents and a.perf_score >= b.perf_score and a.power_w <= b.power_w
    better = a.cents < b.cents or a.perf_score > b.perf_score or a.power_w < b.power_w
    return at_least and better


def pareto(candidates: list[Candidate]) -> list[Candidate]:
    """Parts not dominated by a part with the same signature. Swapping a dominated part for
    the part that dominates it keeps the build compatible and never makes it worse on any
    criterion, so TOPSIS never ranks a build with the dominated part higher."""
    groups: dict[tuple, list[Candidate]] = {}
    for x in candidates:
        groups.setdefault(signature(x.part), []).append(x)
    kept = []
    for group in groups.values():
        kept += [x for x in group if not any(_dominates(y, x) for y in group if y is not x)]
    return kept


def prefilter(domains: dict[Slot, list[Candidate]], budget: Decimal, purpose: Purpose,
              cap: int = MAX_PARTS_PER_CATEGORY, optional: tuple[Slot, ...] = OPTIONAL,
              extra: PairRule | None = None) -> dict[Slot, list[Candidate]]:
    """At most `cap` parts per slot for the build search:
    1. parts with specs whose price leaves room for the cheapest part of every other slot;
    2. the Pareto front within each signature group (see `pareto`);
    3. one part of a cheap build: slot by slot, the cheapest part that fits (compatibility
       and `extra`) the parts reserved so far, with a PSU covering their draw + 50 W for
       the case, cooler and drives. Without it, the best-ranked parts can all be too
       expensive together and no build fits the budget, even though cheaper builds exist;
    4. the parts a part-level TOPSIS (same weights, the part's own price/performance/power;
       for coolers the rated TDP counts as performance, so better coolers rank higher, not
       just cheaper ones) ranks best, taking groups in turn so different sockets and sizes
       stay represented, and only parts that fit (compatibility and `extra`) at least one
       part already picked for each earlier slot.
    """
    with_specs = {s: [x for x in domains.get(s, []) if x.part.spec is not None] for s in Slot}
    cheapest = {s: min((x.cents for x in xs), default=0) for s, xs in with_specs.items()}
    for s in optional:
        cheapest[s] = 0  # may be left out
    limit = int(budget * 100)
    picked: dict[Slot, list[Candidate]] = {}
    chain: dict[Slot, Candidate | None] = {}  # the cheap build of step 3

    def fits_chain(slot: Slot, x: Candidate | None) -> bool:
        if slot == Slot.PSU and x is not None:
            draw = sum(y.power_w for y in chain.values() if y)
            if x.part.spec.wattage < draw + 50:
                return False
        return all(_strict_fit(s, y, slot, x) and (extra is None or extra(s, y, slot, x)) for s, y in chain.items())

    for category in PICK_ORDER:
        room = limit - sum(v for c, v in cheapest.items() if c != category)
        front = pareto([x for x in with_specs[category] if x.cents <= room])

        def fits_earlier(x: Candidate) -> bool:
            for earlier, chosen in picked.items():
                options = chosen + ([None] if earlier in optional else [])
                if not any(_strict_fit(earlier, y, category, x)
                           and (extra is None or extra(earlier, y, category, x)) for y in options):
                    return False
            return True

        front = [x for x in front if fits_earlier(x)]
        if not front:
            picked[category] = []
            continue
        matrix = [[x.cents, x.perf_score, x.power_w] for x in front]
        order = [front[s.index] for s in topsis(matrix, list(WEIGHTS[purpose]), MAXIMIZE)]
        groups: dict[tuple, list[Candidate]] = {}
        for x in order:  # best first within each group; groups ordered by their best part
            groups.setdefault(signature(x.part), []).append(x)
        if category in optional and fits_chain(category, None):
            chain[category], chosen = None, []
        else:
            reserved = min((x for x in front if fits_chain(category, x)), key=lambda x: x.cents, default=None)
            chain[category], chosen = reserved, [reserved] if reserved else []
        queues = [[x for x in queue if x not in chosen] for queue in groups.values()]
        while len(chosen) < cap and any(queues):
            for queue in queues:
                if queue and len(chosen) < cap:
                    chosen.append(queue.pop(0))
        picked[category] = chosen
    return picked


def _strict_fit(a: Slot, x: Candidate | None, b: Slot, y: Candidate | None) -> bool:
    if x is None or y is None:
        return supported(a, x and x.part, b, y and y.part)
    _, issues, unknown = check_pair(x.part, y.part)
    return not unknown and not any(i.severity == "error" for i in issues)
