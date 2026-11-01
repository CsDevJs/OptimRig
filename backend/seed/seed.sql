-- PC Configurator catalog seed data.
-- Prices, availability and URLs were checked by hand on the store websites on 2026-10-21.
--
-- Run after `alembic upgrade head`, either:
--   * from backend/:  .venv\Scripts\python -m scripts.seed
--   * or paste this whole file into pgAdmin's Query Tool (connected to pc_configurator) and press F5.
-- Safe to re-run: every row is upserted by its natural key (slug, or component + store for offers).
-- Parts and specs: edit the rows here and run the file again.
-- Prices, sales and stock: the prices below are only the starting values for NEW offers.
-- For offers that already exist, `python -m scripts.check_offers` keeps them up to date,
-- and re-running this file does not overwrite them (it only updates the URL).

BEGIN;

-- ===== Stores =====
INSERT INTO stores (slug, name, website) VALUES
    ('xstore', 'Xstore', 'https://xstore.md'),
    ('neocomputer', 'NeoComputer', 'https://neocomputer.md'),
    ('darwin', 'Darwin', 'https://darwin.md'),
    ('ultra', 'Ultra', 'https://ultra.md'),
    ('primepc', 'PrimePC', 'https://prime-pc.md')
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    website = EXCLUDED.website;

-- ===== CPUs =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('amd-ryzen-5-5500', 'cpu', 'low', 'AMD', 'Ryzen 5 5500 (Tray)', 48, 'estimate: relative gaming performance, Ryzen 7 9800X3D = 100', 88, 2022),
    ('intel-core-i3-12100f', 'cpu', 'low', 'Intel', 'Core i3-12100F (Tray)', 50, 'estimate: relative gaming performance, Ryzen 7 9800X3D = 100', 89, 2022),
    ('amd-ryzen-5-7600', 'cpu', 'mid', 'AMD', 'Ryzen 5 7600 (Tray)', 72, 'estimate: relative gaming performance, Ryzen 7 9800X3D = 100', 88, 2023),
    ('intel-core-i5-14400f', 'cpu', 'mid', 'Intel', 'Core i5-14400F (Tray)', 68, 'estimate: relative gaming performance, Ryzen 7 9800X3D = 100', 148, 2024),
    ('amd-ryzen-7-9800x3d', 'cpu', 'high', 'AMD', 'Ryzen 7 9800X3D (Tray)', 100, 'estimate: relative gaming performance, Ryzen 7 9800X3D = 100', 162, 2024),
    ('intel-core-ultra-7-265k', 'cpu', 'high', 'Intel', 'Core Ultra 7 265K (Tray)', 80, 'estimate: relative gaming performance, Ryzen 7 9800X3D = 100', 250, 2024)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO cpu_specs (component_id, socket, cores, threads, base_clock_ghz, boost_clock_ghz, tdp_w, integrated_graphics, memory_types, includes_cooler) VALUES
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-5500'), 'AM4', 6, 12, 3.6, 4.2, 65, false, ARRAY['DDR4'], false),
    ((SELECT id FROM components WHERE slug = 'intel-core-i3-12100f'), 'LGA1700', 4, 8, 3.3, 4.3, 58, false, ARRAY['DDR4', 'DDR5'], false),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-7600'), 'AM5', 6, 12, 3.8, 5.1, 65, true, ARRAY['DDR5'], false),
    ((SELECT id FROM components WHERE slug = 'intel-core-i5-14400f'), 'LGA1700', 10, 16, 2.5, 4.7, 65, false, ARRAY['DDR4', 'DDR5'], false),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-7-9800x3d'), 'AM5', 8, 16, 4.7, 5.2, 120, true, ARRAY['DDR5'], false),
    ((SELECT id FROM components WHERE slug = 'intel-core-ultra-7-265k'), 'LGA1851', 20, 20, 3.9, 5.5, 125, true, ARRAY['DDR5'], false)
ON CONFLICT (component_id) DO UPDATE SET
    socket = EXCLUDED.socket,
    cores = EXCLUDED.cores,
    threads = EXCLUDED.threads,
    base_clock_ghz = EXCLUDED.base_clock_ghz,
    boost_clock_ghz = EXCLUDED.boost_clock_ghz,
    tdp_w = EXCLUDED.tdp_w,
    integrated_graphics = EXCLUDED.integrated_graphics,
    memory_types = EXCLUDED.memory_types,
    includes_cooler = EXCLUDED.includes_cooler;

-- ===== Motherboards =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('gigabyte-b550m-ds3h-r2', 'motherboard', 'low', 'Gigabyte', 'B550M DS3H R2', NULL, NULL, 40, 2024),
    ('gigabyte-b760m-h-ddr4', 'motherboard', 'low', 'Gigabyte', 'B760M H DDR4', NULL, NULL, 40, 2023),
    ('gigabyte-b650m-d3hp', 'motherboard', 'mid', 'Gigabyte', 'B650M D3HP', NULL, NULL, 45, 2023),
    ('asus-tuf-gaming-b760-plus-wifi', 'motherboard', 'mid', 'ASUS', 'TUF GAMING B760-PLUS WIFI', NULL, NULL, 50, 2023),
    ('gigabyte-x870e-aorus-elite-wifi7', 'motherboard', 'high', 'Gigabyte', 'X870E AORUS ELITE WIFI7', NULL, NULL, 60, 2024),
    ('asus-tuf-gaming-z890-plus-wifi', 'motherboard', 'high', 'ASUS', 'TUF GAMING Z890-PLUS WIFI', NULL, NULL, 60, 2024)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO motherboard_specs (component_id, socket, chipset, form_factor, memory_type, memory_slots, max_memory_gb, m2_slots, sata_ports, wifi) VALUES
    ((SELECT id FROM components WHERE slug = 'gigabyte-b550m-ds3h-r2'), 'AM4', 'B550', 'Micro-ATX', 'DDR4', 4, 128, 2, 4, false),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b760m-h-ddr4'), 'LGA1700', 'B760', 'Micro-ATX', 'DDR4', 2, 64, 2, 4, false),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b650m-d3hp'), 'AM5', 'B650', 'Micro-ATX', 'DDR5', 4, 256, 2, 4, false),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-b760-plus-wifi'), 'LGA1700', 'B760', 'ATX', 'DDR5', 4, 192, 3, 4, true),
    ((SELECT id FROM components WHERE slug = 'gigabyte-x870e-aorus-elite-wifi7'), 'AM5', 'X870E', 'ATX', 'DDR5', 4, 256, 4, 4, true),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-z890-plus-wifi'), 'LGA1851', 'Z890', 'ATX', 'DDR5', 4, 256, 4, 4, true)
ON CONFLICT (component_id) DO UPDATE SET
    socket = EXCLUDED.socket,
    chipset = EXCLUDED.chipset,
    form_factor = EXCLUDED.form_factor,
    memory_type = EXCLUDED.memory_type,
    memory_slots = EXCLUDED.memory_slots,
    max_memory_gb = EXCLUDED.max_memory_gb,
    m2_slots = EXCLUDED.m2_slots,
    sata_ports = EXCLUDED.sata_ports,
    wifi = EXCLUDED.wifi;

