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

   `.env` is git-ignored. The app refuses to start without `JWT_SECRET`.

   Optional: set `GEMINI_API_KEY` (from <https://aistudio.google.com/apikey>) to
   enable the AI advice endpoints. Without it they answer HTTP 503.

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
| POST | `/auth/login` | Get a bearer token; HTTP 401 for a wrong email or password |
| GET | `/auth/me` | The logged-in user 🔒 |
| GET / POST | `/builds` | List your saved builds / save a new one 🔒 |
| GET / PUT / DELETE | `/builds/{build_id}` | Read, replace or delete one of your builds 🔒 |
| POST | `/purchase/plan` | Which store to buy each part from, at the lowest total (Min-Cost Max-Flow) |
| POST | `/ai/budget-advice` | Gemini's advice for a budget in MDL, based on catalog prices; HTTP 503 without `GEMINI_API_KEY`, 502 if Gemini fails |
| POST | `/ai/performance` | Gemini's performance estimate for a selection; same errors |

🔒 = send `Authorization: Bearer <access_token>` from `/auth/login`.

`/components` supports optional `category`, `tier`, and `brand` filters.
Categories: `cpu`, `motherboard`, `ram`, `gpu`, `storage`, `psu`, `case`, `cooler`.
Tiers: `low`, `mid`, `high`. Brand matching is exact, case-insensitive, and trims
surrounding spaces. Combined filters use AND.

Example: <http://127.0.0.1:8000/components?category=cpu&tier=low&brand=AMD&limit=10&offset=0>.

The response has `items`, `total` (matching rows before pagination), `limit`
(default 20, range 1–100), and `offset` (default 0, nonnegative). Components are
ordered by ID so pagination is deterministic. Invalid parameters return HTTP 422.

Component details include a typed `specs` object for their category. If a manually
entered component has no specifications yet, `specs` is `null`. A component without
offers returns `offers: []`. All offers are included, including out-of-stock and
on-order offers, ordered by price and then store ID. Each offer includes its store,
availability, product URL, and `checked_on` date. Decimal values such as `price_mdl`
are JSON strings (e.g. `"2499.00"`) to preserve precision. Unknown stock quantities
are `null`, rather than zero.

The API reads only from PostgreSQL; it never contacts the stores itself. Parts
and specs are maintained in `seed/seed.sql`; prices, sales and stock can be
refreshed from the store websites on demand with `scripts.check_offers` (below).
There are no automatic or scheduled updates. Catalog editing endpoints are not
yet implemented.

## Accounts and saved builds

Register and log in with JSON `{"email": "...", "password": "..."}`. Emails are
stored lowercased; passwords need 8–128 characters and are stored as argon2
hashes. Login returns `access_token`, `token_type` (`bearer`) and `expires_in`
(seconds, `ACCESS_TOKEN_MINUTES`, default 24 h). Wrong password and unknown
email give the same 401, so accounts can't be probed.

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

- **Where the data comes from:** all four stores embed schema.org Product data
  (current price and availability) in their pages. The sale's regular price is
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

The MVP accepts one component per category: one RAM kit and one storage device.
Partial builds are allowed, but at least one selection is required. IDs must be
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
| Storage | M.2 slot for M.2 NVMe; SATA port for non-M.2 SATA storage |
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
Recommendation generation, Min-Cost Max-Flow, and TOPSIS are future milestones.
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
