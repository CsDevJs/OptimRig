import itertools
import random
from decimal import Decimal
from math import sqrt

import pytest

from app.db.models import (
    CaseSpec, Category, Component, CoolerSpec, CpuSpec, GpuSpec,
    MotherboardSpec, PsuSpec, RamSpec, StorageSpec,
)
from app.services.catalog_normalize import cpu_chip
from app.services.compatibility import SelectedPart, check_build
from app.services.recommend import (
    PERFORMANCE_MIX, WEIGHTS, Candidate, compatible_builds, criteria, rank_builds,
)
from app.services.topsis import topsis

D = Decimal


# ---------- TOPSIS ----------

def test_worked_example():
    # Criteria: cost (min), benefit (max), equal weights.
    # Column norms sqrt(6) and 3; weighted rows: a0 (0.204, 0.167), a1 (0.408, 0.333), a2 (0.204, 0.333).
    # Ideal (0.204, 0.333), anti-ideal (0.408, 0.167).
    scores = topsis([[1, 1], [2, 2], [1, 2]], [0.5, 0.5], [False, True])
    assert [s.index for s in scores] == [2, 0, 1]
    by_index = {s.index: s for s in scores}
    cost, benefit = 0.5 / sqrt(6), 0.5 / 3
    assert by_index[2].distance_best == pytest.approx(0)
    assert by_index[2].closeness == pytest.approx(1)
    assert by_index[0].distance_best == pytest.approx(benefit)
    assert by_index[0].distance_worst == pytest.approx(cost)
    assert by_index[0].closeness == pytest.approx(cost / (cost + benefit))
    assert by_index[1].closeness == pytest.approx(benefit / (cost + benefit))


def test_dominating_and_dominated_alternatives():
    # Row 1 is best on every criterion, row 2 worst on every criterion.
    scores = topsis([[50, 60, 300], [40, 90, 200], [70, 30, 400]], [0.4, 0.4, 0.2], [False, True, False])
    assert scores[0].index == 1 and scores[0].closeness == pytest.approx(1)
    assert scores[-1].index == 2 and scores[-1].closeness == pytest.approx(0)


def test_units_do_not_matter():
    # Vector normalization: prices in lei or bani give the same ranking and closeness.
    matrix = [[18844, 21.6, 159], [29143, 44.9, 362], [49529, 72.0, 573]]
    in_bani = [[row[0] * 100, *row[1:]] for row in matrix]
    weights, maximize = [0.35, 0.5, 0.15], [False, True, False]
    assert [(s.index, pytest.approx(s.closeness)) for s in topsis(matrix, weights, maximize)] == \
           [(s.index, s.closeness) for s in topsis(in_bani, weights, maximize)]


def test_weights_decide_the_winner():
    cheap_slow, pricey_fast = [100, 10], [300, 30]
    matrix = [cheap_slow, pricey_fast]
    assert topsis(matrix, [0.8, 0.2], [False, True])[0].index == 0
    assert topsis(matrix, [0.2, 0.8], [False, True])[0].index == 1


def test_identical_alternatives_and_zero_columns():
    scores = topsis([[5, 0], [5, 0]], [0.5, 0.5], [False, True])
    assert [s.closeness for s in scores] == [1, 1]
    assert topsis([], [1.0], [True]) == []


@pytest.mark.parametrize("weights", [[0.5, 0.6], [1.2, -0.2], [0.5, 0.4]])
def test_weights_must_be_nonnegative_and_sum_to_one(weights):
    with pytest.raises(ValueError):
        topsis([[1, 2]], weights, [False, True])


def test_shape_is_checked():
    with pytest.raises(ValueError):
        topsis([[1, 2, 3]], [0.5, 0.5], [False, True])
    with pytest.raises(ValueError):
        topsis([[1, 2]], [0.5, 0.5], [False])


def test_purpose_weights_are_valid():
    for purpose, weights in WEIGHTS.items():
        assert all(w >= 0 for w in weights) and sum(weights) == pytest.approx(1), purpose
        assert sum(PERFORMANCE_MIX[purpose]) == pytest.approx(1), purpose


# ---------- Generating the alternatives ----------