-- ===== RAM kits =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('kingston-kf432c16bbk2-16', 'ram', 'low', 'Kingston', 'FURY Beast KF432C16BBK2/16 (2x8GB DDR4-3200 CL16)', NULL, NULL, 6, NULL),
    ('kingston-kf556c36bbek2-16', 'ram', 'low', 'Kingston', 'FURY Beast KF556C36BBEK2-16 (2x8GB DDR5-5600 CL36)', NULL, NULL, 8, NULL),
    ('kingston-kf432c16bb1k2-32', 'ram', 'mid', 'Kingston', 'FURY Beast KF432C16BB1K2/32 (2x16GB DDR4-3200 CL16)', NULL, NULL, 8, NULL),
    ('kingston-kf560c36bbe2ak2-32', 'ram', 'mid', 'Kingston', 'FURY Beast RGB KF560C36BBE2AK2-32 (2x16GB DDR5-6000 CL36)', NULL, NULL, 10, NULL),
    ('kingston-kf568c34bbeak2-32', 'ram', 'high', 'Kingston', 'FURY Beast RGB KF568C34BBEAK2-32 (2x16GB DDR5-6800 CL34)', NULL, NULL, 10, NULL),
    ('kingston-kf560c30bbeak2-64', 'ram', 'high', 'Kingston', 'FURY Beast RGB KF560C30BBEAK2-64 (2x32GB DDR5-6000 CL30)', NULL, NULL, 12, NULL)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO ram_specs (component_id, memory_type, capacity_gb, modules, speed_mts, cas_latency) VALUES
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bbk2-16'), 'DDR4', 16, 2, 3200, 16),
    ((SELECT id FROM components WHERE slug = 'kingston-kf556c36bbek2-16'), 'DDR5', 16, 2, 5600, 36),
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bb1k2-32'), 'DDR4', 32, 2, 3200, 16),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c36bbe2ak2-32'), 'DDR5', 32, 2, 6000, 36),
    ((SELECT id FROM components WHERE slug = 'kingston-kf568c34bbeak2-32'), 'DDR5', 32, 2, 6800, 34),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c30bbeak2-64'), 'DDR5', 64, 2, 6000, 30)
ON CONFLICT (component_id) DO UPDATE SET
    memory_type = EXCLUDED.memory_type,
    capacity_gb = EXCLUDED.capacity_gb,
    modules = EXCLUDED.modules,
    speed_mts = EXCLUDED.speed_mts,
    cas_latency = EXCLUDED.cas_latency;

-- ===== Graphics cards =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('gigabyte-rtx-5050-windforce-oc-8g', 'gpu', 'low', 'Gigabyte', 'GeForce RTX 5050 WINDFORCE OC 8G (GV-N5050WF2OC-8GD)', 25, 'estimate: relative 1440p raster performance, RTX 5090 = 100', 130, 2025),
    ('gigabyte-rx-9060-xt-gaming-oc-8g', 'gpu', 'low', 'Gigabyte', 'Radeon RX 9060 XT GAMING OC 8G (GV-R9060XTGAMING OC-8GD)', 35, 'estimate: relative 1440p raster performance, RTX 5090 = 100', 150, 2025),
    ('asus-dual-rtx-5060-ti-o16g', 'gpu', 'mid', 'ASUS', 'Dual GeForce RTX 5060 Ti OC Edition 16GB (DUAL-RTX5060TI-O16G)', 38, 'estimate: relative 1440p raster performance, RTX 5090 = 100', 180, 2025),
    ('gigabyte-rx-9060-xt-gaming-oc-16g', 'gpu', 'mid', 'Gigabyte', 'Radeon RX 9060 XT GAMING OC 16G (GV-R9060XTGAMING OC-16GD)', 37, 'estimate: relative 1440p raster performance, RTX 5090 = 100', 160, 2025),
    ('gigabyte-rtx-5070-ti-windforce-oc-16g', 'gpu', 'high', 'Gigabyte', 'GeForce RTX 5070 Ti WINDFORCE OC 16G (GV-N507TWF3OC-16GD)', 60, 'estimate: relative 1440p raster performance, RTX 5090 = 100', 300, 2025),
    ('gigabyte-rx-9070-xt-gaming-oc-16g', 'gpu', 'high', 'Gigabyte', 'Radeon RX 9070 XT GAMING OC 16G (GV-R9070XTGAMING OC-16GD)', 60, 'estimate: relative 1440p raster performance, RTX 5090 = 100', 340, 2025)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO gpu_specs (component_id, chipset, vram_gb, length_mm, slot_width, tdp_w, recommended_psu_w, power_connectors) VALUES
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5050-windforce-oc-8g'), 'GeForce RTX 5050', 8, 199, 2.0, 130, 550, '1x 8-pin'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-8g'), 'Radeon RX 9060 XT', 8, 281, 2.0, 150, 450, '1x 8-pin'),
    ((SELECT id FROM components WHERE slug = 'asus-dual-rtx-5060-ti-o16g'), 'GeForce RTX 5060 Ti', 16, 229, 2.5, 180, 550, '1x 8-pin'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-16g'), 'Radeon RX 9060 XT', 16, 281, 2.0, 160, 450, '1x 8-pin'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5070-ti-windforce-oc-16g'), 'GeForce RTX 5070 Ti', 16, 304, 2.5, 300, 750, '1x 16-pin'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9070-xt-gaming-oc-16g'), 'Radeon RX 9070 XT', 16, 288, 2.8, 340, 850, '3x 8-pin')
ON CONFLICT (component_id) DO UPDATE SET
    chipset = EXCLUDED.chipset,
    vram_gb = EXCLUDED.vram_gb,
    length_mm = EXCLUDED.length_mm,
    slot_width = EXCLUDED.slot_width,
    tdp_w = EXCLUDED.tdp_w,
    recommended_psu_w = EXCLUDED.recommended_psu_w,
    power_connectors = EXCLUDED.power_connectors;

-- ===== Storage =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('kingston-a400-480gb', 'storage', 'low', 'Kingston', 'A400 480GB (SA400S37/480G)', NULL, NULL, 3, 2017),
    ('kingston-nv3-1tb', 'storage', 'low', 'Kingston', 'NV3 1TB (SNV3S/1000G)', NULL, NULL, 6, 2024),
    ('samsung-990-evo-plus-1tb', 'storage', 'mid', 'Samsung', '990 EVO Plus 1TB (MZ-V9S1T0BW)', NULL, NULL, 6, 2024),
    ('kingston-nv3-2tb', 'storage', 'mid', 'Kingston', 'NV3 2TB (SNV3S/2000G)', NULL, NULL, 6, 2024),
    ('samsung-990-pro-2tb', 'storage', 'high', 'Samsung', '990 PRO 2TB (MZ-V9P2T0BW)', NULL, NULL, 8, 2022),
    ('samsung-990-pro-4tb', 'storage', 'high', 'Samsung', '990 PRO 4TB (MZ-V9P4T0BW)', NULL, NULL, 8, 2023)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO storage_specs (component_id, storage_type, interface, form_factor, capacity_gb, read_mbps, write_mbps) VALUES
    ((SELECT id FROM components WHERE slug = 'kingston-a400-480gb'), 'sata_ssd', 'SATA III', '2.5', 480, 500, 450),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-1tb'), 'nvme', 'PCIe 4.0 x4', 'M.2 2280', 1000, 6000, 4000),
    ((SELECT id FROM components WHERE slug = 'samsung-990-evo-plus-1tb'), 'nvme', 'PCIe 4.0 x4', 'M.2 2280', 1000, 7150, 6300),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-2tb'), 'nvme', 'PCIe 4.0 x4', 'M.2 2280', 2000, 6000, 5000),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-2tb'), 'nvme', 'PCIe 4.0 x4', 'M.2 2280', 2000, 7450, 6900),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-4tb'), 'nvme', 'PCIe 4.0 x4', 'M.2 2280', 4000, 7450, 6900)
ON CONFLICT (component_id) DO UPDATE SET
    storage_type = EXCLUDED.storage_type,
    interface = EXCLUDED.interface,
    form_factor = EXCLUDED.form_factor,
    capacity_gb = EXCLUDED.capacity_gb,
    read_mbps = EXCLUDED.read_mbps,
    write_mbps = EXCLUDED.write_mbps;

