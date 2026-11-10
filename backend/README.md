# Backend

FastAPI + PostgreSQL backend for the PC Configurator. Contains the component
catalog schema, migrations, manually maintained seed data, a read-only catalog
API, and compatibility checks that do not modify stored data.
Python 3.12 or newer is recommended. Run all commands below from `backend/`.

## Setup

1. Create a database and role (in `psql` as `postgres`):

   ```sql
   CREATE ROLE pc_app LOGIN PASSWORD 'choose-a-password';
   CREATE DATABASE pc_configurator OWNER pc_app;
   ```

2. Copy `.env.example` to `.env`, put your password in `DATABASE_URL`, and set
   `JWT_SECRET` to a long random value (it signs login tokens):

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Also set `VAULT_KEY`, the key of the encrypted users vault (32 random bytes):

   ```bash
   python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

   `.env` is git-ignored. The app refuses to start without `JWT_SECRET` and a valid
   `VAULT_KEY`. Back up `VAULT_KEY` somewhere other than the vault file: without it
   no account can be read.

3. Install dependencies, create the tables, and load the seed data (Linux/macOS):

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m alembic upgrade head
   .venv/bin/python -m scripts.seed
   ```

   On Windows, create the environment with `python -m venv .venv` and replace
   `.venv/bin/python` with `.venv\Scripts\python.exe` in the remaining commands.

4. Start the API:

   ```bash
   .venv/bin/python -m uvicorn app.main:app --reload
   ```

   Interactive API documentation: <http://127.0.0.1:8000/docs>.
   OpenAPI schema: <http://127.0.0.1:8000/openapi.json>.
   The API does not create tables or seed data automatically.

## Running the public site from this computer

