# CryptoSignal Project Evaluation

Assessment of the current state and concrete improvement recommendations.

---

## Summary

**Strengths:** Clear domain (Polymarket BTC daily signal bot), solid structure (FastAPI, async Postgres, structured logging), good test count (72 tests), phase-based docs, security-conscious (webhook secret, user whitelist, env-only secrets). **Gaps:** No CI/CD, no static type checking, lint violations (ruff), ad-hoc schema changes, and some doc/observability improvements.

---

## 1. Code Quality & Tooling

### Current state
- **Tests:** 72 tests, `pytest` + `pytest-asyncio`, `respx` for HTTP mocking. All pass.
- **Lint:** Ruff configured (`line-length=100`, `py311`). **34 Ruff errors** (unused imports, E402 imports not at top, unused variables).
- **Type checking:** None (no mypy/pyright in `pyproject.toml`).
- **Format:** No `ruff format` (or black) in README/CI; style may drift.

### Recommendations
1. **Fix Ruff:** Run `uv run ruff check src tests --fix` and fix remaining E402/unsafe by hand (e.g. move imports to top in `signal_runs.py`).
2. **Add Ruff format:** `[tool.ruff.format]` and `uv run ruff format src tests` in README; run in CI.
3. **Add static type checking:** Add `mypy` or `pyright` to `[project.optional-dependencies].dev`, a small config (e.g. `[tool.mypy]` with `strict optional` and exclude untyped deps), and run in CI. Start with `mypy src/app` (no tests) to avoid test-only annotations.
4. **Pre-commit:** Add `.pre-commit-config.yaml` with `ruff check`, `ruff format`, and optionally `mypy`, so lint/format/typecheck run before commit.

---

## 2. CI/CD

### Current state
- No `.github/` directory; no automated tests or deploys on push/PR.

### Recommendations
1. **GitHub Actions:** Add `.github/workflows/ci.yml` that:
   - On push/PR: `uv sync`, `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run pytest`.
   - Optionally: `uv run mypy src/app` when mypy is added.
2. **Deploy:** When you have a target (e.g. Fly, Railway, or a VPS), add a deploy job or separate workflow (e.g. deploy on push to `main` or tag), using secrets for `DATABASE_URL`, `TELEGRAM_*`, etc.

---

## 3. Database & Migrations

### Current state
- Single `schema.sql` as source of truth; `scripts/migrate_*.sql` for additive changes (e.g. `actual_result`, `asset`, `order_book_snapshot`).
- No migration runner (e.g. Alembic); schema applied manually or via `scripts/run_schema.py`.

### Recommendations
1. **Document migration order:** In README or `docs/runbook.md`, list: apply `schema.sql` once, then run `migrate_*.sql` in a defined order (e.g. by date or version). Add a one-line “current schema version” note (e.g. “after migrate_add_order_book_snapshot”).
2. **Optional – Alembic:** For multiple environments and rollbacks, introduce Alembic (or similar), put initial state from current `schema.sql` + migrations into a single “base” revision, then all new changes as new revisions.
3. **Health check:** `/health` already exposes DB; optional: add a simple “schema version” table or key in a table and return it in `/health` for “expected schema” checks after deploy.

---

## 4. Observability & Operations

### Current state
- Structured logging (structlog), JSON in prod.
- `/health` returns 200/503, `last_signal_at`, `data_sources`.
- Runbook covers deploy, rotate keys, cron, replay, outages, monitoring.
- Admin alerts to `ADMIN_CHAT_ID` on webhook errors.

### Recommendations
1. **Structured error response:** For `POST /internal/run-daily-signal` and `run-eod-outcomes`, on 500 return a stable `error_code` (e.g. `daily_signal_failed`) plus `error` message, and always log a correlation id or request id so logs can be tied to a single run.
2. **Metrics (optional):** If you add Prometheus later, expose a `/metrics` with counters for: signal runs, EOD updates, fetcher failures, webhook errors. Not required for MVP but useful as traffic grows.
3. **Runbook:** Add a “Check schema version after deploy” step and reference “Replay missed jobs” for both signal and EOD.

---