-- ===== Power supplies =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('be-quiet-system-power-11-650w', 'psu', 'low', 'be quiet!', 'System Power 11 650W (BP011EU)', NULL, NULL, 0, 2024),
    ('cougar-atlas-750', 'psu', 'low', 'Cougar', 'Atlas 750', NULL, NULL, 0, NULL),
    ('cougar-gex-pro-750', 'psu', 'mid', 'Cougar', 'GEX PRO 750', NULL, NULL, 0, NULL),
    ('cougar-gex-pro-850', 'psu', 'mid', 'Cougar', 'GEX PRO 850', NULL, NULL, 0, NULL),
    ('asus-rog-strix-850w-platinum', 'psu', 'high', 'ASUS', 'ROG Strix 850W Platinum', NULL, NULL, 0, 2024),
    ('be-quiet-pure-power-13-m-1000w', 'psu', 'high', 'be quiet!', 'Pure Power 13 M 1000W (BP028EU)', NULL, NULL, 0, 2024)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO psu_specs (component_id, wattage, efficiency, modular, form_factor, has_16pin) VALUES
    ((SELECT id FROM components WHERE slug = 'be-quiet-system-power-11-650w'), 650, '80+ Bronze', 'none', 'ATX', true),
    ((SELECT id FROM components WHERE slug = 'cougar-atlas-750'), 750, '80+ Bronze', 'none', 'ATX', false),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-750'), 750, '80+ Gold', 'full', 'ATX', true),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-850'), 850, '80+ Gold', 'full', 'ATX', true),
    ((SELECT id FROM components WHERE slug = 'asus-rog-strix-850w-platinum'), 850, '80+ Platinum', 'full', 'ATX', true),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-power-13-m-1000w'), 1000, '80+ Gold', 'full', 'ATX', true)
ON CONFLICT (component_id) DO UPDATE SET
    wattage = EXCLUDED.wattage,
    efficiency = EXCLUDED.efficiency,
    modular = EXCLUDED.modular,
    form_factor = EXCLUDED.form_factor,
    has_16pin = EXCLUDED.has_16pin;

-- ===== Cases =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('deepcool-cc560-v2-black', 'case', 'low', 'DeepCool', 'CC560 V2 Black', NULL, NULL, 12, 2024),
    ('deepcool-ch360-white', 'case', 'low', 'DeepCool', 'CH360 White', NULL, NULL, 9, 2023),
    ('deepcool-ch560-black', 'case', 'mid', 'DeepCool', 'CH560 Black', NULL, NULL, 12, 2023),
    ('be-quiet-pure-base-501-lx-white', 'case', 'mid', 'be quiet!', 'Pure Base 501 LX White', NULL, NULL, 12, 2025),
    ('be-quiet-light-base-600-lx-white', 'case', 'high', 'be quiet!', 'Light Base 600 LX White', NULL, NULL, 12, 2024),
    ('be-quiet-shadow-base-800-fx-white', 'case', 'high', 'be quiet!', 'Shadow Base 800 FX White', NULL, NULL, 12, 2024)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO case_specs (component_id, supported_board_form_factors, max_gpu_length_mm, max_cooler_height_mm, max_radiator_mm, psu_form_factor, included_fans) VALUES
    ((SELECT id FROM components WHERE slug = 'deepcool-cc560-v2-black'), ARRAY['ATX', 'Micro-ATX', 'Mini-ITX'], 370, 165, 360, 'ATX', 4),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch360-white'), ARRAY['Micro-ATX', 'Mini-ITX'], 378, 165, 360, 'ATX', 3),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch560-black'), ARRAY['E-ATX', 'ATX', 'Micro-ATX', 'Mini-ITX'], 380, 175, 360, 'ATX', 4),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-base-501-lx-white'), ARRAY['ATX', 'Micro-ATX', 'Mini-ITX'], 368, 178, 360, 'ATX', 4),
    ((SELECT id FROM components WHERE slug = 'be-quiet-light-base-600-lx-white'), ARRAY['ATX', 'Micro-ATX', 'Mini-ITX'], 400, 170, 360, 'ATX', 4),
    ((SELECT id FROM components WHERE slug = 'be-quiet-shadow-base-800-fx-white'), ARRAY['E-ATX', 'ATX', 'Micro-ATX', 'Mini-ITX'], 430, 180, 420, 'ATX', 4)
ON CONFLICT (component_id) DO UPDATE SET
    supported_board_form_factors = EXCLUDED.supported_board_form_factors,
    max_gpu_length_mm = EXCLUDED.max_gpu_length_mm,
    max_cooler_height_mm = EXCLUDED.max_cooler_height_mm,
    max_radiator_mm = EXCLUDED.max_radiator_mm,
    psu_form_factor = EXCLUDED.psu_form_factor,
    included_fans = EXCLUDED.included_fans;

-- ===== CPU coolers =====
INSERT INTO components (slug, category, tier, brand, model, perf_score, perf_source, power_draw_w, release_year) VALUES
    ('deepcool-ag400-led', 'cooler', 'low', 'DeepCool', 'AG400 LED', NULL, NULL, 3, 2022),
    ('deepcool-ag620-bk-argb-v2', 'cooler', 'low', 'DeepCool', 'AG620 BK ARGB V2', NULL, NULL, 5, 2025),
    ('deepcool-ak500s-digital-se', 'cooler', 'mid', 'DeepCool', 'AK500S Digital SE', NULL, NULL, 4, 2024),
    ('deepcool-ak620-digital', 'cooler', 'mid', 'DeepCool', 'AK620 Digital', NULL, NULL, 6, 2023),
    ('deepcool-le360-pro-black', 'cooler', 'high', 'DeepCool', 'LE360 PRO Black', NULL, NULL, 12, 2025),
    ('arctic-liquid-freezer-iii-pro-360', 'cooler', 'high', 'ARCTIC', 'Liquid Freezer III Pro 360', NULL, NULL, 12, 2025)
ON CONFLICT (slug) DO UPDATE SET
    category = EXCLUDED.category,
    tier = EXCLUDED.tier,
    brand = EXCLUDED.brand,
    model = EXCLUDED.model,
    perf_score = EXCLUDED.perf_score,
    perf_source = EXCLUDED.perf_source,
    power_draw_w = EXCLUDED.power_draw_w,
    release_year = EXCLUDED.release_year,
    updated_at = now();

INSERT INTO cooler_specs (component_id, cooler_type, supported_sockets, height_mm, radiator_mm, max_tdp_w) VALUES
    ((SELECT id FROM components WHERE slug = 'deepcool-ag400-led'), 'air', ARRAY['AM4', 'AM5', 'LGA1700', 'LGA1851'], 150, NULL, 220),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag620-bk-argb-v2'), 'air', ARRAY['AM4', 'AM5', 'LGA1700', 'LGA1851'], 161, NULL, 260),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak500s-digital-se'), 'air', ARRAY['AM4', 'AM5', 'LGA1700', 'LGA1851'], 160, NULL, 240),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak620-digital'), 'air', ARRAY['AM4', 'AM5', 'LGA1700', 'LGA1851'], 162, NULL, 260),
    ((SELECT id FROM components WHERE slug = 'deepcool-le360-pro-black'), 'aio', ARRAY['AM4', 'AM5', 'LGA1700', 'LGA1851'], NULL, 360, 300),
    ((SELECT id FROM components WHERE slug = 'arctic-liquid-freezer-iii-pro-360'), 'aio', ARRAY['AM4', 'AM5', 'LGA1700', 'LGA1851'], NULL, 360, 300)
