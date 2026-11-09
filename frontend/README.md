# Frontend

React 19 + TypeScript + Vite single-page app for the PC Configurator. It talks
only to the FastAPI backend in `../backend`.

## Run it

Needs Node.js 22+ (we use 24 LTS). Start the backend first (see
`backend/README.md`), then:

```bash
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server forwards every `/api/...` request to
FastAPI at `http://127.0.0.1:8000` (`vite.config.ts`), so the browser sees a
single origin and the backend needs no CORS setup in development. Point it
elsewhere with `API_TARGET=http://host:port npm run dev`.

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-check (`tsc -b`) and build to `dist/` |
| `npm run lint` | Lint with oxlint |
| `npm run preview` | Serve the production build locally |

## What the pages do

The UI is in Romanian. Styling is Tailwind CSS v4 (`@tailwindcss/vite`); the
design's colour palette and glass effects live in `src/index.css`.

- **Smart (`/`)**: pick a budget, a CPU brand and what the PC is for (gaming,
  office, workstation/AI, video/photo editing); the page calls
  `POST /recommendations` and shows six variants from cheap to near the budget
  (the best TOPSIS-ranked build of each price band, each with a different
  CPU chip + GPU chip pair), with their score, price, CPU, GPU, RAM, storage,
  performance and consumption. The purpose sets the criteria weights and the
  minimum hardware for that use (see the backend README, Recommendations).
- **Manual (`/manual`)**: one row per category, plus an optional second drive
  ("Stocare 2", picked from storage). With "Compatibilitate auto" on,
  each dropdown asks the AC-3 endpoint (`POST /compatibility/filter`) and hides
  parts that no longer fit. After each change the summary calls
  `POST /compatibility/check` (verdict, conflicts, power vs PSU) and
  `POST /purchase/plan` (which store to buy each part from, Min-Cost Max-Flow).
  Signed-in users can save the build, or save changes to a build they opened.
- **Șabloane (`/sabloane`)**: the six templates with live totals and a live
  compatibility check; "Încarcă în Manual" opens one in the manual builder.
- **Exchange (`/exchange`)**: converter and site-wide display currency. Rates
  are fixed and approximate (`src/lib/currencies.ts`); every real price is in MDL.
- **Fondatori (`/fondatori`)**: the team. Clicking an avatar uploads a photo,
  stored only in that browser.
- **Autentificare (`/autentificare`)** and **Cont (`/cont`)**: register or sign
  in (token in `localStorage`), then list, open or delete saved builds.

## Code layout

```
src/
  api/          types.ts (backend response shapes), client.ts (fetch wrapper)
  auth/         AuthContext: current user, login, register, logout
  builder/      BuilderContext (catalog, selection, live compatibility + plan),
                useTemplates (template totals and checks)
  context/      CurrencyContext (display currency), ToastContext (notifications)
  components/   Header, Logo, CategoryRow, PartLabel, PriceTag, ManualSummary,
                BuildCard, Flag, GlowTracker
  pages/        Smart, Manual, Templates, Exchange, Founders, Auth, Account
  lib/          catalog.ts (labels, icons, spec summaries), templates.ts,
                currencies.ts
  index.css     Tailwind theme and the design's custom classes
```

## Deploying

`npm run build` produces static files in `dist/`. Serve them so that `/api` reaches
the backend (a reverse proxy), or build with `VITE_API_BASE=https://api.example.com`
and enable CORS for the site's origin in the backend.

### Netlify

`netlify.toml` (repository root) builds this folder and publishes `dist/`. Netlify
serves only the frontend; the backend runs on its own server (it needs PostgreSQL
and keeps `data/users.vault` and `logs/` on disk).

1. In Netlify, *Add new site → Import an existing project* and pick this
   repository. The base directory, build command and publish folder come from
   `netlify.toml`.
2. In *Site configuration → Environment variables*, set `BACKEND_URL` to the
   backend's public URL, e.g. `https://api.example.com`. The build fails without it.
3. Deploy.

`scripts/netlify-redirects.mjs` writes `dist/_redirects` at build time so that
`/api/*` is proxied to `BACKEND_URL` (prefix stripped, as in development). The
browser only talks to the Netlify origin, so the backend needs no CORS setup. Any
other path that isn't a file serves `index.html`, so links like `/manual` and page
reloads work. After changing `BACKEND_URL`, redeploy.