The Vercel site (see `frontend/README.md`) can use the API running on your own
computer. An [ngrok](https://ngrok.com) tunnel gives it a fixed public HTTPS
address; PostgreSQL, the users vault and the logs stay on your computer, and only
the API port is reachable from outside. The site works while the script below is
running and shows "Serverul nu este pornit momentan" when it isn't.

One-time setup:

1. Create a free ngrok account, install ngrok (`winget install ngrok.ngrok`) and
   run `ngrok config add-authtoken <your token>` (the token is on the ngrok dashboard).
2. On the ngrok dashboard, under *Domains*, claim your free static domain, for
   example `your-name.ngrok-free.app`.
3. Add it to `.env`: `NGROK_DOMAIN=your-name.ngrok-free.app`.
4. In `frontend/vercel.json`, put `your-name.ngrok-free.app` in the `/api/:path*`
   rewrite and commit. This is needed only once, because the domain doesn't change.

Then, whenever you want the site to work, double-click `scripts\start-public.cmd`
(or run `powershell -ExecutionPolicy Bypass -File scripts\start-public.ps1`). It
starts the API, waits until it can reach the database, and opens the tunnel.
Ctrl+C or closing the window stops both. Your computer has to stay on and awake
while it runs.

To start it automatically when you log in to Windows, press Win+R, open
`shell:startup`, and put a shortcut to `scripts\start-public.cmd` there.
PostgreSQL normally runs as a Windows service, so it is already up by then.

## API

| Method | Path | Result |
|---|---|---|
| GET | `/health` | API liveness; no database query |
| GET | `/health/db` | PostgreSQL connectivity; HTTP 503 if unavailable |
| GET | `/components` | Paginated components with store offers |
| GET | `/components/{component_id}` | A component's specifications and store offers; HTTP 404 if absent |
| GET | `/stores` | Stores sorted by name |
| POST | `/compatibility/check` | Check a complete or partial selection without saving it |
| POST | `/compatibility/filter` | AC-3 filtering of candidate components |
| POST | `/auth/register` | Create an account; HTTP 409 if the email is taken |
| POST | `/auth/login` | Get a bearer token (email); HTTP 401 for a wrong login or password |
| GET | `/auth/me` | The logged-in user 🔒 |
| GET / POST | `/builds` | List your saved builds / save a new one 🔒 |
| GET / PUT / DELETE | `/builds/{build_id}` | Read, replace or delete one of your builds 🔒 |
| POST | `/purchase/plan` | Which store to buy each part from, at the lowest total (Min-Cost Max-Flow) |
| POST | `/recommendations` | The best compatible builds within a budget, ranked by TOPSIS |

🔒 = send `Authorization: Bearer <access_token>` from `/auth/login`.

`/components` supports optional `category`, `tier`, and `brand` filters.
Categories: `cpu`, `motherboard`, `ram`, `gpu`, `storage`, `psu`, `case`, `cooler`.
Tiers: `low`, `mid`, `high`. Brand matching is exact, case-insensitive, and trims
surrounding spaces. Combined filters use AND.

Example: <http://127.0.0.1:8000/components?category=cpu&tier=low&brand=AMD&limit=10&offset=0>.

The response has `items`, `total` (matching rows before pagination), `limit`
(default 20, range 1–1000), and `offset` (default 0, nonnegative). Components are
ordered by ID so pagination is deterministic. Invalid parameters return HTTP 422.

Every component, in the list and in details, includes a typed `specs` object for
its category, so a client can load the whole catalog in a few requests. If a
component has no specifications (some imported parts, see below), `specs` is `null`. A component without
offers returns `offers: []`. All offers are included, including out-of-stock and
on-order offers, ordered by price and then store ID. Each offer includes its store,
availability, product URL, and `checked_on` date. Decimal values such as `price_mdl`
are JSON strings (e.g. `"2499.00"`) to preserve precision. Unknown stock quantities
are `null`, rather than zero.

The API reads only from PostgreSQL; it never contacts the stores itself. The
hand-checked parts are in `seed/seed.sql`; every other in-stock part comes from
`scripts.import_catalog` (below). Prices, sales and stock can be refreshed from
the store websites on demand with `scripts.check_offers`.
There are no automatic or scheduled updates. Catalog editing endpoints are not
yet implemented.

## Accounts and saved builds

Register with `{"email": "...", "password": "..."}` and log in
with `{"login": "<email>", "password": "..."}`. Emails are unique, compared without
case. Passwords need 8–128 characters. Login returns `access_token`, `token_type`
(`bearer`) and `expires_in` (seconds, `ACCESS_TOKEN_MINUTES`, default 24 h). Wrong
password and unknown login give the same 401, so accounts can't be probed.

**Where personal data is kept** (`app/vault.py`): the email and the password
hash are in one file, `data/users.vault` (git-ignored, `VAULT_PATH` to move it),
encrypted with AES-256-GCM using `VAULT_KEY`. GCM also authenticates: a changed or
damaged file, or a wrong key, fails to open instead of giving wrong data. Every save
uses a new random nonce and replaces the file atomically. The `users` table keeps
only the id (saved builds point to it) and the creation time. The email can be
decrypted; passwords are Argon2id hashes (`app/security.py`, salted, slow and
memory-hard), so not even the key turns them back into passwords. Login checks the
hash. Keep the key apart from the file and its backups.

**Activity log** (`app/audit.py`): every account action is one line in
`activity.log` inside `AUDIT_LOG_DIR` (default `backend/logs/`, git-ignored; set it in
`.env` to any folder, e.g. `AUDIT_LOG_DIR=D:/pc-configurator-logs`). A
`RotatingFileHandler` starts a new file at `AUDIT_LOG_MAX_BYTES` (default 5 MB) and
keeps `AUDIT_LOG_BACKUP_COUNT` old ones (default 10: `activity.log.1` … `.10`).
Actions: `REGISTERED`, `REGISTER_FAILED`, `LOGIN_OK`, `LOGIN_FAILED` (reason: wrong
password, or no account with this email), `BUILD_SAVED`, `BUILD_SAVE_FAILED`,
`BUILD_UPDATED`, `BUILD_UPDATE_FAILED`, `BUILD_DELETED`, `BUILD_DELETE_FAILED`.

```
2026-11-04 15:27:27 | LOGIN_FAILED | email=ana@exemplu.com | reason=wrong password
2026-11-04 15:27:31 | BUILD_SAVED | email=ana@exemplu.com | build_id=2 | name=Gaming | parts=8
```

Passwords and tokens are never written. The file holds emails in plain text, so keep
the folder private. Run the server with one worker process: `RotatingFileHandler`
isn't safe when several processes write the same file.

Decrypt and list the accounts (id, email):

```bash
.venv/bin/python -m scripts.vault show
```

Migration `0005` moves to this layout; it refuses to run while accounts with the old
one-way hashes exist, since those passwords can't be recovered.

Save a build with the same `components` shape as `/compatibility/check`, plus a
`name` (1–100 characters):

```json
{"name": "Mid AM5", "components": {"cpu": 3, "motherboard": 9, "ram": 16}}
```

- Incomplete and incompatible builds can be saved; drafts are allowed.
- Each part stores the cheapest in-stock price and store at the moment it was
  added (`saved_price_mdl`, `saved_store`). Reading a build also shows today's
  cheapest in-stock offer (`current_price_mdl`, `current_store`), the two totals,
  and `unpriced_categories` for parts no store has in stock.
- Reading a build recomputes `compatibility` with the current rules, in the same
  format as `/compatibility/check`.
- `PUT` replaces the name and the whole selection. Parts kept in the same
  category keep their saved price; new parts get today's price.
- A build owned by someone else answers 404, as if it didn't exist.
- Components used in saved builds can't be deleted from the catalog.

## Purchase planning (Min-Cost Max-Flow)

`POST /purchase/plan` takes the same `components` shape as `/compatibility/check`
and picks a store for each part:

```json
{"components": {"cpu": 3, "gpu": 22, "ram": 16}}
```

The solver (`app/services/mcmf.py`) is a general Min-Cost Max-Flow using
successive shortest paths, with Bellman-Ford finding each cheapest path.
`app/services/purchase.py` builds this network, one unit of flow per part:

```
source ──1──▶ part ──1, price──▶ store ──▶ sink
```

- **Max flow** = how many parts can be bought. A part with no in-stock offer is
  listed in `unplanned`, and `status` is `partial`.
- **Min cost** = the cheapest way to buy them. Prices are converted to bani
  (integers), so totals are exact. Equal prices go to the lower store ID.
- Only `in_stock` offers are used. Stock quantities and delivery fees are not
  modeled (a team decision: the site gives fast price information).

`tests/test_purchase.py` checks the solver against brute force on 300 random
graphs, and the planner on 500 random purchase cases.

## Recommendations (TOPSIS)

`POST /recommendations` takes a budget, what the PC is for, and optionally a CPU brand:

```json
{"budget_mdl": 55000, "purpose": "gaming", "cpu_brand": "AMD"}
```

`purpose` is `gaming`, `office`, `workstation` or `editing`; `cpu_brand` is
`AMD`, `Intel` or omitted.

**1. Requirements per purpose** (`app/services/tiers.py`, the baseline tier
reference). Hard filters on every alternative, on top of compatibility:

| Purpose | CPU | GPU | RAM | Storage | PSU |
|---|---|---|---|---|---|
| office | ≥ 4 cores / 8 threads, integrated graphics, up to Ryzen 7 / Core i7 / Core Ultra 7 | none (integrated) | 8–16 GB | one 256–512 GB M.2 SSD (NVMe or SATA) | by load |
| gaming | ≥ 6 cores / 12 threads | ≥ 6 GB VRAM | 16–32 GB | SSD ≥ 500 GB + HDD 500 GB–1 TB, or one fast NVMe ≥ 1 TB | ≥ 650 W |
| editing | 8–16 cores | ≥ 12 GB VRAM | 32–64 GB | NVMe ≥ 512 GB + fast NVMe ≥ 2 TB | 80+ Gold or better |
| workstation | ≥ 8 cores / 16 threads | ≥ 8 GB VRAM | ≥ 32 GB (≥ 64 GB with a 24 GB+ GPU) | one fast NVMe 1–2 TB | ≥ 850 W, 80+ Gold or better |

"Fast" NVMe = PCIe 4.0 or newer. "By load" = the compatibility rules (PSU ≥ peak
draw, warning below +20%). A single size ("500 GB", "1 TB") is a minimum; a range
is a range. Every purpose gets a dedicated cooler with a stated rating of at least
1.3 × the CPU's TDP (a bundled stock cooler has no rating, so it doesn't count), and
the pre-filter ranks coolers by that rating, not only by price. A PSU whose
efficiency the stores don't state still counts for "80+ Gold or better"; only a
stated lower rating (Bronze, White, ...) excludes it.

