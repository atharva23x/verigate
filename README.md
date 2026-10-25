# VeriGate — Deployment Bundle

Everything needed to **build and deploy VeriGate** lives in this folder.
It is self-contained: no files outside this directory are required.

```
verigate-deploy/
├── README.md              ← you are here (deployment guide)
├── PROJECT_README.md      ← full project docs, demo scenarios, architecture
├── docker-compose.yml     ← one-command deployment (recommended)
├── deploy.bat             ← build + start with Docker          [Windows]
├── stop.bat               ← stop the deployment               [Windows]
├── logs.bat               ← follow live logs                  [Windows]
├── reset.bat              ← stop and wipe the database        [Windows]
├── dev.bat                ← run WITHOUT Docker (hot reload)    [Windows]
├── scripts/
│   ├── dev.ps1            ← the logic behind dev.bat
│   └── healthcheck.ps1    ← verifies backend + frontend are up
├── backend/               ← FastAPI app (Python 3.11–3.13)
│   ├── main.py, app/
│   ├── requirements.txt, requirements-ocr.txt
│   ├── Dockerfile, .dockerignore, .env.example
│   └── test_*.py          ← API test suites
└── frontend/              ← React + Vite + Tailwind app
    ├── src/, public/, index.html
    ├── package.json, package-lock.json
    ├── vite.config.ts, tsconfig*.json, tailwind.config.js, postcss.config.js
    ├── Dockerfile, nginx.conf, .dockerignore, .env.example
```

> Excluded on purpose (not needed to build): `node_modules/`, `venv/`,
> `dist/`, `__pycache__/`, `*.db`, `storage/`, screenshots, e2e scripts.

---

## Option A — Deploy with Docker (recommended)

**Prerequisite:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + compose plugin).

```bat
deploy.bat
```

That single command builds both images and starts the stack:

| Service  | URL                         |
| -------- | --------------------------- |
| Frontend | http://localhost:5173       |
| Backend  | http://localhost:8000       |
| API docs | http://localhost:8000/docs  |
| Health   | http://localhost:8000/health|

Other commands (double-click):

- `logs.bat` — stream logs (first boot seeds ~30 applications, takes ~30 s)
- `stop.bat` — stop containers, **keep** the data
- `reset.bat` — stop containers and delete the database volume (fresh seed on next start)

Manual equivalent:

```powershell
docker compose up --build -d     # start
docker compose logs -f           # logs
docker compose down              # stop (keep data)
docker compose down -v           # stop + wipe data
```

---

## Option B — Run locally without Docker (dev mode)

**Prerequisites:** Python 3.11–3.13 (3.12 recommended) and Node.js 20+.

```bat
dev.bat
```

It will, on first run only:

1. create `backend\venv` and install `requirements.txt`
2. run `npm install` in `frontend\`
3. open two terminals: backend on **:8000**, frontend on **:5173**

Manual equivalent:

```powershell
# Terminal 1 — backend
cd backend
py -3.12 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

---

## Deploy to Vercel (frontend only)

> Vercel hosts **static sites only** — it cannot run the FastAPI backend.
> The Vercel site will need a separately hosted API (see below).

**Correct root folder: `frontend/`** (the folder that contains `index.html` +
`package.json`). Deploying `verigate-deploy/` itself gives a blank screen,
because the app's entry file is at `frontend/index.html`, not at the root.

Two ways:

1. **Drag & drop** — drag the **`frontend`** folder (not the whole bundle)
   onto https://vercel.com/new. Vercel auto-detects Vite and runs
   `npm run build`, output `dist`.
2. **Existing project** — Vercel dashboard → your project →
   *Settings → General → Root Directory* → set it to `frontend` → Save →
   *Deployments → ⋯ → Redeploy*.

`frontend/vercel.json` already contains the SPA rewrite so deep links
(`/login`, `/queue`, …) don't 404.

### Point the frontend at your API

The built app calls `VITE_API_URL` (default `http://localhost:8000`, which
does not exist for a Vercel visitor). After the backend has a public URL:

1. Vercel → *Settings → Environment Variables* → add
   `VITE_API_URL = https://your-backend.onrender.com`
2. Redeploy (env vars are baked in at build time).

The backend allows any origin (`CORS allow_origins=["*"]`), so no CORS edit
is needed.

---

## Production build notes

- **Frontend:** `cd frontend && npm run build` → static files in `frontend\dist\`,
  serve with any static server (the bundled `nginx.conf` shows SPA-fallback config).
  Set `VITE_API_URL` in `frontend\.env` **before building** if the API is not on
  the same host — it is baked in at build time.
- **Backend:** `uvicorn main:app --host 0.0.0.0 --port 8000` behind your reverse
  proxy (TLS at the proxy). Configure `backend\.env` first.
- **Never ship the default secret** — set a strong `JWT_SECRET`.

### Configuration (`backend\.env` — copy from `backend\.env.example`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `MOCK_MODE` | `True` | Demo safeguard: never depends on heavy OCR/ML |
| `SEED_ON_STARTUP` | `True` | Seeds 30 synthetic applications when the DB is empty |
| `JWT_SECRET` | demo value | **Change in production** |
| `JWT_EXPIRES_MIN` | `480` | Token lifetime |
| `VERIGATE_DB` | `verigate.db` | SQLite path |
| `VERIGATE_STORAGE` | `storage` | Uploads / page renders / ELA images |
| `OCR_CONFIDENCE_THRESHOLD` | `0.90` | Evidence Gate threshold |
| `ISSUER_OUTAGE_PORTALS` | empty | Comma-separated portals to simulate as down |

---

## Verify the deployment

```powershell
powershell -File scripts\healthcheck.ps1
```

Sign in at http://localhost:5173 with a demo account:

| Username | Password | Role |
| --- | --- | --- |
| `officer1` | `officer123` | officer (upload, validate, decide) |
| `reviewer1` | `reviewer123` | reviewer (approve / reject / request) |
| `auditor1` | `auditor123` | auditor (read-only, exports audit) |

---

## Troubleshooting

- **Port already in use** — something else holds 5173/8000:
  `netstat -ano | findstr :5173` then stop that process.
- **First boot seems stuck** — seeding 30 applications runs the full pipeline
  and takes ~30 s; watch `logs.bat`.
- **Frontend can't reach the API** — check `VITE_API_URL` (must be reachable
  from the *browser*, e.g. `http://localhost:8000`) and rebuild.
- **Start from scratch** — `reset.bat` (Docker) or delete `backend\verigate.db`
  and the `backend\storage\` folder (local).

More detail: [PROJECT_README.md](PROJECT_README.md).
