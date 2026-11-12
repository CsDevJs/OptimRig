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
                      optional: tuple[Slot, ...] = OPTIONAL, extra: PairRule | None = None,
                      floor: Decimal = Decimal(0)) -> Iterator[Build]:
    """Yield every complete, compatible build whose total price is between `floor` and `budget`.

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
    limit, minimum = int(budget * 100), int(floor * 100)
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
            # Prune when a later category is left empty, even its cheapest parts exceed the
            # budget, or even its dearest parts stay under the floor.
            if (any(not d for d in reduced) or total + sum(min(map(cents, d)) for d in reduced) > limit
                    or total + sum(max(map(cents, d)) for d in reduced) < minimum):
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
# Slots whose picks are spread over their price range (see prefilter step 4): CPU and GPU
# set a build's price level; RAM and drive sizes make the variants differ for office too.
PRICE_SPREAD_SLOTS = (Slot.CPU, Slot.GPU, Slot.RAM, Slot.STORAGE)


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
    """About `cap` parts per slot for the build search:
    1. parts with specs whose price leaves room for the cheapest part of every other slot;
    2. the Pareto front within each signature group (see `pareto`);
    3. the parts of cheap complete builds (see `cheap_build`): first the cheapest overall,
       then, once the CPUs are picked, one for each picked CPU. Without them, the
       best-ranked parts of different slots may not combine (an expensive or other-socket
       pick in one slot, no matching part in the next), leaving a CPU with no build or no
       build within the budget. A slot can get a little over `cap` parts this way;
    4. for CPU, GPU, RAM and the first drive, the best-ranked part (by the part-level
       TOPSIS of step 5) in each of the remaining price bands of the slot, so builds span
       cheap to near the budget and differ in more than one part;
    5. the parts a part-level TOPSIS (same weights, the part's own price/performance/power;
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
    base = {s: pareto([x for x in with_specs[s] if x.cents <= limit - sum(v for c, v in cheapest.items() if c != s)])
            for s in Slot}
    first = cheap_build(base, optional, extra)  # {} when no cheap build was found
    chains = [first] if first else []
    picked: dict[Slot, list[Candidate]] = {}

    for category in PICK_ORDER:
        front = base[category]

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
        chosen = []
        for chain in chains:
            part = chain.get(category)
            if part is not None and part in front and part not in chosen:
                chosen.append(part)
        if category in PRICE_SPREAD_SLOTS:
            # Take the best-ranked part of each price band, so the shown variants can run
            # from cheap to near the budget.
            low, high = min(x.cents for x in front), max(x.cents for x in front)
            bands = cap - len(chosen)
            width = (high - low) / bands if bands else 0
            for band in range(bands):
                in_band = [x for x in order if x not in chosen and
                           (width == 0 or min(bands - 1, int((x.cents - low) / width)) == band)]
                if in_band:
                    chosen.append(in_band[0])
        queues = [[x for x in queue if x not in chosen] for queue in groups.values()]
        while len(chosen) < cap and any(queues):
            for queue in queues:
                if queue and len(chosen) < cap:
                    chosen.append(queue.pop(0))
        picked[category] = chosen
        if category == Slot.CPU:
            # Step 3 for every picked CPU: each one then has parts to form a complete build.
            for cpu in chosen:
                if not any(chain.get(Slot.CPU) is cpu for chain in chains):
                    chain = cheap_build({**base, Slot.CPU: [cpu]}, optional, extra)
                    if chain:
                        chains.append(chain)
    return picked


CHEAP_BUILD_CPU_TRIES = 25


def cheap_build(domains: dict[Slot, list[Candidate]], optional: tuple[Slot, ...] = OPTIONAL,
                extra: PairRule | None = None) -> dict[Slot, Candidate | None]:
    """A cheap complete build, built greedily: for each CPU from the cheapest up (at most
    CHEAP_BUILD_CPU_TRIES), slot by slot the cheapest part that fits (compatibility and
    `extra`) every part chosen so far, an optional slot left empty when that fits, and a
    PSU covering the chosen parts' draw + 50 W for the case, cooler and drives. The first
    CPU for which every slot gets a part wins; {} when none does."""
    for cpu in sorted(domains[Slot.CPU], key=lambda x: x.cents)[:CHEAP_BUILD_CPU_TRIES]:
        build: dict[Slot, Candidate | None] = {Slot.CPU: cpu}

        def fits(slot: Slot, x: Candidate | None) -> bool:
            if slot == Slot.PSU and x is not None:
                if x.part.spec.wattage < sum(y.power_w for y in build.values() if y) + 50:
                    return False
            return all(_strict_fit(s, y, slot, x) and (extra is None or extra(s, y, slot, x))
                       for s, y in build.items())

        for slot in PICK_ORDER[1:]:
            if slot in optional and fits(slot, None):
                build[slot] = None
                continue
            part = min((x for x in domains[slot] if fits(slot, x)), key=lambda x: x.cents, default=None)
            if part is None:
                break
            build[slot] = part
        else:
            if _drives_fit(build):
                return build
    return {}


def _strict_fit(a: Slot, x: Candidate | None, b: Slot, y: Candidate | None) -> bool:
    if x is None or y is None:
        return supported(a, x and x.part, b, y and y.part)
    _, issues, unknown = check_pair(x.part, y.part)
    return not unknown and not any(i.severity == "error" for i in issues)


# ---------- Which ranked builds to show ----------

SHOWN_BUILDS = 6


def spread_in_range(scores: list[TopsisScore], prices: list[Decimal], pairs: list[tuple], low: Decimal,
                    high: Decimal, count: int = SHOWN_BUILDS,
                    setups: list[tuple] | None = None) -> list[tuple[int, TopsisScore]]:
    """Builds to show, as (rank, score), cheapest first.

    The price range low-high is split into `count` equal bands; each band shows its
    best-ranked build, so the variants run from the low end to the high end of the range.
    No two shown builds share a CPU chip + GPU chip pair (`pairs[i]`). When some bands
    are empty, the best-ranked remaining builds with new pairs fill in; when no new pair
    is left, builds without a GPU (office) with a new `setups[i]` (pair plus RAM and
    storage size) do; a build with a GPU never repeats a pair. Fewer than `count` are
    returned when there are not enough different builds.
    `prices[i]`, `pairs[i]` and `setups[i]` belong to the build at `scores[k].index == i`.
    """
    if not scores:
        return []
    width = (high - low) / count
    band_of = lambda price: count - 1 if width <= 0 else max(0, min(count - 1, int((price - low) / width)))
    ranked = list(enumerate(scores, start=1))
    chosen: list[tuple[int, TopsisScore]] = []
    bands, used = set(), set()
    for rank, score in ranked:  # best first: the first build seen in a band is its best
        band, pair = band_of(prices[score.index]), pairs[score.index]
        if band not in bands and pair not in used:
            bands.add(band)
            used.add(pair)
            chosen.append((rank, score))
    for rank, score in ranked:
        if len(chosen) >= count:
            break
        if pairs[score.index] not in used:
            used.add(pairs[score.index])
            chosen.append((rank, score))
    if setups is not None:
        shown = {setups[s.index] for _, s in chosen}
        for rank, score in ranked:
            if len(chosen) >= count:
                break
            # Only GPU-less builds: with a GPU, a new RAM or storage size is no new variant.
            if pairs[score.index][1] is None and setups[score.index] not in shown:
                shown.add(setups[score.index])
                chosen.append((rank, score))
    return sorted(chosen, key=lambda item: prices[item[1].index])
