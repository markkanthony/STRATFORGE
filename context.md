# StratForge Context

## Active Product Surface

- Active frontend: `web/` (React + Vite + TanStack Query + shadcn/radix UI)
- Active backend: `api/` (FastAPI)
- Active engine: `run.py`, `strategy.py`, `core/`, `signals/`, `viz/`
- Legacy Dash UI under `ui/` was removed

## How To Run

Backend:

```powershell
uvicorn api.main:app --reload --port 8000
```

Frontend:

```powershell
cd web
npm.cmd run dev
```

Frontend URL:

- `http://localhost:5173`

Backend URL:

- `http://localhost:8000`
- docs: `http://localhost:8000/docs`

## Current App Routes

Defined in `web/src/App.tsx`.

- `/dashboard`
- `/pricing`
- `/projects/:projectId`
- `/projects/:projectId/strategies/:strategyId`
- `/projects/:projectId/runs/:runId`
- `/settings`

`/login` and `/register` currently redirect to `/dashboard`.

## Current UX Structure

### Dashboard

File: `web/src/pages/Dashboard.tsx`

Purpose:

- portfolio-style workspace overview
- project analytics
- recent project activity
- attention queue for projects needing work
- project creation modal

### Project Workspace

File: `web/src/pages/ProjectDetail.tsx`

Purpose:

- strategy rail on the left
- selected strategy summary
- run history table
- integrated run review section with chart + trades
- quick path into strategy builder

### Strategy Builder

File: `web/src/pages/StrategyEditor.tsx`
Main component: `web/src/components/StrategyBuilder.tsx`

Purpose:

- edit indicators, patterns, Python entry code, exits, risk
- save config into `Strategy.config_json`
- trigger a run from the builder

### Run Review

File: `web/src/pages/RunDetail.tsx`

Purpose:

- review one run in isolation
- toggle train vs validation
- chart, metrics, and trades

## Backend Model Summary

Main ORM models in `api/models.py`:

- `User`
- `Project`
- `Strategy`
- `Run`

Relationships:

- user -> many projects
- project -> many strategies
- strategy -> many runs

## Important Semantics

### Strategy Entry Model

Strategies are now **Python-first** for entry logic.

Current behavior:

- `Strategy.config_json` keeps structured `backtest`, `strategy`, and `risk` sections
- `strategy.entry_code` is now the canonical entry definition
- `strategy.entry_contract_version` is currently `1`
- entry code must define:

```python
def generate_entry(df):
    long_mask = ...
    short_mask = ...
    return long_mask, short_mask
```

- backend injects `pd`, `np`, and the fully prepared DataFrame into that code
- helper rule columns can still exist, but they are no longer the primary editing model
- legacy `long_require_all` / `short_require_all` strategies are not supported by the web editor anymore

Important files:

- `strategy.py`
- `api/routers/strategies.py`
- `web/src/lib/strategy.ts`
- `web/src/components/StrategyBuilder.tsx`
- `web/src/pages/StrategyEditor.tsx`

### Project Timeframe

Projects are **not** timeframe-constrained anymore.

Current behavior:

- project stores `name`, `description`, `symbol`
- project creation does not ask for symbol; backend assigns the default symbol from the active provider
- the web shell preloads provider-backed symbols at startup
- pair selection lives on the project workspace page
- runner falls back to base `config.yaml` if strategy config does not override timeframe
- runs use the project symbol unless a one-off `symbol_override` is supplied
- strategies can enable a higher-timeframe trend filter through:
  - `backtest.timeframe` for the execution chart
  - `strategy.context.use_higher_timeframe`
  - `strategy.context.higher_timeframe`

Relevant files:

- `api/schemas.py`
- `api/routers/projects.py`
- `api/runner.py`

## Run Execution Flow

1. User triggers run from project page or strategy builder.
2. FastAPI route in `api/routers/runs.py` loads strategy + project.
3. `api/runner.py` builds engine config:
   - symbol from project or run-level override
   - timeframe from `strategy.config_json.backtest.timeframe` if present
   - otherwise uses base `config.yaml`
4. Existing engine runs through `run.py`.
5. Artifacts still go to `results/`.
6. Run row stores metadata and artifact path.

## Multi-Timeframe Support

- execution timeframe still comes from `backtest.timeframe`
- higher-timeframe confirmation is computed in `strategy.py`
- when enabled, the engine resamples the price series to the configured higher timeframe
- trend state is projected back onto base bars using the last completed higher-timeframe bar only
- if higher timeframe is omitted or matches the execution timeframe, strategy logic falls back to the base-chart trend filter

## Prepared Columns For Python Entry

The DataFrame passed to `generate_entry(df)` can include:

- OHLCV/time columns
- `session`
- `ema_fast`, `ema_slow`, `ema_trend`
- `rsi`, `atr`
- `bb_mid`, `bb_upper`, `bb_lower`
- pattern/context columns such as:
  - `bullish_engulfing`
  - `bearish_engulfing`
  - `inside_bar`
  - `sweep_prev_high`
  - `sweep_prev_low`
  - `orb_breakout_long`
  - `orb_breakout_short`
  - `prev_day_high`
  - `prev_day_low`
- helper boolean rule columns from `build_rule_features()` may still be present

## Data Source Flow

The engine still tries:

1. MetaTrader 5
2. CSV fallback in `data/`

Core loader logic lives in `core/data_feed.py`.

## Mock Mode / Dev Mode

Mock API data is in:

- `web/src/api/mock.ts`

Seeded mock strategies now use `strategy.entry_code`, not legacy rule arrays.

Frontend API client:

- `web/src/api/client.ts`

React data hooks:

- `web/src/hooks/useProject.ts`
- `web/src/hooks/useRun.ts`
- `web/src/hooks/useAuth.ts`

## Design System / UI Notes

- global tokens and visual system: `web/src/index.css`
- shell/layout:
  - `web/src/components/layout/AppShell.tsx`
  - `web/src/components/layout/Sidebar.tsx`
  - `web/src/components/layout/Topbar.tsx`
- shadcn-style UI primitives live in `web/src/components/ui/`

Current visual direction:

- dark operator surface
- warm primary accent
- restrained data-heavy layout
- dashboard-first orientation

## Cleanup Already Done

- removed legacy `ui/` Dash app
- removed old unused web files:
  - `web/src/App.css`
  - `web/src/pages/Landing.tsx`
  - `web/src/pages/Login.tsx`
  - `web/src/pages/Register.tsx`
  - unused starter assets under `web/src/assets/`
- removed generated workspace caches/logs:
  - root `__pycache__`
  - project `__pycache__` folders outside venv
  - `api_server.log`
  - root stray `package-lock.json`
  - `web/dist/`
- removed unused frontend dependency:
  - `@fontsource-variable/geist`

## Known Caveats

- `npm.cmd run build` passes
- Vite build still emits lightningcss warnings about `@theme` / `@utility` from the current CSS toolchain, but build succeeds
- repo may still contain user-created untracked or in-progress files in `web/`; do not assume a clean git state

## Recommended Next Agent Entry Points

If working on product UI:

- start with `web/src/App.tsx`
- then `web/src/pages/Dashboard.tsx`
- then `web/src/pages/ProjectDetail.tsx`

If working on strategy/run behavior:

- start with `api/routers/runs.py`
- then `api/runner.py`
- then `run.py`

If working on project creation/editing:

- start with `api/routers/projects.py`
- then `api/schemas.py`
- then `web/src/api/client.ts`
- then `web/src/hooks/useProject.ts`