## 5. Security

### Current state
- Webhook secret verification; user ID whitelist; secrets in env; security doc and runbook for rotation.
- Internal cron endpoints protected by `X-Cron-Secret` (`EOD_CRON_SECRET`).
- No obvious secret logging.

### Recommendations
1. **Rate limit internal endpoints:** Consider a simple in-process rate limit (e.g. 1 req/min per IP for `/internal/run-daily-signal` and `/internal/run-eod-outcomes`) to reduce impact of secret leakage; document in security.md.
2. **Audit:** Ensure no PII or API keys in logs (search for `logger.*token`, `logger.*secret`, `logger.*password`). Already looks clean; make it explicit in security.md.

---

## 6. Documentation & Structure

### Current state
- README: setup, health, dev (tests, ruff), phases, production, webhook.
- `docs/`: context (data-sources, domain, message-spec, observability, polymarket-spec, runbook, security, signal-spec), phases README, prompts, runbook, sheets templates.
- Code: many modules have docstrings; some endpoints have short docstrings.

### Recommendations
1. **README:** Add “Lint and format” one-liner: `uv run ruff check src tests && uv run ruff format src tests`.
2. **API:** Add a short “Internal API” section in README or `docs/context/` listing: `POST /internal/run-daily-signal`, `POST /internal/run-eod-outcomes`, `POST /internal/admin-heartbeat`, `GET /api/signals`, `GET /api/stats`, all with “X-Cron-Secret when EOD_CRON_SECRET set”.
3. **Changelog:** Keep a minimal `CHANGELOG.md` (or “Releases” in README) for deploy notes and schema migration order.

---

## 7. Dependencies & Packaging

### Current state
- `pyproject.toml`: Python ≥3.11, FastAPI, uvicorn, asyncpg, pydantic, httpx, structlog; dev: pytest, pytest-asyncio, respx, ruff.
- `uv` recommended; Docker Compose for app + Postgres.
- Hatch build; packages = `src/app`.

### Recommendations
1. **Pin upper bounds for prod:** Consider loose upper bounds (e.g. `fastapi>=0.109,<1`) to avoid surprise breakage on major bumps; optional, project policy dependent.
2. **py.typed:** Add empty `src/app/py.typed` to declare the package as typed for PEP 561 (helps mypy/pyright consumers).

---

## 8. Test & Dev Experience

### Current state
- `conftest.py` sets minimal env so `get_settings()` and app startup work.
- Tests are a mix of unit (signal engine, edge, kelly, calibration, resolution) and integration-style (endpoints with TestClient, outcomes, fetchers with respx).
- No coverage gate in CI (no coverage yet).

### Recommendations
1. **Coverage:** Add `pytest-cov`; run `uv run pytest --cov=app --cov-report=term-missing`. Optionally fail CI if coverage drops below a threshold (e.g. 80%) once baseline is set.
2. **Integration tests:** Document that tests assume no real Telegram/Polymarket/DB (respx + env). If you add a “full stack” test against a real DB, use a separate env (e.g. `DATABASE_URL` for test DB) and document in README.
3. **Type annotations in tests:** Use `from __future__ import annotations` where helpful; add return types to test functions for consistency with your style.

---

## Priority Checklist

| Priority | Action |
|----------|--------|
| P0 | Fix all Ruff errors (fix + move imports in `signal_runs.py`). |
| P0 | Add CI workflow: ruff check, ruff format --check, pytest. |
| P1 | Document migration order (schema + migrate_*.sql) in runbook/README. |
| P1 | Add Ruff format to dev workflow and README. |
| P2 | Add mypy or pyright; run in CI. |
| P2 | Add pre-commit config. |
| P2 | py.typed + optional CHANGELOG / API summary. |
| P3 | Optional: Alembic, /metrics, rate limit on internal endpoints, coverage gate. |

---

## Conclusion

The project is in good shape for an MVP: clear scope, working tests, and thoughtful docs/security. The highest-impact improvements are: **clean up Ruff**, **add CI**, and **document schema migration order**. After that, adding **format + type checking** and **pre-commit** will keep quality consistent as the codebase grows.
