# StratForge

StratForge is a deterministic Python backtesting engine with a new SaaS wrapper on top.

The engine layer stays intact:

- `run.py` for direct backtests
- `ai_loop.py` for local AI iteration
- `strategy.py`, `core/`, and the existing signal modules

The new product surface adds:

- a FastAPI backend in `api/`
- a React + Vite frontend in `web/`
- user auth, projects, strategies, runs, chart review, and Stripe billing hooks

The legacy Dash UI in `ui/` still works for local-only usage.

## Requirements

- Python 3.11+
- Node.js 20+ and npm
- MetaTrader 5 is optional
- An Anthropic API key is only required for `ai_loop.py`
- A Stripe account is only required if you want billing routes to work

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/markkanthony/STRATFORGE.git
cd STRATFORGE

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
cd web
npm install
cd ..
```

If PowerShell blocks `npm`, use `npm.cmd install` and `npm.cmd run dev` instead.

## Environment Setup

Create a backend `.env` file from the example:

```bash
# macOS / Linux
cp .env.example .env

# PowerShell
Copy-Item .env.example .env
```

Important variables:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | JWT and auth secrets |
| `DATABASE_URL` | SQLite for dev, PostgreSQL for production |
| `FRONTEND_URL` | CORS and Stripe redirect base URL |
| `STRIPE_SECRET_KEY` | Required for Checkout and billing portal |
| `STRIPE_WEBHOOK_SECRET` | Required for webhook verification |
| `STRIPE_PRICE_PRO` | Stripe price ID for Pro |
| `STRIPE_PRICE_ELITE` | Stripe price ID for Elite |

Default local development uses SQLite and creates `stratforge.db` automatically on first API startup.

## Usage

### SaaS mode

Start the API:

```bash
uvicorn api.main:app --reload --port 8000
```

Start the frontend in a second terminal:

```bash
cd web
npm run dev
```

Then open:

- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Local Vite development already proxies `/api` and `/auth` to `http://localhost:8000`, so you do not need `VITE_API_URL` for local use.

Typical SaaS workflow:

1. Register a user account.
2. Create a project with a symbol and timeframe.
3. Create or edit a strategy in the visual builder.
4. Trigger a backtest from the project page or strategy editor.
5. Open the run detail page to inspect chart data, trades, and metrics.
6. Open Settings or Pricing if Stripe billing is configured.

### CLI engine mode

Run the original backtest pipeline directly:

```bash
python run.py
```

This still produces the usual engine artifacts under `results/`, including:

| Path | Description |
| --- | --- |
| `results/run_001.json` | Full run artifact with trades, metrics, and config snapshot |
| `results/latest.json` | Latest run summary |
| `results/history.jsonl` | Append-only run log |
| `results/run_001/` | Static charts and HTML summary |

### Legacy Dash UI

Run the original local dashboard:

```bash
python ui/app.py
```

Then open `http://127.0.0.1:8081`.

This mode reads directly from `results/` and does not use the FastAPI backend or the React frontend.

### AI loop

Set your Anthropic API key first:

```bash
# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows Command Prompt
set ANTHROPIC_API_KEY=sk-ant-...

# PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

Then run:

```bash
python ai_loop.py
```

`ai_loop.py` is still a local engine workflow. It is not wired into the SaaS UI.

## Data Sources

StratForge tries MetaTrader 5 first, then falls back to CSV automatically.

### MetaTrader 5

1. Open MetaTrader 5 and log into your broker account.
2. Make sure the symbol in `config.yaml` is available in Market Watch.
3. Run `python run.py` or trigger a run through the API/UI.

### CSV fallback

Place a CSV file at `data/fallback.csv` with this header:

```csv
time,open,high,low,close,tick_volume
2023-01-02 00:00:00,1.07016,1.07027,1.07004,1.07016,2085
```

The repo already includes a fallback dataset so the engine can run without MT5.

## Main Application Surfaces

### Backend

The FastAPI backend lives in `api/` and provides:

- `/auth/*` for register/login/JWT user flows
- `/api/projects` for project CRUD
- `/api/projects/{id}/strategies` and `/api/strategies/{id}` for strategy CRUD
- `/api/strategies/{id}/runs` and `/api/strategies/{id}/runs/trigger` for run history and execution
- `/api/runs/{id}/chart-data`, `/trades`, and `/metrics` for review surfaces
- `/api/library/indicators` and `/patterns` for the strategy builder
- `/api/billing/*` for Stripe checkout, portal, webhook, and billing status

### Frontend

The React app lives in `web/` and provides:

- landing page and pricing
- login and registration
- dashboard with project cards
- project detail with strategy list and run history
- strategy editor with the visual builder
- run detail with chart, trades, and metrics
- settings with billing status and portal actions

## Development Notes

- The FastAPI app auto-creates tables on startup.
- The async runner wraps the unchanged engine and stores run metadata in the database.
- Run artifacts still live in `results/`, and database rows store the artifact path.
- Stripe routes return configuration errors until Stripe keys and price IDs are provided.

## Useful Commands

```bash
# Backend health
curl http://localhost:8000/health

# Run the backend
uvicorn api.main:app --reload --port 8000

# Run the frontend
cd web
npm run dev

# Production frontend build
cd web
npm run build

# Legacy local UI
python ui/app.py

# Direct engine run
python run.py
```