**2. Alternatives** (`app/services/recommend.py`): the complete builds that are
compatible, meet the purpose's requirements and cost at most the budget. The
catalog has hundreds of parts per category, too many builds to list, so `prefilter`
first keeps about 5 per slot:

1. parts with specs whose price leaves room for the cheapest part of every other category;
2. parts not dominated (cheaper or equal, faster or equal, lower or equal draw, and
   better in one) by a part with exactly the same specs. Same specs = same
   compatibility, so a build with the dominated part is never ranked above the same
   build with the part that dominates it;
3. the parts of cheap complete builds (`cheap_build`: per slot the cheapest part that
   fits everything chosen so far, PSU ≥ draw + 50 W): the cheapest build overall, and
   one for each picked CPU, so every picked CPU has parts to form a build and some
   build fits a small budget. A slot can get a little over 5 parts this way;
4. for CPU, GPU, RAM and the first drive, the best-ranked part of each price band of
   the slot, so builds span from cheap to near the budget and differ in more than one part;
5. up to 5 in total: the parts that a part-level TOPSIS (same weights, the part's own price, performance
   and draw; a cooler's rating counts as its performance) ranks best, taking spec
   groups in turn so different sockets and sizes stay represented, and only parts
   compatible with (and meeting the requirements together with) at least one part
   already picked for each earlier slot (CPU, board, RAM, GPU, PSU, case, cooler,
   storage, second drive).

8 per category was tried first; real store data is so compatible that it gave up to
6 million builds and 20 s to 7 minutes per request.

AC-3 then prunes these domains, and backtracking with forward checking picks one part per category,
dropping a branch as soon as a later category has no compatible part left or the
cheapest remaining parts would exceed the budget. A build is kept only when
`/compatibility/check` would call it `compatible`: no failed rule, no rule left
unresolved by missing data (so AIO coolers, whose radiator mounts are always
"to verify", are not used), and a PSU at least as large as the recorded peak draw.
The GPU is left out only for office (the CPU then must have graphics); the second
drive only where the purpose allows one drive; two drives need two connectors of
their kind on the board. Only parts with an in-stock offer are used.

**3. Criteria**, one decision-matrix row per build:

| Criterion | Value | Goal |
|---|---|---|
| Price | sum of each part's cheapest in-stock offer (what `/purchase/plan` pays) | min |
| Performance | CPU share × CPU `perf_score` + GPU share × GPU `perf_score` (0 without a GPU) | max |
| Consumption | sum of recorded peak draw, PSU excluded (`estimated_power_w`) | min |

**4. Weights** (non-negative, each row sums to 1) and the performance mix:

| Purpose | Price | Performance | Consumption | CPU / GPU in performance |
|---|---|---|---|---|
| gaming | 0.35 | 0.50 | 0.15 | 0.5 / 0.5 |
| office | 0.60 | 0.20 | 0.20 | 0.7 / 0.3 |
| workstation | 0.25 | 0.60 | 0.15 | 0.5 / 0.5 |
| editing | 0.30 | 0.55 | 0.15 | 0.6 / 0.4 |

**5. TOPSIS** (`app/services/topsis.py`): vector-normalize each column
(r = x / √Σx²), multiply by the weights, take the ideal (A+) and anti-ideal (A−)
value per criterion (max/min for performance, min/max for price and consumption),
compute each build's Euclidean distances D+ and D−, and rank by closeness
C = D− / (D+ + D−).

The response gives the `weights`, the `performance_mix`, how many `alternatives`
were ranked, and up to six `builds` with their `components` (`null` = no separate
GPU/cooler or second drive), criteria values, `distance_best`, `distance_worst` and
`closeness`, cheapest first (`spread_by_price`). The range from the cheapest ranked
build to the budget is split into six equal price bands, and each band shows its
best-ranked build, so the variants run from cheap to near the budget. No two shown
builds share a CPU chip + GPU chip pair (builds that differ only in the case, the
card maker or Box/Tray packaging score almost the same). Empty bands are filled by
the best-ranked builds with a new pair, then (office has no GPU) by builds with a
new RAM or storage size. `rank` is the build's position in the full TOPSIS ranking,
so it can skip numbers. With no build within budget, `builds` is empty.

`tests/test_topsis.py` checks TOPSIS on a hand-computed example, and the build
generator against brute force (every combination through `check_build`) on 60
random catalogs; `tests/test_catalog_import.py` checks the pre-filter. A request
ranks up to about 270,000 builds and takes 1–3 s.

## Importing every in-stock part from the stores

```bash
.venv/bin/python -m scripts.seed                    # stores (incl. PrimePC) and hand-checked parts
.venv/bin/python -m scripts.import_catalog crawl    # store pages -> .crawl-cache/products.json
.venv/bin/python -m scripts.import_catalog load     # -> components, specs, offers in the database
```

`crawl xstore darwin` crawls only those stores (the others' saved products are kept).
Nothing runs automatically.

**Crawling** (`scripts/import_catalog.py`, Crawlee): each store's category listings,
page by page (`?page=N`), then every product page. Neocomputer's robots.txt forbids
`?page=`, so its products come from its product sitemap, filtered by keywords, and
the breadcrumb on each page decides the category. Each store runs in its own
process. Politeness: robots.txt is followed with its `*` and `$` wildcards
(`scripts/crawl.py`; Python's own parser ignores them), at most one request every
0.5 s per store, the project's User-Agent, and a page cache (`.crawl-cache/`,
git-ignored), so a rerun only asks for new pages. Neocomputer stopped answering at
0.5 s, so it gets one request every 3 s.

**Specs** (`app/services/catalog_normalize.py`): each store names its specs
differently, in Romanian or Russian; a field is found by label keywords, then by
the title. Skipped, judged on the title and the store's own product-type labels
(`not_a_desktop_part` and the per-category rules): used, refurbished, reconditioned or
recertified parts (title, or a condition field such as Ultra's "Stare"); laptop memory; ECC/registered and
OEM server/NAS memory, power supplies and drives (Dell, Fujitsu, HP, Lenovo, Synology,
Supermicro); DDR3 platforms (e.g. H61, H81, A68 boards); SSD enclosures, external
drives and memory cards; SAS and M.2 22110 data-center drives; external GPUs; PSU
cables and adapters; cases with a built-in PSU; TFX/Flex PSUs; case fans and other
cooling accessories. Retail enterprise SATA HDDs (Seagate Exos, WD Gold) are kept:
they work in a desktop.
Pages of the same product are merged (by part number; CPUs by model + Box/Tray). A
spec is never taken as a part number (`DDR5-5600`, `PC4-25600`, `ATX-550W`), nor is a
board's bare series name (`B860-PLUS` is ASUS PRIME and TUF GAMING): without a part
number the brand and full model name are the identity. Pages under one identity that
disagree on a key spec (RAM size, sticks, speed, CL; board chipset and memory type;
CPU graphics; drive size; VRAM; PSU wattage), and two pages of one store, stay separate
products. Kingston's part number states its specs and overrides the store's table;
Intel's name settles graphics (F = none); an AM5/LGA1851 board takes DDR5, AM4 DDR4.
`load` stops and lists every merge conflict (`merge_conflicts`) before writing
anything; `tests/test_catalog_import.py::test_whole_crawl_merges_without_conflicts`
runs the same check over the last crawl, and `python -m scripts.spot_check 10`
compares 10 random merged products per store with the live pages.
Missing values are filled, in this order
(`app/services/catalog_merge.py`):

1. the value most of the product's pages agree on;
2. platform facts: an AM5/LGA1851 CPU uses DDR5, AM4/LGA1200 DDR4, LGA1700 both;
   Intel "F" CPUs have no graphics; a Tray CPU, or one whose cooler isn't stated,
   is treated as coming without a cooler (the build then requires one);
3. PassMark's chip page: CPU cores, threads, clocks and TDP; GPU TDP;
4. other cards with the same GPU chip: median TDP, recommended PSU and thickness;
   if no store gives a card's length, the longest card with that chip;
5. the manufacturer's page linked by the store: case maximum GPU length
   (PrimePC doesn't list it). be quiet! answers crawlers with HTTP 403, so its
   cases stay without it;
6. fields no rule reads: a board's maximum memory from its slots (32 GB per DDR4
   slot, 64 GB per DDR5), unstated PSU efficiency/modularity, unstated case fans (0).

A product still missing a required spec is saved without specs: it can be chosen
in the manual configurator (with a "specifications missing" warning), and TOPSIS
skips it. `.crawl-cache/import-report.json` lists these products, every filled
value with its source, and the skipped pages.

**Performance scores**: CPUs and GPUs, imported and hand-entered alike, get
`perf_score` = PassMark mark / best mark in the catalog × 100 (CPU Mark, G3D Mark),
from PassMark's chart pages. `perf_source` shows the numbers. **Power draw** follows
the seed's convention: CPU maximum package power (AMD 1.35 × TDP, Intel PL2 by TDP
class), GPU board power, small fixed values for the other parts. **Tier** is the
price third within the category.

A product whose page is already an offer of a component is that component: it gets
the new offers. Parts from `seed/seed.sql` keep their hand-checked specs; imported
parts get the specs of the latest run.

## Updating prices, sales and stock from the stores

Run this whenever you want fresh data (nothing runs automatically):

```bash
.venv/bin/python -m scripts.check_offers      # Windows: .venv\Scripts\python -m scripts.check_offers
```

It opens every offer's product page (171 pages take about 2 minutes) and updates
`price_mdl`, `regular_price_mdl` (the crossed-out price during a sale, otherwise
null), `availability` and `checked_on`, then prints what changed:

```
  changed Xstore       intel-core-i5-14400f: price 3709.00 -> 3659.00, on sale (regular 3879.00)
Done: 171 ok (82 changed), 0 failed, 0 page gone.
```

- **Where the data comes from:** Xstore, NeoComputer, Darwin and Ultra embed
  schema.org Product data (current price and availability) in their pages.
  PrimePC doesn't, so its price and stock are read from the page's HTML: the
  "Цена:" price block when the product can be bought, the "Последняя цена
  продажи:" (last selling price) block when it is out of stock. The sale's regular price is
  read from the crossed-out price in each store's price block
  (`app/services/store_pages.py`).
- **Being polite:** the script follows each store's robots.txt, waits 2 seconds
  between requests to the same store, and names the project in its User-Agent.
- **Failures never erase data:** if a page can't be read, the offer keeps its
  previous values and `last_check_status` becomes `failed` (`page_gone` for HTTP
  404/410). The API shows `last_check_status` with each offer.
- **If a store redesigns its site,** that store's offers start failing.
  `tests/test_store_pages.py` runs the parsers on trimmed real pages saved in
  `tests/fixtures/store_pages/`; update the selector and save a fresh page.
- Xstore and NeoComputer show a crossed-out price on most products, so most of
  their offers appear as on sale. That is what the stores display.

The API returns `regular_price_mdl`, `on_sale` and `last_check_status` with each offer.

## Compatibility checks

Send a JSON object to `POST /compatibility/check`. Obtain component IDs from
`GET /components`; IDs below are examples, not guaranteed across databases:

```json
{
  "components": {
    "cpu": 1,
    "motherboard": 7,
    "ram": 13
  }
}
```

Keys are slots: one per category, plus `storage2` for an optional second drive
(a storage component; it may be the same drive as `storage`). Partial builds are allowed, but at least one selection is required. IDs must be
positive JSON integers; duplicate IDs, unknown categories, extra request fields,
and a component selected under the wrong category return HTTP 422. IDs absent
from the catalog return HTTP 404. A valid request returns HTTP 200 even when the
parts are incompatible: compatibility is the result, not an HTTP failure.

The response includes:

- `status`: `incompatible` if a known conflict exists; otherwise `incomplete` if
  required categories are absent; otherwise `undetermined` if selected data
  cannot resolve a modeled check; otherwise `compatible` under the modeled rules.
- `missing_categories`: CPU, motherboard, RAM, storage, PSU, and case are required.
  A discrete GPU is also required when the selected CPU has no integrated graphics;
  a separate cooler is required when the CPU does not include one. An unknown CPU
  spec cannot establish those extra requirements and is reported as missing data.
- `issues`: stable rule `code`, `severity` (`error` or `warning`), affected
  `component_ids`, and a human-readable `message` with relevant values.
- `checked_rules`: codes of hard constraints actually evaluated, whether passed
  or failed. A missing component or missing spec never counts as a passed check.
- `estimated_power_w`: sum of recorded peak draw for selected parts, excluding
  the PSU itself. For partial builds this is only a lower bound.
- `recommended_psu_w`: the greater of rounded-up peak draw plus 20% and the GPU's
  recorded PSU recommendation. The 20% margin is an MVP policy. Capacity below
  recorded draw is an error; capacity meeting draw but below the recommendation
  is a warning. This is an estimate, not measured consumption.
- `limitations`: checks the current schema cannot fully establish. `compatible`
  means no conflicts in the modeled rules; it is not a physical assembly guarantee.

Implemented rules:

| Area | Checks |
|---|---|
| Platform | CPU/motherboard sockets; CPU memory support; motherboard/RAM DDR generation |
| RAM | Kit module count versus available slots; kit capacity versus board maximum |
| Case | Motherboard form factor; GPU length; air cooler height |
| Cooling | Cooler socket support; AIO maximum radiator size; advisory thermal rating |
| Storage | M.2 slot for M.2 NVMe; SATA port for non-M.2 SATA storage; with two drives, enough M.2 slots and SATA ports for both |
| Power | Selected peak draw versus PSU wattage; recommended capacity with margin |

Unknown specifications and empty supported-value lists produce warnings and
cannot establish compatibility. PSU/case form-factor differences are unresolved
because adapters are not modeled. AIO radiator sizes above the case maximum are
conflicts; sizes within the maximum still require exact mount verification.
The existing catalog defines `max_radiator_mm = null` as no AIO radiator support;
selecting an AIO with such a case returns a conflict. A missing case spec is
reported as unknown data instead.
M.2 SATA protocol support and non-M.2 NVMe connections require manual verification.

Motherboard CPU support/BIOS versions, power cable inventories, drive bays, exact
M.2 lengths/protocols, and interacting clearances are not fully modeled. Matching
sockets alone do not establish CPU support; see [Intel's compatibility guidance](https://www.intel.com/content/www/us/en/support/articles/000092149/processors.html).
Radiator fit also depends on dimensions and mounting arrangements; see
[Corsair's radiator guidance](https://help.corsair.com/hc/en-us/articles/360052178672-Hydro-X-Tips-on-choosing-the-right-radiator-for-your-Hydro-X-cooler).

Rule code lives in `app/services/compatibility.py`, independently of HTTP/database
access. Binary rules are available through `check_pair` for later AC-3 reuse;
build completeness and total power are checked separately by `check_build`.
Min-Cost Max-Flow and TOPSIS are described in their own sections.
The check endpoint validates an existing selection; AC-3 filtering is described below.

## Tests

Install test dependencies and run:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

HTTP validation, compatibility rule boundaries, liveness, OpenAPI, and
unavailable-database checks run without PostgreSQL. Catalog and compatibility
endpoint integration tests are skipped unless `TEST_DATABASE_URL` is
set. Use a **separate test database** with migrations and seed data loaded:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://pc_app:YOUR_PASSWORD@localhost:5432/pc_configurator_test'
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m scripts.seed
.venv/bin/python -m pytest -q
```

Create `pc_configurator_test` first with the same role as in setup. In PowerShell,
use `$env:TEST_DATABASE_URL = '...'` and `$env:DATABASE_URL = $env:TEST_DATABASE_URL`
before running the migration and seed commands. Integration tests use transactions
that roll back their changes; the database must still be dedicated to tests.

## Schema

| Table | Purpose |
|---|---|
| `components` | One row per product: category, tier (`low`/`mid`/`high`), brand, model, `perf_score`, `power_draw_w` |
| `cpu_specs`, `motherboard_specs`, `ram_specs`, `gpu_specs`, `storage_specs`, `psu_specs`, `case_specs`, `cooler_specs` | Typed specs, one row per component, keyed by `component_id` |
| `stores` | Xstore, NeoComputer, Darwin, Ultra |
| `offers` | A store's price (MDL), availability and product URL for a component; one row per (component, store) |

The fields used by compatibility checks:

- CPU `socket` ↔ motherboard `socket`
- CPU `memory_types` ∋ motherboard `memory_type` = RAM `memory_type`
- Motherboard `form_factor` ∈ case `supported_board_form_factors`
- GPU `length_mm` ≤ case `max_gpu_length_mm`
- Air cooler `height_mm` ≤ case `max_cooler_height_mm`; AIO `radiator_mm` ≤ case `max_radiator_mm`
- CPU `socket` ∈ cooler `supported_sockets`
- PSU `wattage` vs. the sum of `power_draw_w`

## Seed data

All catalog data is in one SQL file, `seed/seed.sql`, grouped by section: stores,
then each category (its `components` rows followed by its spec rows), then
store offers. Rows reference each other by `slug`, never by numeric id.

Load it in either of two ways (after `alembic upgrade head`):

- `python -m scripts.seed` from `backend/`, or
- open `seed/seed.sql` in pgAdmin's Query Tool, connected to `pc_configurator`, and press F5.

Every `INSERT` ends in `ON CONFLICT … DO UPDATE`, so the file is safe to re-run.
To add a part or change specs, edit `seed.sql` and run it again. Offer prices in
`seed.sql` are only starting values for new offers: re-running it never
overwrites the price, sale or stock of an existing offer (only its URL), so data
from `scripts.check_offers` is kept. Use the checker to refresh prices.

### Where the data came from (2026-10-21)

- **Prices and URLs** were looked up by hand on each store's website on 2026-10-21.
  They are the current (discounted) prices shown on the site.
- **Availability**: Darwin and Ultra were checked on each product page
  ("Stoc epuizat" / "Notifică" → `out_of_stock`). Xstore and NeoComputer don't
  show stock clearly, so an offer is marked `in_stock` when the product can be
  added to the cart.
- **NeoComputer RAM**: listings don't show Kingston part numbers. They were
  matched by capacity, speed and series.
- **Specs used by compatibility checks** (GPU length/PSU recommendation,
  motherboard memory/M.2/SATA/form factor, cooler height/radiator/sockets,
  case GPU/cooler/radiator limits and board sizes, PSU connectors) were checked
  against the manufacturers' own spec pages (Gigabyte, ASUS, DeepCool, be quiet!)
  on 2026-10-22. Exceptions: the Cougar GEX PRO 16-pin connector is from retailer
  listings, and the Cougar Atlas 750 and ARCTIC Liquid Freezer III Pro 360 were not
  re-checked. DeepCool CH360: GPUs up to 378 mm fit, but only 320 mm with a
  front-mounted radiator; the schema stores one limit, so 378 is used.
- **`perf_score` values are rough estimates** (`perf_source` says so), only for
  CPUs and GPUs. Replace them with sourced benchmark numbers before the evaluation chapter.

## AC-3 candidate filtering

`POST /compatibility/filter` accepts `{"components": {"cpu": 1}}`, using actual
catalog IDs, or `{}` to start without selections. Selected categories become
singleton domains; all other categories start with their catalog candidates.
The endpoint reuses pairwise compatibility rules and repeatedly removes candidates
that have no supporting choice in another domain, until no domain changes.
Missing specifications and advisory warnings do not by themselves remove a choice.

The response contains `domains` (remaining IDs per category), `removed` (IDs
pruned from the initial domains), `empty_categories`, and `status`:
`arc_consistent` or `inconsistent`. Selected IDs can be removed if they have no
support, yielding an inconsistent result; the request itself is never modified.
GPU and cooler domains may include JSON `null`, representing no separate part.
These choices are removed for CPUs without integrated graphics or a bundled cooler.
Other categories are required. All catalog offers are considered regardless of
stock; price, budget, and total system power are outside this binary filtering step.

Nonempty domains do not guarantee a global solution. Run `/compatibility/check`
on a final selection to check total power and completeness. Remove `null` choices
from the selection before calling that endpoint. No data is saved by filtering.
