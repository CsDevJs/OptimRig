# OptimRig

A PC configurator: a React site (`frontend/`) and a FastAPI + PostgreSQL API
(`backend/`). See each folder's README for development.

## Deploying on Vercel

`vercel.json` deploys both parts as one Vercel project with two services:

| Service | Folder | Public at |
|---|---|---|
| `frontend` | `frontend/` (Vite) | `/` |
| `backend` | `backend/` (FastAPI, `app/main.py`) | `/api/*` |

The site calls `/api/...` on its own domain, so it needs no CORS or backend address.
The backend accepts its routes with or without the `/api` prefix.

On Vercel (`VERCEL=1`) the backend's disk isn't kept, so by default:
- the encrypted users vault is stored in the database (`user_vault` table) instead of
  `data/users.vault`, still encrypted with `VAULT_KEY`;
- the activity log goes to Vercel's logs (project → *Logs*) instead of `logs/`;
- connections aren't pooled by the app; use the database's pooled address.

### 1. Create the Vercel project

*Add New → Project*, import this repository, and leave *Root Directory* at the
repository root (`vercel.json` defines the services). The first deployment can fail
until steps 2 and 3 are done; that's expected.

### 2. Add the database and the secrets

1. In the project: *Storage → Create Database → Neon (Postgres)*, and connect it to
   the project. This adds `DATABASE_URL` (pooled; the backend uses it) and
   `DATABASE_URL_UNPOOLED` (direct; for step 3) to its environment variables.
2. *Settings → Environment Variables*, add:
   - `JWT_SECRET`: a long random value
     (`python -c "import secrets; print(secrets.token_urlsafe(48))"`);
   - `VAULT_KEY`: the one in your `backend\.env` if you'll copy your accounts (step 3),
     otherwise a new one
     (`python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`).
     Keep a copy somewhere safe: without it no account can be opened.

### 3. Fill the database from your computer

In PowerShell, in `backend\`, point the commands at the new database for this window
only (your `.env` stays unchanged), using the `DATABASE_URL_UNPOOLED` value:

```powershell
$env:DATABASE_URL = "postgresql://...the DATABASE_URL_UNPOOLED value..."
```

Then either **copy your local database** (catalog, accounts and saved builds):

```powershell
pg_dump --no-owner --no-privileges -Fc -d "postgresql://pc_app:YOUR_PASSWORD@localhost:5432/pc_configurator" -f optimrig.dump
pg_restore --no-owner --no-privileges -d $env:DATABASE_URL optimrig.dump
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m scripts.vault copy-to-database
```

`copy-to-database` copies `data\users.vault`, still encrypted, so the project must
use the same `VAULT_KEY` as your `.env`. `pg_dump` must be at least as new as the
database's PostgreSQL version.

Or **start empty** (catalog from the seed data, no accounts):

```powershell
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m scripts.seed
```

### 4. Deploy

*Deployments → ⋯ → Redeploy* on the latest one (it picks up the new variables). Then
`https://<project>.vercel.app/api/health/db` should answer `{"status":"ok"}`.

Every push to `main` redeploys. After a schema change, run `alembic upgrade head`
against the database (step 3) before or right after deploying. To update prices or the
catalog, run the catalog scripts on your computer with `DATABASE_URL` set as in step 3.