ON CONFLICT (component_id) DO UPDATE SET
    cooler_type = EXCLUDED.cooler_type,
    supported_sockets = EXCLUDED.supported_sockets,
    height_mm = EXCLUDED.height_mm,
    radiator_mm = EXCLUDED.radiator_mm,
    max_tdp_w = EXCLUDED.max_tdp_w;

-- ===== Store offers (price in MDL) =====
INSERT INTO offers (component_id, store_id, price_mdl, availability, url, checked_on) VALUES
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-5500'), (SELECT id FROM stores WHERE slug = 'xstore'), 1989, 'in_stock', 'https://xstore.md/componente-pc/procesoare/procesor-amd-ryzen-5-5500-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-5500'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1989, 'in_stock', 'https://neocomputer.md/amd-ryzen-5-5500-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-5500'), (SELECT id FROM stores WHERE slug = 'darwin'), 1999, 'in_stock', 'https://darwin.md/procesor-amd-ryzen-5-5500-360-ghz-420-ghz-tray.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-5500'), (SELECT id FROM stores WHERE slug = 'ultra'), 1999, 'in_stock', 'https://ultra.md/product/cpu-amd-ryzen-5-5500-3-6-4-2ghz-6c12t-l2-3mb-l3-16mb-7nm-65w-socket-am4-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-i3-12100f'), (SELECT id FROM stores WHERE slug = 'xstore'), 1799, 'in_stock', 'https://xstore.md/componente-pc/procesoare/procesor-intel-core-i3-12100f-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-i3-12100f'), (SELECT id FROM stores WHERE slug = 'darwin'), 1339, 'out_of_stock', 'https://darwin.md/procesor-intel-core-i3-12100f-330-ghz-tray.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-7600'), (SELECT id FROM stores WHERE slug = 'xstore'), 3799, 'in_stock', 'https://xstore.md/componente-pc/procesoare/procesor-amd-ryzen-5-7600-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-7600'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 4175, 'in_stock', 'https://neocomputer.md/amd-ryzen-5-7600-tray-six-core-socket-am5-38-51ghz-6mb-l2-32mb-l3-cache-amd-radeon-graphics-5nm-65w-zen4-unlocked', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-7600'), (SELECT id FROM stores WHERE slug = 'darwin'), 3979, 'in_stock', 'https://darwin.md/procesor-amd-ryzen-5-7600-tray-am5-380-ghz-510-ghz.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-5-7600'), (SELECT id FROM stores WHERE slug = 'ultra'), 3979, 'in_stock', 'https://ultra.md/product/cpu-amd-ryzen-5-7600-3-8-5-1ghz-6c12t-l2-6mb-l3-32mb-5nm-65w-socket-am5-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-i5-14400f'), (SELECT id FROM stores WHERE slug = 'xstore'), 3709, 'in_stock', 'https://xstore.md/componente-pc/procesoare/intel-core-i5-14400f-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-i5-14400f'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 3860, 'in_stock', 'https://neocomputer.md/procesoare-intel-core-i5-14400f-198529', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-i5-14400f'), (SELECT id FROM stores WHERE slug = 'darwin'), 3879, 'in_stock', 'https://darwin.md/procesor-intel-core-i5-14400f-tray-s1700-250-ghz-470-ghz.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-i5-14400f'), (SELECT id FROM stores WHERE slug = 'ultra'), 3879, 'in_stock', 'https://ultra.md/product/cpu-intel-core-i5-14400f-2-5-4-7ghz-6p-plus4e16t20mbs1700-10nm-no-integ-graphics-65w-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-7-9800x3d'), (SELECT id FROM stores WHERE slug = 'xstore'), 9489, 'in_stock', 'https://xstore.md/componente-pc/procesoare/amd-ryzen-7-9800x3d-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-7-9800x3d'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 9485, 'in_stock', 'https://neocomputer.md/procesor-amd-ryzen-7-9800x3d-tray-223242', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-7-9800x3d'), (SELECT id FROM stores WHERE slug = 'darwin'), 10049, 'in_stock', 'https://darwin.md/procesor-amd-ryzen-7-9800x3d-tray-am5-470-ghz-520-ghz.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'amd-ryzen-7-9800x3d'), (SELECT id FROM stores WHERE slug = 'ultra'), 10049, 'in_stock', 'https://ultra.md/product/cpu-amd-ryzen-7-9800x3d-4-7-5-2ghz-8c16t-l2-8mb-l3-98mb-5nm-120w-socket-am5-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-ultra-7-265k'), (SELECT id FROM stores WHERE slug = 'xstore'), 7009, 'in_stock', 'https://xstore.md/componente-pc/procesoare/intel-core-ultra-7-265k-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-ultra-7-265k'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 7260, 'in_stock', 'https://neocomputer.md/procesor-intel-core-ultra-7-265k-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-ultra-7-265k'), (SELECT id FROM stores WHERE slug = 'darwin'), 7399, 'in_stock', 'https://darwin.md/procesor-intel-core-ultra-7-265k-tray-s1851-330-ghz-550-ghz.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'intel-core-ultra-7-265k'), (SELECT id FROM stores WHERE slug = 'ultra'), 7399, 'in_stock', 'https://ultra.md/product/cpu-intel-core-ultra-7-265k-3-3-5-5ghz-8p-plus12e20t36mbs1851-10nm-integ-graphics-125w-tray', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b550m-ds3h-r2'), (SELECT id FROM stores WHERE slug = 'xstore'), 1989, 'in_stock', 'https://xstore.md/componente-pc/placi-de-baza/gigabyte-b550m-ds3h-r2', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b550m-ds3h-r2'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1997, 'in_stock', 'https://neocomputer.md/placa-de-baza-gigabyte-b550m-ds3h-r2', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b550m-ds3h-r2'), (SELECT id FROM stores WHERE slug = 'darwin'), 2089, 'in_stock', 'https://darwin.md/placa-de-baza-gigabyte-b550m-ds3h-r2-matx-amd-b550m-ddr4.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b550m-ds3h-r2'), (SELECT id FROM stores WHERE slug = 'ultra'), 2089, 'in_stock', 'https://ultra.md/product/mb-am4-gigabyte-b550m-ds3h-r2-matx', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b760m-h-ddr4'), (SELECT id FROM stores WHERE slug = 'xstore'), 2059, 'in_stock', 'https://xstore.md/componente-pc/placi-de-baza/gigabyte-b760m-h-ddr4', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b760m-h-ddr4'), (SELECT id FROM stores WHERE slug = 'darwin'), 1989, 'out_of_stock', 'https://darwin.md/placa-de-baza-gigabyte-b760m-h-matx-intel-b760m.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b760m-h-ddr4'), (SELECT id FROM stores WHERE slug = 'ultra'), 1989, 'out_of_stock', 'https://ultra.md/product/mb-s1700-gigabyte-b760m-h-ddr4-matx', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b650m-d3hp'), (SELECT id FROM stores WHERE slug = 'xstore'), 2629, 'in_stock', 'https://xstore.md/componente-pc/placi-de-baza/gigabyte-b650m-d3hp', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b650m-d3hp'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 2632, 'in_stock', 'https://neocomputer.md/placi-de-baza-gigabyte-b650m-d3hp-193200', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b650m-d3hp'), (SELECT id FROM stores WHERE slug = 'darwin'), 2739, 'in_stock', 'https://darwin.md/placa-de-baza-gigabyte-b650m-d3hp-micro-atx-amd-b650m.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-b650m-d3hp'), (SELECT id FROM stores WHERE slug = 'ultra'), 2739, 'in_stock', 'https://ultra.md/product/mb-am5-gigabyte-b650m-d3hp-matx', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-b760-plus-wifi'), (SELECT id FROM stores WHERE slug = 'xstore'), 4499, 'in_stock', 'https://xstore.md/componente-pc/placi-de-baza/asus-tuf-gaming-b760-plus-wifi', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-b760-plus-wifi'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 4538, 'in_stock', 'https://neocomputer.md/placi-de-baza-asus-tuf-gaming-b760-plus-wifi-198454', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-b760-plus-wifi'), (SELECT id FROM stores WHERE slug = 'darwin'), 4749, 'in_stock', 'https://darwin.md/placa-de-baza-asus-tuf-gaming-b760-plus-wifi-atx-intel-b760.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-b760-plus-wifi'), (SELECT id FROM stores WHERE slug = 'ultra'), 4749, 'in_stock', 'https://ultra.md/product/mb-s1700-asus-tuf-gaming-b760-plus-wifi-atx', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-x870e-aorus-elite-wifi7'), (SELECT id FROM stores WHERE slug = 'xstore'), 7159, 'in_stock', 'https://xstore.md/componente-pc/placi-de-baza/gigabyte-x870e-aorus-elite-wifi7', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-x870e-aorus-elite-wifi7'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 7260, 'in_stock', 'https://neocomputer.md/placa-de-baza-gigabyte-x870e-a-eltite-wifi7', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-x870e-aorus-elite-wifi7'), (SELECT id FROM stores WHERE slug = 'darwin'), 7399, 'in_stock', 'https://darwin.md/placa-de-baza-gigabyte-x870e-a-elite-wifi7-atx-amd-x870e.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-x870e-aorus-elite-wifi7'), (SELECT id FROM stores WHERE slug = 'ultra'), 7399, 'in_stock', 'https://ultra.md/product/mb-am5-gigabyte-x870e-a-elite-wifi7-atx', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-z890-plus-wifi'), (SELECT id FROM stores WHERE slug = 'xstore'), 7159, 'in_stock', 'https://xstore.md/componente-pc/placi-de-baza/asus-tuf-gaming-z890-plus-wifi', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-z890-plus-wifi'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 7260, 'in_stock', 'https://neocomputer.md/placa-de-baza-asus-tuf-gaming-z890-plus-wifi', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-z890-plus-wifi'), (SELECT id FROM stores WHERE slug = 'darwin'), 7549, 'in_stock', 'https://darwin.md/placa-de-baza-asus-tuf-gaming-z890-plus-wifi-atx-intel-z890-plus.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-tuf-gaming-z890-plus-wifi'), (SELECT id FROM stores WHERE slug = 'ultra'), 7549, 'in_stock', 'https://ultra.md/product/mb-s1851-asus-tuf-gaming-z890-plus-wifi-atx', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bbk2-16'), (SELECT id FROM stores WHERE slug = 'xstore'), 4559, 'in_stock', 'https://xstore.md/componente-pc/memorii-ram/kingston-fury-beast-kf432c16bbk216', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bbk2-16'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 4699, 'in_stock', 'https://neocomputer.md/16gb-kit-of-2x8gb-ddr4-3200-kingston-fury-beast-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bbk2-16'), (SELECT id FROM stores WHERE slug = 'darwin'), 2039, 'out_of_stock', 'https://darwin.md/memorie-ram-16-gb-ddr4-3200-mhz-kingston-fury-beast-kf432c16bbk216.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf556c36bbek2-16'), (SELECT id FROM stores WHERE slug = 'xstore'), 7039, 'in_stock', 'https://xstore.md/componente-pc/memorii-ram/kingston-fury-beast-kf556c36bbek216', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf556c36bbek2-16'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 7164, 'in_stock', 'https://neocomputer.md/memorie-16gb-kit-of-2x8gb-ddr5-5600-kingston-fury-beast-ddr5-expo', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf556c36bbek2-16'), (SELECT id FROM stores WHERE slug = 'darwin'), 7599, 'in_stock', 'https://darwin.md/memorie-ram-kingston-fury-beast-kf556c36bbek2-16-ddr5-16-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf556c36bbek2-16'), (SELECT id FROM stores WHERE slug = 'ultra'), 7599, 'in_stock', 'https://ultra.md/product/16gb-ddr5-5600mhz-kingston-fury-beast-kit-of-2x8gb-kf556c36bbek2-16-cl36-38-38-1-25v-amd-exp', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bb1k2-32'), (SELECT id FROM stores WHERE slug = 'xstore'), 8499, 'in_stock', 'https://xstore.md/componente-pc/memorii-ram/kingston-fury-beast-kf432c16bb1k232', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bb1k2-32'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 8456, 'in_stock', 'https://neocomputer.md/32gb-kit-of-2x16gb-ddr4-3200-kingston-fury-beast-pc25600-cl16-1-35v', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf432c16bb1k2-32'), (SELECT id FROM stores WHERE slug = 'darwin'), 6899, 'out_of_stock', 'https://darwin.md/memorie-ram-32-gb-ddr4-3200-mhz-kingston-fury-beast-kf432c16bb1k232.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c36bbe2ak2-32'), (SELECT id FROM stores WHERE slug = 'xstore'), 15019, 'in_stock', 'https://xstore.md/componente-pc/memorii-ram/kingston-fury-beast-rgb-kf560c36bbe2ak2-32', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c36bbe2ak2-32'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 15670, 'in_stock', 'https://neocomputer.md/memorie-ram-32gb-kit-of-2x16gb-ddr5-6000-kingston-fury-beast-rgb-kf560c36bbe2ak2-32-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c36bbe2ak2-32'), (SELECT id FROM stores WHERE slug = 'darwin'), 15749, 'in_stock', 'https://darwin.md/memorie-ram-kingston-fury-beast-rgb-kf560c36bbe2ak2-32-ddr5-32-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c36bbe2ak2-32'), (SELECT id FROM stores WHERE slug = 'ultra'), 15749, 'in_stock', 'https://ultra.md/product/32gb-ddr5-6000mhz-kingston-fury-beast-rgb-kit-of-2x16gb-kf560c36bbe2ak2-32-cl36-44-44-1-35v', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf568c34bbeak2-32'), (SELECT id FROM stores WHERE slug = 'xstore'), 16439, 'in_stock', 'https://xstore.md/componente-pc/memorii-ram/kingston-fury-beast-rgb-kf568c34bbeak2-32', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf568c34bbeak2-32'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 17163, 'in_stock', 'https://neocomputer.md/memorie-ram-32gb-kit-of-2x16gb-ddr5-6800-kingston-fury-beast-rgb-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf568c34bbeak2-32'), (SELECT id FROM stores WHERE slug = 'darwin'), 17249, 'in_stock', 'https://darwin.md/memorie-ram-kingston-fury-beast-rgb-kf568c34bbeak2-32-ddr5-32-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf568c34bbeak2-32'), (SELECT id FROM stores WHERE slug = 'ultra'), 17249, 'in_stock', 'https://ultra.md/product/32gb-ddr5-6800mhz-kingston-fury-beast-rgb-kit-of-2x16gb-kf568c34bbeak2-32-cl34-45-45-1-4v-a', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c30bbeak2-64'), (SELECT id FROM stores WHERE slug = 'xstore'), 31499, 'in_stock', 'https://xstore.md/componente-pc/memorii-ram/kingston-fury-beast-expo-kf560c30bbeak2-64', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c30bbeak2-64'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 32925, 'in_stock', 'https://neocomputer.md/64gb-kit-of-2x32gb-ddr5-6000-kingston-fury-beast-ddr5-rgb-expo-kf560c30bbeak2-64', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c30bbeak2-64'), (SELECT id FROM stores WHERE slug = 'darwin'), 33089, 'in_stock', 'https://darwin.md/memorie-ram-kingston-fury-beast-rgb-kf560c30bbeak2-64-ddr5-64-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-kf560c30bbeak2-64'), (SELECT id FROM stores WHERE slug = 'ultra'), 33090, 'in_stock', 'https://ultra.md/product/64gb-ddr5-6000mhz-kingston-fury-beast-rgb-kit-of-2x32gb-kf560c30bbeak2-64-cl30-36-36-1-4v-a', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5050-windforce-oc-8g'), (SELECT id FROM stores WHERE slug = 'xstore'), 10529, 'in_stock', 'https://xstore.md/componente-pc/placi-video/gigabyte-geforce-rtx-5050-windforce-oc-8g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5050-windforce-oc-8g'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 10618, 'in_stock', 'https://neocomputer.md/placa-video-gigabyte-geforce-rtx-5050-windforce-oc', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5050-windforce-oc-8g'), (SELECT id FROM stores WHERE slug = 'darwin'), 11099, 'in_stock', 'https://darwin.md/placa-video-gigabyte-geforce-rtx-5050-windforce-oc-gv-n5050wf2oc-8gd-8-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-8g'), (SELECT id FROM stores WHERE slug = 'xstore'), 13439, 'in_stock', 'https://xstore.md/componente-pc/placi-video/gigabyte-radeon-rx-9060-xt-gaming-oc-8g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-8g'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 13650, 'in_stock', 'https://neocomputer.md/placa-video-gigabyte-radeon-rx-9060-xt-gaming-oc-8gb-gddr6', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-8g'), (SELECT id FROM stores WHERE slug = 'darwin'), 14199, 'in_stock', 'https://darwin.md/placa-video-gigabyte-radeon-rx-9060-xt-gaming-oc-gv-r9060xtgaming-oc-8gd-8-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-8g'), (SELECT id FROM stores WHERE slug = 'ultra'), 14199, 'in_stock', 'https://ultra.md/product/vga-gigabyte-radeon-rx-9060-xt-8gb-gddr6-gaming-oc-gv-r9060xtgaming-oc-8gd', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-dual-rtx-5060-ti-o16g'), (SELECT id FROM stores WHERE slug = 'xstore'), 20399, 'in_stock', 'https://xstore.md/componente-pc/placi-video/asus-dual-geforce-rtx-5060-ti-oc-edition-16-gb', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-dual-rtx-5060-ti-o16g'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 19390, 'in_stock', 'https://neocomputer.md/placa-video-asus-dual-geforce-rtx-5060-ti-oc-edition', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-dual-rtx-5060-ti-o16g'), (SELECT id FROM stores WHERE slug = 'darwin'), 21589, 'in_stock', 'https://darwin.md/placa-video-asus-geforce-rtx-5060ti-dual-oc-edition-dual-rtx5060ti-o16g-16-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-dual-rtx-5060-ti-o16g'), (SELECT id FROM stores WHERE slug = 'ultra'), 21590, 'in_stock', 'https://ultra.md/product/vga-asus-rtx5060ti-16gb-gddr7-dual-oc-dual-rtx5060ti-o16g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'xstore'), 18419, 'in_stock', 'https://xstore.md/componente-pc/placi-video/gigabyte-radeon-rx-9060-xt-gaming-oc-16g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 18745, 'in_stock', 'https://neocomputer.md/placa-video-gigabyte-radeon-rx-9060-xt-gaming-oc-16gb-gddr6', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'darwin'), 19499, 'in_stock', 'https://darwin.md/placa-video-gigabyte-radeon-rx-9060-xt-gaming-oc-gv-r9060xtgaming-oc-16gd-16-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9060-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'ultra'), 19499, 'in_stock', 'https://ultra.md/product/vga-gigabyte-radeon-rx-9060-xt-16gb-gddr6-gaming-oc-gv-r9060xtgaming-oc-16gd', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5070-ti-windforce-oc-16g'), (SELECT id FROM stores WHERE slug = 'xstore'), 30199, 'in_stock', 'https://xstore.md/componente-pc/placi-video/gigabyte-geforce-rtx-5070-ti-windforce-oc-16g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5070-ti-windforce-oc-16g'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 30674, 'in_stock', 'https://neocomputer.md/gigabyte-rtx-5070-ti-windforce-oc', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5070-ti-windforce-oc-16g'), (SELECT id FROM stores WHERE slug = 'darwin'), 31990, 'in_stock', 'https://darwin.md/placa-video-gigabyte-geforce-rtx-5070-ti-windforce-oc-gv-n507twf3oc-16gd-16-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rtx-5070-ti-windforce-oc-16g'), (SELECT id FROM stores WHERE slug = 'ultra'), 31990, 'in_stock', 'https://ultra.md/product/vga-gigabyte-rtx5070ti-16gb-gddr7-windforce-oc-gv-n507twf30c-16gd', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9070-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'xstore'), 24999, 'in_stock', 'https://xstore.md/componente-pc/placi-video/gigabyte-radeon-rx-9070-xt-gaming-oc-16g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9070-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 25480, 'in_stock', 'https://neocomputer.md/placa-video-gigabyte-radeon-rx-9070-xt-gaming-oc', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9070-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'darwin'), 26389, 'in_stock', 'https://darwin.md/placa-video-gigabyte-radeon-rx-9070-xt-gaming-oc-gv-r9070xtgaming-oc-16gd-16-gb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'gigabyte-rx-9070-xt-gaming-oc-16g'), (SELECT id FROM stores WHERE slug = 'ultra'), 26390, 'in_stock', 'https://ultra.md/product/vga-gigabyte-radeon-rx-9070-xt-16gb-gddr6-gaming-oc-gv-r9070xtgaming-oc-16gd', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-a400-480gb'), (SELECT id FROM stores WHERE slug = 'xstore'), 2639, 'in_stock', 'https://xstore.md/componente-pc/stocare/ssd-kingston-a400-sa400s37-480g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-a400-480gb'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 2705, 'in_stock', 'https://neocomputer.md/ssd-480gb-kingston-a400', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-a400-480gb'), (SELECT id FROM stores WHERE slug = 'darwin'), 2829, 'in_stock', 'https://darwin.md/ssd-480gb-kingston-a400-sa400s37480g.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-a400-480gb'), (SELECT id FROM stores WHERE slug = 'ultra'), 2829, 'in_stock', 'https://ultra.md/product/25-sata-ssd-480gb-kingston-a400-sa400s37480g-rw500450mbs-phison-s11-3d-nand-tlc', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-1tb'), (SELECT id FROM stores WHERE slug = 'xstore'), 3649, 'in_stock', 'https://xstore.md/componente-pc/stocare/kingston-nv3-snv3s1000g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-1tb'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 4520, 'in_stock', 'https://neocomputer.md/storage-ssd-m2-nvme-ssd-10tb-kingston-nv3-interface-pcie40-x4-nvme13-m2-type-2280-form-factor-sequential-reads-6000-196556', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-1tb'), (SELECT id FROM stores WHERE slug = 'darwin'), 4699, 'in_stock', 'https://darwin.md/ssd-kingston-nv3-1-tb-m2-nvme.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-1tb'), (SELECT id FROM stores WHERE slug = 'ultra'), 4699, 'in_stock', 'https://ultra.md/product/m2-nvme-ssd-1-0tb-kingston-nv3-pcie-4-0-x4-rw60004000mbs-320tbw-3d-nand', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-evo-plus-1tb'), (SELECT id FROM stores WHERE slug = 'xstore'), 5959, 'in_stock', 'https://xstore.md/componente-pc/stocare/samsung-990-evo-plus-mz-v9s1t0bw', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-evo-plus-1tb'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 6218, 'in_stock', 'https://neocomputer.md/ssd-10tb-samsung-990-evo-plus-mz-v9s1t0bw', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-evo-plus-1tb'), (SELECT id FROM stores WHERE slug = 'darwin'), 6249, 'in_stock', 'https://darwin.md/ssd-samsung-990-evo-plus-1-tb-m2.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-evo-plus-1tb'), (SELECT id FROM stores WHERE slug = 'ultra'), 6249, 'in_stock', 'https://ultra.md/product/m2-nvme-ssd-1-0tb-samsung-990-evo-plus-mz-v9s1t0bw-pcie-4-0-x45-0-x2-rw71506300mbs-850k13', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-2tb'), (SELECT id FROM stores WHERE slug = 'xstore'), 8349, 'in_stock', 'https://xstore.md/componente-pc/stocare/kingston-nv3-snv3s2000g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-2tb'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 8694, 'in_stock', 'https://neocomputer.md/storage-ssd-m2-nvme-ssd-20tb-kingston-nv3-interface-pcie40-x4-nvme13-m2-type-2280-form-factor-sequential-reads-6000-196557', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-2tb'), (SELECT id FROM stores WHERE slug = 'darwin'), 9099, 'in_stock', 'https://darwin.md/ssd-kingston-nv3-2-tb-m2-nvme.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'kingston-nv3-2tb'), (SELECT id FROM stores WHERE slug = 'ultra'), 9099, 'in_stock', 'https://ultra.md/product/m2-nvme-ssd-2-0tb-kingston-nv3-pcie-4-0-x4-rw60005000mbs-640tbw-3d-nand', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-2tb'), (SELECT id FROM stores WHERE slug = 'xstore'), 9729, 'in_stock', 'https://xstore.md/componente-pc/stocare/samsung-990-pro-mz-v9p2t0bw', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-2tb'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 10148, 'in_stock', 'https://neocomputer.md/m-2-nvme-ssd-2-0tb-samsung-990-pro', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-2tb'), (SELECT id FROM stores WHERE slug = 'darwin'), 10199, 'in_stock', 'https://darwin.md/dispozitiv-de-stocare-ssd-samsung-990-pro-m2-nvme-2-tb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-4tb'), (SELECT id FROM stores WHERE slug = 'xstore'), 17859, 'in_stock', 'https://xstore.md/componente-pc/stocare/samsung-990-pro-4tb', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-4tb'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 18495, 'in_stock', 'https://neocomputer.md/m2-nvme-ssd-40tb-samsung-990-pro-pcie40-x4-nvme20-m2-type-2280-form-factor-read-7450-mbs-write-6900-mbs', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'samsung-990-pro-4tb'), (SELECT id FROM stores WHERE slug = 'darwin'), 19499, 'in_stock', 'https://darwin.md/ssd-samsung-990-pro-4-tb-m2-nvme.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-system-power-11-650w'), (SELECT id FROM stores WHERE slug = 'xstore'), 1469, 'in_stock', 'https://xstore.md/componente-pc/surse/be-quiet-system-power-11-bp011eu', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-system-power-11-650w'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1492, 'in_stock', 'https://neocomputer.md/bloc-de-alimentare-650w-be-quiet-system-power-11', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-system-power-11-650w'), (SELECT id FROM stores WHERE slug = 'darwin'), 1539, 'in_stock', 'https://darwin.md/sursa-de-alimentare-be-quiet-system-power-11-80-bronze-650-w-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-atlas-750'), (SELECT id FROM stores WHERE slug = 'xstore'), 1359, 'in_stock', 'https://xstore.md/componente-pc/surse/cougar-atlas-750', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-atlas-750'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1362, 'in_stock', 'https://neocomputer.md/bloc-de-alimentare-750w-cougar-power-atlas-750', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-atlas-750'), (SELECT id FROM stores WHERE slug = 'darwin'), 1439, 'in_stock', 'https://darwin.md/sursa-de-alimentare-cougar-atlas-750-80-bronze-80-bronze-750-w-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-750'), (SELECT id FROM stores WHERE slug = 'xstore'), 2429, 'in_stock', 'https://xstore.md/componente-pc/surse/cougar-gex-pro-750', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-750'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 2433, 'in_stock', 'https://neocomputer.md/bloc-de-alimentare-750w-cougar-power-gex-pro-750', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-750'), (SELECT id FROM stores WHERE slug = 'darwin'), 2579, 'in_stock', 'https://darwin.md/sursa-de-alimentare-cougar-gex-pro-750-80-gold-80-gold-750-w-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-750'), (SELECT id FROM stores WHERE slug = 'ultra'), 2579, 'in_stock', 'https://ultra.md/product/power-supply-atx-750w-cougar-power-gex-pro-750-80-plus-gold-120mm-full-modular', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-850'), (SELECT id FROM stores WHERE slug = 'xstore'), 2629, 'in_stock', 'https://xstore.md/componente-pc/surse/cougar-gex-pro-850', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-850'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 2632, 'in_stock', 'https://neocomputer.md/bloc-de-alimentare-850w-cougar-power-gex-pro-850', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'cougar-gex-pro-850'), (SELECT id FROM stores WHERE slug = 'darwin'), 2799, 'in_stock', 'https://darwin.md/sursa-de-alimentare-cougar-gex-pro-850-80-gold-80-gold-850-w-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-rog-strix-850w-platinum'), (SELECT id FROM stores WHERE slug = 'xstore'), 4409, 'in_stock', 'https://xstore.md/componente-pc/surse/asus-rog-strix-850w-platinum-850w-80-platinum-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-rog-strix-850w-platinum'), (SELECT id FROM stores WHERE slug = 'darwin'), 4719, 'in_stock', 'https://darwin.md/sursa-de-alimentare-asus-rog-strix-gaming-80-platinum-80-platinum-850-w-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'asus-rog-strix-850w-platinum'), (SELECT id FROM stores WHERE slug = 'ultra'), 4719, 'in_stock', 'https://ultra.md/product/power-supply-atx-850w-asus-rog-strix-gaming-80-plus-platinum-160mm-active-pfc-oppovpuvpscpocpot', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-power-13-m-1000w'), (SELECT id FROM stores WHERE slug = 'xstore'), 3639, 'in_stock', 'https://xstore.md/componente-pc/surse/be-quiet-pure-power-13-m-bp028eu', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-power-13-m-1000w'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 3830, 'in_stock', 'https://neocomputer.md/bloc-de-alimentare-1000w-be-quiet-pure-power-13-m-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-power-13-m-1000w'), (SELECT id FROM stores WHERE slug = 'darwin'), 3849, 'in_stock', 'https://darwin.md/sursa-de-alimentare-be-quiet-pure-power-13-m-80-gold-1000-w-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-cc560-v2-black'), (SELECT id FROM stores WHERE slug = 'xstore'), 979, 'in_stock', 'https://xstore.md/componente-pc/carcase/deepcool-cc560-v2-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-cc560-v2-black'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1010, 'in_stock', 'https://neocomputer.md/deepcool-cc560-v2-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-cc560-v2-black'), (SELECT id FROM stores WHERE slug = 'darwin'), 1039, 'in_stock', 'https://darwin.md/carcasa-deepcool-cc560-v2-mid-tower-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-cc560-v2-black'), (SELECT id FROM stores WHERE slug = 'ultra'), 1039, 'in_stock', 'https://ultra.md/product/case-atx-deepcool-cc560-v2-wo-psu-4x120mm-led-fans-usb3-0-usb2-0-mesh-front-tempered-glass-213993', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch360-white'), (SELECT id FROM stores WHERE slug = 'xstore'), 1469, 'in_stock', 'https://xstore.md/componente-pc/carcase/deepcool-ch360-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch360-white'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1477, 'in_stock', 'https://neocomputer.md/carcasa-pc-deepcool-ch360-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch560-black'), (SELECT id FROM stores WHERE slug = 'xstore'), 2119, 'in_stock', 'https://xstore.md/componente-pc/carcase/deepcool-ch560', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch560-black'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 2132, 'in_stock', 'https://neocomputer.md/deepcool-ch560-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch560-black'), (SELECT id FROM stores WHERE slug = 'darwin'), 2329, 'out_of_stock', 'https://darwin.md/carcasa-deepcool-ch560-mid-tower-black.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ch560-black'), (SELECT id FROM stores WHERE slug = 'ultra'), 2325, 'out_of_stock', 'https://ultra.md/product/case-atx-deepcool-ch560-wo-psu-3x140mm-1x120mm-argb-hybrid-tempered-glass-gpu-support-arm', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-base-501-lx-white'), (SELECT id FROM stores WHERE slug = 'xstore'), 2459, 'in_stock', 'https://xstore.md/componente-pc/carcase/be-quiet-pure-base-501-lx-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-base-501-lx-white'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 2586, 'in_stock', 'https://neocomputer.md/carcasa-pc-be-quiet-pure-base-501-lx-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-base-501-lx-white'), (SELECT id FROM stores WHERE slug = 'darwin'), 2619, 'in_stock', 'https://darwin.md/carcasa-be-quiet-pure-base-501-lx-mid-tower-white.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-pure-base-501-lx-white'), (SELECT id FROM stores WHERE slug = 'ultra'), 2619, 'in_stock', 'https://ultra.md/product/case-atx-be-quiet-pure-base-501-lx-wo-psu-3x120mm-1x140mm-argb-fronttop-mesh-tg-dust-filte-229507', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-light-base-600-lx-white'), (SELECT id FROM stores WHERE slug = 'xstore'), 3699, 'in_stock', 'https://xstore.md/componente-pc/carcase/be-quiet-light-base-600-lx-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-light-base-600-lx-white'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 3780, 'in_stock', 'https://neocomputer.md/carcasa-pc-be-quiet-ligh-base-600-lx-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-light-base-600-lx-white'), (SELECT id FROM stores WHERE slug = 'darwin'), 3949, 'in_stock', 'https://darwin.md/carcasa-be-quiet-ligh-base-600-lx-mid-tower-white.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-light-base-600-lx-white'), (SELECT id FROM stores WHERE slug = 'ultra'), 3949, 'in_stock', 'https://ultra.md/product/case-atx-be-quiet-ligh-base-600-lx-wo-psu-4x120mm-argb-fan-argb-strips-front-side-tg-df-vg-229490', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-shadow-base-800-fx-white'), (SELECT id FROM stores WHERE slug = 'xstore'), 4269, 'in_stock', 'https://xstore.md/componente-pc/carcase/be-quiet-shadow-base-800-fx-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-shadow-base-800-fx-white'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 4476, 'in_stock', 'https://neocomputer.md/be-quiet-shadow-base-800-fx-white-atx-wo-psu-4x140mm-argb-2xusb-32-1xusb-type-c-tg-ro', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-shadow-base-800-fx-white'), (SELECT id FROM stores WHERE slug = 'darwin'), 4559, 'in_stock', 'https://darwin.md/carcasa-be-quiet-shadow-base-800-fx-mid-tower-white.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'be-quiet-shadow-base-800-fx-white'), (SELECT id FROM stores WHERE slug = 'ultra'), 4559, 'in_stock', 'https://ultra.md/product/case-atx-be-quiet-shadow-base-800-fx-wo-psu-4x140mm-argb-2xusb-3-2-1xusb-type-c-tg-white', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag400-led'), (SELECT id FROM stores WHERE slug = 'xstore'), 409, 'in_stock', 'https://xstore.md/componente-pc/racire/deepcool-gammaxx-ag400-led', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag400-led'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 400, 'in_stock', 'https://neocomputer.md/deepcool-ag400-led', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag400-led'), (SELECT id FROM stores WHERE slug = 'darwin'), 429, 'in_stock', 'https://darwin.md/cooler-deepcool-ag400-led-silver.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag400-led'), (SELECT id FROM stores WHERE slug = 'ultra'), 429, 'in_stock', 'https://ultra.md/product/ac-deepcool-ag400-led-31-6db-500-2000rpm-75-89-cfm-120mm-led-220w-46mm-614g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag620-bk-argb-v2'), (SELECT id FROM stores WHERE slug = 'xstore'), 1149, 'in_stock', 'https://xstore.md/componente-pc/racire/deepcool-ag620-bk-argb-v2', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag620-bk-argb-v2'), (SELECT id FROM stores WHERE slug = 'darwin'), 1199, 'in_stock', 'https://darwin.md/cooler-deepcool-ag620-bk-argb-v2-hidrodinamic-1950-rotmin-black-argb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ag620-bk-argb-v2'), (SELECT id FROM stores WHERE slug = 'ultra'), 1189, 'in_stock', 'https://ultra.md/componente-pc/coolere-procesor/deepcool-ag620-bk-argb-v2-120-mm-activ-678', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak500s-digital-se'), (SELECT id FROM stores WHERE slug = 'xstore'), 899, 'in_stock', 'https://xstore.md/componente-pc/racire/deepcool-ak500s-digital-se-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak500s-digital-se'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 890, 'in_stock', 'https://neocomputer.md/cooler-procesor-deepcool-ak500s-digital-se-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak500s-digital-se'), (SELECT id FROM stores WHERE slug = 'darwin'), 949, 'in_stock', 'https://darwin.md/cooler-deepcool-ak500s-digital-se-hidrodinamic-1850-rotmin-black-rgb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak620-digital'), (SELECT id FROM stores WHERE slug = 'xstore'), 1369, 'in_stock', 'https://xstore.md/componente-pc/racire/deepcool-ak620-digital-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak620-digital'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1344, 'in_stock', 'https://neocomputer.md/deepcool-ak620-digital', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak620-digital'), (SELECT id FROM stores WHERE slug = 'darwin'), 1429, 'in_stock', 'https://darwin.md/cooler-deepcool-ak620-digital-hydro-bearing-1850-rpm.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-ak620-digital'), (SELECT id FROM stores WHERE slug = 'ultra'), 1429, 'in_stock', 'https://ultra.md/product/ac-deepcool-ak620-digital-28-db-500-1850rpm-68-99-cfm-2x120mm-argb-260w-66mm-1486g', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-le360-pro-black'), (SELECT id FROM stores WHERE slug = 'xstore'), 1549, 'in_stock', 'https://xstore.md/componente-pc/racire/deepcool-le360-pro-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-le360-pro-black'), (SELECT id FROM stores WHERE slug = 'neocomputer'), 1543, 'in_stock', 'https://neocomputer.md/cooler-procesor-deepcool-le360-pro-black', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'deepcool-le360-pro-black'), (SELECT id FROM stores WHERE slug = 'darwin'), 1639, 'in_stock', 'https://darwin.md/cooler-cu-lichid-deepcool-le360-pro-hydro-bearing-2400-rotmin-black-rgb.html', DATE '2026-10-21'),
    ((SELECT id FROM components WHERE slug = 'arctic-liquid-freezer-iii-pro-360'), (SELECT id FROM stores WHERE slug = 'xstore'), 3119, 'in_stock', 'https://xstore.md/componente-pc/racire/arctic-liquid-freezer-iii-pro-360', DATE '2026-10-21')
-- Existing offers keep the price, sale and stock found by scripts.check_offers.
-- A changed URL is saved and marked as not yet checked.
ON CONFLICT (component_id, store_id) DO UPDATE SET
    url = EXCLUDED.url,
    last_check_status = CASE WHEN offers.url = EXCLUDED.url THEN offers.last_check_status END;

COMMIT;
