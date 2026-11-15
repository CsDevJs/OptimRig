"""Rule boundaries use explicit synthetic parts; endpoint tests use PostgreSQL."""

import pytest
from sqlalchemy import func, select

from app.db.models import (
    CaseSpec, Category, Component, CoolerSpec, CpuSpec, GpuSpec,
    MotherboardSpec, PsuSpec, RamSpec, Slot, StorageSpec,
)
from app.compatibility_schemas import CompatibilityRequest
from app.services.compatibility import SelectedPart, check_build, check_pair


@pytest.fixture
def parts():
    specs = {
        Category.CPU: CpuSpec(socket="AM4", memory_types=["DDR4"], tdp_w=65,
                             includes_cooler=True, integrated_graphics=True),
        Category.MOTHERBOARD: MotherboardSpec(socket="AM4", memory_type="DDR4",
            form_factor="ATX", memory_slots=4, max_memory_gb=128, m2_slots=2, sata_ports=4),
        Category.RAM: RamSpec(memory_type="DDR4", capacity_gb=32, modules=2),
        Category.GPU: GpuSpec(length_mm=250, recommended_psu_w=500),
        Category.STORAGE: StorageSpec(storage_type="nvme", form_factor="M.2 2280"),
        Category.PSU: PsuSpec(wattage=650, form_factor="ATX"),
        Category.CASE: CaseSpec(supported_board_form_factors=["ATX", "Micro-ATX"],
            max_gpu_length_mm=300, max_cooler_height_mm=160, max_radiator_mm=360,
            psu_form_factor="ATX"),
        Category.COOLER: CoolerSpec(cooler_type="air", height_mm=150,
            supported_sockets=["AM4"], max_tdp_w=150),
    }
    power = [100, 40, 10, 200, 10, 999, 5, 5]
    return {category: SelectedPart(
        Component(id=index + 1, category=category, power_draw_w=power[index]), spec,
    ) for index, (category, spec) in enumerate(specs.items())}


def issue_codes(result, severity=None):
    return {issue.code for issue in result.issues if severity is None or issue.severity == severity}


def test_complete_build_and_power_policy(parts):
    result = check_build(parts)
    assert result.status == "compatible"
    assert result.missing_categories == []
    assert issue_codes(result, "error") == set()
    assert result.estimated_power_w == 370  # excludes PSU's deliberately nonzero draw
    assert result.recommended_psu_w == 500  # max(ceil(370 * 1.2), GPU recommendation)
    assert "cpu_socket" in result.checked_rules
    assert "psu_capacity" in result.checked_rules
    assert result.limitations


@pytest.mark.parametrize("category,field,value,code", [
    (Category.MOTHERBOARD, "socket", "LGA1700", "cpu_socket"),
    (Category.MOTHERBOARD, "memory_type", "DDR5", "cpu_board_memory"),
    (Category.RAM, "memory_type", "DDR5", "cpu_ram_memory"),
    (Category.RAM, "memory_type", "DDR5", "board_ram_memory"),
    (Category.RAM, "modules", 5, "ram_slots"),
    (Category.RAM, "capacity_gb", 129, "ram_capacity"),
    (Category.MOTHERBOARD, "form_factor", "E-ATX", "board_case_size"),
    (Category.GPU, "length_mm", 301, "gpu_length"),
    (Category.COOLER, "supported_sockets", ["LGA1700"], "cooler_socket"),
    (Category.COOLER, "height_mm", 161, "cooler_height"),
    (Category.MOTHERBOARD, "m2_slots", 0, "storage_m2_slot"),
    (Category.PSU, "wattage", 369, "psu_capacity"),
])
def test_hard_conflicts_include_component_ids(parts, category, field, value, code):
    setattr(parts[category].spec, field, value)
    result = check_build(parts)
    assert result.status == "incompatible"
    issue = next(issue for issue in result.issues if issue.code == code)
    assert issue.severity == "error" and issue.component_ids and issue.message
    assert parts[category].component.id in issue.component_ids