def random_catalog(rng):
    """Two or three random parts per category, with values that make rules pass and fail."""
    sockets, memory = ["AM4", "AM5"], ["DDR4", "DDR5"]
    make = {
        Category.CPU: lambda: CpuSpec(socket=rng.choice(sockets), memory_types=rng.sample(memory, rng.randint(1, 2)),
                                      tdp_w=rng.choice([65, 120, 170]), includes_cooler=rng.random() < 0.3,
                                      integrated_graphics=rng.random() < 0.4),
        Category.MOTHERBOARD: lambda: MotherboardSpec(socket=rng.choice(sockets), memory_type=rng.choice(memory),
                                                      form_factor=rng.choice(["ATX", "Micro-ATX"]), memory_slots=rng.choice([2, 4]),
                                                      max_memory_gb=rng.choice([64, 128]), m2_slots=rng.choice([0, 2]), sata_ports=4),
        Category.RAM: lambda: RamSpec(memory_type=rng.choice(memory), capacity_gb=rng.choice([16, 32, 96]),
                                      modules=rng.choice([2, 4])),
        Category.GPU: lambda: GpuSpec(length_mm=rng.choice([250, 330]), recommended_psu_w=rng.choice([550, 750])),
        Category.STORAGE: lambda: rng.choice([StorageSpec(storage_type="nvme", form_factor="M.2 2280"),
                                              StorageSpec(storage_type="sata", form_factor="2.5")]),
        Category.PSU: lambda: PsuSpec(wattage=rng.choice([350, 550, 850]), form_factor="ATX"),
        Category.CASE: lambda: CaseSpec(supported_board_form_factors=rng.choice([["ATX", "Micro-ATX"], ["Micro-ATX"]]),
                                        max_gpu_length_mm=rng.choice([300, 400]), max_cooler_height_mm=rng.choice([150, 170]),
                                        max_radiator_mm=rng.choice([None, 360]), psu_form_factor="ATX"),
        Category.COOLER: lambda: rng.choice([
            CoolerSpec(cooler_type="air", height_mm=rng.choice([140, 160]), supported_sockets=rng.sample(sockets, rng.randint(1, 2)),
                       max_tdp_w=200),
            CoolerSpec(cooler_type="aio", radiator_mm=240, supported_sockets=sockets, max_tdp_w=250),
        ]),
    }
    domains, next_id = {}, 1
    for category, spec in make.items():
        domains[category] = []
        for _ in range(rng.randint(2, 3)):
            component = Component(id=next_id, category=category, power_draw_w=rng.choice([10, 80, 200]),
                                  perf_score=D(rng.randint(10, 100)) if category in (Category.CPU, Category.GPU) else None)
            domains[category].append(Candidate(SelectedPart(component, spec()), D(rng.randint(500, 5000))))
            next_id += 1
    return domains


def ids(build):
    return tuple(None if build.get(c) is None else build[c].part.component.id for c in Category)


def brute_force(domains, budget):
    """Every combination, judged by the same check as POST /compatibility/check."""
    options = [domains[c] + ([None] if c in (Category.GPU, Category.COOLER) else []) for c in Category]
    found = set()
    for combo in itertools.product(*options):
        build = {c: x for c, x in zip(Category, combo) if x is not None}
        if sum(x.price for x in build.values()) <= budget and \
                check_build({c: x.part for c, x in build.items()}).status == "compatible":
            found.add(ids(build))
    return found


def test_builds_match_brute_force_on_random_catalogs():
    rng = random.Random(7)
    total = 0
    for _ in range(60):
        domains = random_catalog(rng)
        budget = D(rng.randint(8000, 40000))
        found = [ids(b) for b in compatible_builds(domains, budget)]
        assert len(found) == len(set(found))
        assert set(found) == brute_force(domains, budget)
        total += len(found)
    assert total > 100  # the random catalogs do produce compatible builds


def test_criteria_and_ranking():
    rng = random.Random(3)
    domains = random_catalog(rng)
    builds = list(compatible_builds(domains, D(10**6)))
    assert builds
    for purpose in WEIGHTS:
        scores = rank_builds(builds, purpose)
        assert sorted(s.index for s in scores) == list(range(len(builds)))
        assert all(a.closeness >= b.closeness for a, b in zip(scores, scores[1:]))
    build = builds[0]
    price, performance, power = criteria(build, "gaming")
    assert price == sum(x.price for x in build.values() if x)
    gpu = build[Category.GPU]
    assert performance == pytest.approx(0.5 * float(build[Category.CPU].part.component.perf_score)
                                        + 0.5 * (float(gpu.part.component.perf_score) if gpu else 0))
    assert power == sum(x.part.component.power_draw_w for c, x in build.items() if x and c != Category.PSU)


# ---------- Endpoint ----------

@pytest.mark.parametrize("body", [
    {"budget_mdl": 30000},
    {"budget_mdl": 0, "purpose": "gaming"},
    {"budget_mdl": 30000, "purpose": "mining"},
    {"budget_mdl": 30000, "purpose": "gaming", "cpu_brand": "VIA"},
    {"budget_mdl": 30000, "purpose": "gaming", "extra": 1},
])
def test_invalid_recommendation_requests(client, body):
    assert client.post("/recommendations", json=body).status_code == 422