def test_dimension_capacity_and_power_boundaries_are_inclusive(parts):
    parts[Category.GPU].spec.length_mm = 300
    parts[Category.COOLER].spec.height_mm = 160
    parts[Category.RAM].spec.modules = 4
    parts[Category.RAM].spec.capacity_gb = 128
    parts[Category.PSU].spec.wattage = 370
    result = check_build(parts)
    assert result.status == "compatible"
    assert "psu_headroom" in issue_codes(result, "warning")
    assert not issue_codes(result, "error")


def test_psu_headroom_rounding(parts):
    parts.pop(Category.GPU)
    parts[Category.CPU].component.power_draw_w = 101
    result = check_build(parts)
    assert result.estimated_power_w == 171
    assert result.recommended_psu_w == 206  # ceil(205.2)
    parts[Category.PSU].spec.wattage = 206
    assert "psu_headroom" not in issue_codes(check_build(parts))
    parts[Category.PSU].spec.wattage = 205
    assert "psu_headroom" in issue_codes(check_build(parts), "warning")


def test_partial_build_does_not_claim_compatibility(parts):
    result = check_build({Category.CPU: parts[Category.CPU]})
    assert result.status == "incomplete"
    assert set(result.missing_categories) == {
        Category.MOTHERBOARD, Category.RAM, Category.STORAGE, Category.PSU, Category.CASE,
    }
    assert result.estimated_power_w == 100


def test_conflict_takes_precedence_over_incomplete(parts):
    parts[Category.MOTHERBOARD].spec.socket = "LGA1700"
    result = check_build({category: parts[category] for category in (Category.CPU, Category.MOTHERBOARD)})
    assert result.status == "incompatible"
    assert result.missing_categories


def test_graphics_and_cooling_depend_on_cpu(parts):
    parts.pop(Category.GPU)
    parts.pop(Category.COOLER)
    assert check_build(parts).status == "compatible"  # iGPU and boxed cooler
    parts[Category.CPU].spec.integrated_graphics = False
    parts[Category.CPU].spec.includes_cooler = False
    result = check_build(parts)
    assert result.status == "incomplete"
    assert set(result.missing_categories) == {Category.GPU, Category.COOLER}


@pytest.mark.parametrize("category", list(Category))
def test_missing_specs_are_unknown_not_a_pass(parts, category):
    parts[category] = SelectedPart(parts[category].component, None)
    result = check_build(parts)
    assert result.status == "undetermined"
    assert "specifications_missing" in issue_codes(result, "warning")


@pytest.mark.parametrize("category,field", [
    (Category.CPU, "memory_types"),
    (Category.CASE, "supported_board_form_factors"),
    (Category.COOLER, "supported_sockets"),
])
def test_empty_supported_lists_are_unknown(parts, category, field):
    setattr(parts[category].spec, field, [])
    assert check_build(parts).status == "undetermined"


def test_cpu_that_supports_two_memory_types_still_needs_matching_board_and_ram(parts):
    parts[Category.CPU].spec.memory_types = ["DDR4", "DDR5"]
    parts[Category.RAM].spec.memory_type = "DDR5"
    result = check_build(parts)
    assert issue_codes(result, "error") == {"board_ram_memory"}


@pytest.mark.parametrize("category", [Category.CPU, Category.MOTHERBOARD])
def test_blank_socket_is_unknown(parts, category):
    parts[category].spec.socket = " "
    result = check_build(parts)
    assert result.status == "undetermined"
    assert not issue_codes(result, "error")


@pytest.mark.parametrize("radiator,maximum,status,code", [
    (420, 360, "incompatible", "radiator_size"),
    (360, 360, "undetermined", "radiator_mounts_unverified"),
    (280, 360, "undetermined", "radiator_mounts_unverified"),
    (240, None, "incompatible", "case_radiator_unsupported"),
    (240, 0, "incompatible", "radiator_size"),
    (None, 360, "undetermined", "radiator_size_unknown"),
])
def test_aio_does_not_infer_mounts_from_a_maximum(parts, radiator, maximum, status, code):
    parts[Category.COOLER].spec.cooler_type = "aio"
    parts[Category.COOLER].spec.radiator_mm = radiator
    parts[Category.CASE].spec.max_radiator_mm = maximum
    result = check_build(parts)
    assert result.status == status
    assert code in issue_codes(result)


def test_unknown_air_cooler_height(parts):
    parts[Category.COOLER].spec.height_mm = None
    assert check_build(parts).status == "undetermined"


@pytest.mark.parametrize("rating", [None, 64])
def test_thermal_ratings_are_advisory(parts, rating):
    parts[Category.COOLER].spec.max_tdp_w = rating
    result = check_build(parts)
    assert result.status == "compatible"
    assert any(issue.code.startswith("cooler_") and issue.severity == "warning" for issue in result.issues)


def test_psu_form_factor_difference_requires_manual_check(parts):
    parts[Category.PSU].spec.form_factor = "SFX"
    result = check_build(parts)
    assert result.status == "undetermined"
    assert "psu_case_size" in issue_codes(result, "warning")


def test_sata_port_required(parts):
    parts[Category.STORAGE].spec.storage_type = "sata_ssd"
    parts[Category.STORAGE].spec.form_factor = "2.5"
    parts[Category.MOTHERBOARD].spec.sata_ports = 0
    assert "storage_sata_port" in issue_codes(check_build(parts), "error")


def test_m2_sata_protocol_is_unverified(parts):
    parts[Category.STORAGE].spec.storage_type = "sata_ssd"
    assert check_build(parts).status == "undetermined"
    assert "storage_m2_sata_protocol" in issue_codes(check_build(parts), "warning")


def test_non_m2_nvme_does_not_assume_m2_slot(parts):
    parts[Category.STORAGE].spec.form_factor = "U.2"
    parts[Category.MOTHERBOARD].spec.m2_slots = 0
    result = check_build(parts)
    assert result.status == "undetermined"
    assert "storage_m2_slot" not in issue_codes(result, "error")


def test_pair_rules_are_symmetric_and_report_missing_data(parts):
    cpu, board = parts[Category.CPU], parts[Category.MOTHERBOARD]
    board.spec.socket = "LGA1700"
    assert check_pair(cpu, board) == check_pair(board, cpu)
    assert check_pair(cpu, SelectedPart(board.component, None))[2] is True


def test_input_order_does_not_change_report(parts):
    parts[Category.CPU] = SelectedPart(parts[Category.CPU].component, None)
    parts[Category.RAM] = SelectedPart(parts[Category.RAM].component, None)
    assert check_build(parts) == check_build(dict(reversed(list(parts.items()))))


@pytest.mark.parametrize("payload", [
    {}, {"components": {}}, {"components": {"cpu": 0}},
    {"components": {"cpu": -1}}, {"components": {"cpu": True}},
    {"components": {"cpu": "1"}}, {"components": {"cpu": 1.5}},
    {"components": {"invalid": 1}}, {"components": {"cpu": 1, "ram": 1}},
    {"components": {"cpu": 1}, "unexpected": True},
])
def test_invalid_requests(client, payload):
    assert client.post("/compatibility/check", json=payload).status_code == 422


def test_endpoint_loads_catalog_specs_and_explains_conflict(catalog_client):
    client, db = catalog_client
    components = db.scalars(select(Component)).all()
    by_slug = {component.slug: component for component in components}
    cpu = by_slug["amd-ryzen-5-5500"]
    board = by_slug["gigabyte-b760m-h-ddr4"]
    response = client.post("/compatibility/check", json={"components": {
        "cpu": cpu.id, "motherboard": board.id,
    }})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "incompatible"
    conflict = next(issue for issue in body["issues"] if issue["code"] == "cpu_socket")
    assert conflict["component_ids"] == [cpu.id, board.id]
    assert "AM4" in conflict["message"] and "LGA1700" in conflict["message"]


def test_endpoint_partial_missing_and_wrong_category(catalog_client):
    client, db = catalog_client
    cpu = db.scalar(select(Component).where(Component.category == Category.CPU).order_by(Component.id))
    response = client.post("/compatibility/check", json={"components": {"cpu": cpu.id}})
    assert response.status_code == 200
    assert response.json()["status"] == "incomplete"
    missing_id = db.scalar(select(func.max(Component.id))) + 1
    response = client.post("/compatibility/check", json={"components": {"cpu": missing_id}})
    assert response.status_code == 404
    assert response.json()["detail"]["component_ids"] == [missing_id]
    response = client.post("/compatibility/check", json={"components": {"ram": cpu.id}})
    assert response.status_code == 422
    assert response.json()["detail"]["mismatches"] == [{
        "component_id": cpu.id, "expected": "ram", "actual": "cpu",
    }]