def test_recommendations_are_compatible_and_within_budget(catalog_client):
    client, _ = catalog_client
    response = client.post("/recommendations", json={"budget_mdl": 30000, "purpose": "gaming", "cpu_brand": "AMD"})
    assert response.status_code == 200
    body = response.json()
    assert body["weights"] == {"price": 0.35, "performance": 0.5, "power": 0.15}
    assert body["alternatives"] >= len(body["builds"]) > 0
    assert 1 in [b["rank"] for b in body["builds"]] and len(body["builds"]) <= 6
    prices = [D(b["price_mdl"]) for b in body["builds"]]
    assert prices == sorted(prices)  # cheapest first
    def chips(build):
        cpu = client.get(f"/components/{build['components']['cpu']}").json()
        gpu_id = build["components"]["gpu"]
        gpu = client.get(f"/components/{gpu_id}").json()["specs"]["chipset"] if gpu_id else None
        return cpu_chip(cpu["model"]) or cpu["model"], gpu
    pairs = [chips(b) for b in body["builds"]]
    assert len(set(pairs)) == len(pairs)
    for build in body["builds"]:
        assert D(build["price_mdl"]) <= 30000
        selection = {c: i for c, i in build["components"].items() if i is not None}
        check = client.post("/compatibility/check", json={"components": selection}).json()
        assert check["status"] == "compatible"
        assert check["estimated_power_w"] == build["power_w"]
        cpu = client.get(f"/components/{selection['cpu']}").json()
        assert cpu["brand"] == "AMD"


def test_no_build_fits_a_tiny_budget(catalog_client):
    client, _ = catalog_client
    body = client.post("/recommendations", json={"budget_mdl": 1000, "purpose": "office"}).json()
    assert body["alternatives"] == 0 and body["builds"] == []


# ---------- Which builds are shown ----------

def test_spread_by_price_takes_the_best_of_each_band():
    from app.services.recommend import spread_by_price
    from app.services.topsis import TopsisScore
    # Index = build. Cheapest 0, budget 600 -> six bands of 100 lei.
    prices = [D(p) for p in (0, 60, 150, 250, 350, 450, 590, 120)]
    pairs = [("A", "X"), ("B", "X"), ("C", "X"), ("A", "X"), ("D", "Y"), ("E", "Y"), ("F", "Z"), ("G", "Z")]
    order = [3, 0, 1, 7, 2, 4, 5, 6]  # ranks: build 3 is first, then 0, 1, 7, ...
    scores = [TopsisScore(i, 0, 0, 1 - k / 10) for k, i in enumerate(order)]
    shown = spread_by_price(scores, prices, pairs, D(600))
    # Band 2 (200-300): build 3, rank 1. Band 0: build 0 shares pair A/X with build 3, so build 1.
    # Band 1 (100-200): build 7 (rank 4) beats build 2 (rank 5). Bands 3, 4, 5: builds 4, 5, 6.
    assert [s.index for _, s in shown] == [1, 7, 3, 4, 5, 6]
    assert [rank for rank, _ in shown] == [3, 4, 1, 6, 7, 8]


def test_spread_by_price_fills_empty_bands_with_new_pairs():
    from app.services.recommend import spread_by_price
    from app.services.topsis import TopsisScore
    prices = [D(p) for p in (100, 101, 102, 103, 104, 105, 106, 990)]
    pairs = [(c, None) for c in "ABCDEFGA"]
    scores = [TopsisScore(i, 0, 0, 1 - i / 10) for i in range(8)]
    shown = spread_by_price(scores, prices, pairs, D(1000))
    assert len(shown) == 6 and len({pairs[s.index] for _, s in shown}) == 6
    assert spread_by_price([], [], [], D(1000)) == []


def test_spread_by_price_never_repeats_a_pair_with_a_gpu():
    from app.services.recommend import spread_by_price
    from app.services.topsis import TopsisScore
    # Two gaming pairs, each in builds that differ only in RAM or storage size: two shown.
    prices = [D(p) for p in (100, 200, 300, 400)]
    pairs = [("A", "X"), ("A", "X"), ("A", "Y"), ("A", "Y")]
    setups = [pair + (size,) for pair, size in zip(pairs, (16, 32, 16, 32))]
    scores = [TopsisScore(i, 0, 0, 1 - i / 10) for i in range(4)]
    shown = spread_by_price(scores, prices, pairs, D(1000), setups=setups)
    assert [s.index for _, s in shown] == [0, 2]
    # Without a GPU (office), another RAM or storage size does count as a variant.
    office = [("A", None)] * 4
    setups = [pair + (size,) for pair, size in zip(office, (16, 32, 16, 64))]
    shown = spread_by_price(scores, prices, office, D(1000), setups=setups)
    assert [s.index for _, s in shown] == [0, 1, 3]