def test_endpoint_reports_missing_catalog_spec(catalog_client):
    client, db = catalog_client
    component = Component(slug="test-cpu-without-spec", brand="Test", model="No spec",
                          category=Category.CPU, tier="low", power_draw_w=0)
    db.add(component)
    db.flush()
    response = client.post("/compatibility/check", json={"components": {"cpu": component.id}})
    assert response.status_code == 200
    assert any(issue["code"] == "specifications_missing" for issue in response.json()["issues"])


def test_endpoint_checks_complete_seeded_build(catalog_client):
    client, db = catalog_client
    slugs = [
        "amd-ryzen-5-5500", "gigabyte-b550m-ds3h-r2", "kingston-kf432c16bbk2-16",
        "gigabyte-rtx-5050-windforce-oc-8g", "kingston-a400-480gb",
        "be-quiet-system-power-11-650w", "deepcool-cc560-v2-black", "deepcool-ag400-led",
    ]
    components = db.scalars(select(Component).where(Component.slug.in_(slugs))).all()
    assert len(components) == 8
    response = client.post("/compatibility/check", json={"components": {
        part.category.value: part.id for part in components
    }})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "compatible"
    assert body["missing_categories"] == []
    assert not [issue for issue in body["issues"] if issue["severity"] == "error"]
    assert body["estimated_power_w"] == sum(part.power_draw_w for part in components if part.category != Category.PSU)


def _extra(slot, component_id, spec):
    return {slot: SelectedPart(Component(id=component_id, category=slot.category, power_draw_w=5), spec)}


def test_extra_ram_kits_share_the_board_slots_and_capacity(parts):
    # The 2x32 GB kit plus an identical one fill the board's 4 slots and stay under 128 GB.
    twin = check_build({**parts, Slot.RAM2: parts[Category.RAM]})
    assert twin.status == "compatible" and {"ram_slots_total", "ram_capacity_total"} <= set(twin.checked_rules)
    third = _extra(Slot.RAM3, 50, RamSpec(memory_type="DDR4", capacity_gb=16, modules=1))
    over = check_build({**parts, Slot.RAM2: parts[Category.RAM], **third})
    assert "ram_slots_total" in issue_codes(over, "error")
    big = _extra(Slot.RAM2, 51, RamSpec(memory_type="DDR4", capacity_gb=128, modules=2))
    assert "ram_capacity_total" in issue_codes(check_build({**parts, **big}), "error")


def test_ram_kits_must_be_one_memory_type(parts):
    ddr5 = _extra(Slot.RAM2, 52, RamSpec(memory_type="DDR5", capacity_gb=32, modules=2))
    without_board = {k: v for k, v in parts.items() if k != Category.MOTHERBOARD}
    result = check_build({**without_board, **ddr5})
    assert "ram_kits_memory" in issue_codes(result, "error")
    _, issues, _ = check_pair(parts[Category.RAM], ddr5[Slot.RAM2])
    assert [i.code for i in issues] == ["ram_kits_memory"]


def test_drives_beyond_two_need_connectors(parts):
    m2 = parts[Category.STORAGE]
    ok = check_build({**parts, Slot.STORAGE2: m2})
    assert ok.status == "compatible"
    over = check_build({**parts, Slot.STORAGE2: m2, Slot.STORAGE3: m2})
    assert "storage_m2_count" in issue_codes(over, "error")
    sata = _extra(Slot.STORAGE3, 53, StorageSpec(storage_type="sata", form_factor="2.5\""))
    assert check_build({**parts, Slot.STORAGE2: m2, **sata}).status == "compatible"


def test_ids_may_repeat_only_within_ram_or_storage():
    assert CompatibilityRequest(components={"ram": 3, "ram2": 3, "storage": 5, "storage4": 5})
    with pytest.raises(ValueError):
        CompatibilityRequest(components={"ram": 3, "storage": 3})

