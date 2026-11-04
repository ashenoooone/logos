# Project Instructions

## Goal

Build working MVP fast without making codebase unmaintainable mess.

Prioritize simplicity, correctness, maintainability over premature optimization and overengineering.

## Project Knowledge

Project docs stored locally:

- `docs/stories/` — user stories + acceptance criteria.
- `docs/adr/` — architectural decisions.
- `docs/domain/` — business rules, domain knowledge.
- `CONTEXT.md` — domain glossary; no implementation details.
- `docs/stories/README.md` — GitHub mapping, snapshot dates, dependencies, refresh procedure.
- `docs/open-questions.md` — unresolved requirements + technical decisions, grouped by implementation stage.
- `docs/backend-contract.md` — implemented HTTP endpoints, errors, CLI behavior.

## Current Baseline

- Accepted choices recorded in `docs/adr/0001-project-baseline.md` through `docs/adr/0005-frontend-feod.md`.
- Backend: Python 3.13 + uv, FastAPI + Uvicorn, sync SQLAlchemy 2 + Alembic, argon2-cffi; pytest, Ruff, mypy. Versions pinned in `uv.lock`.
- Frontend in `frontend/`: React 19 + Mantine UI 9, TypeScript strict + Vite, pnpm 11.25.0, TanStack Router with code-based routes. Node.js 24.15.0 in `.nvmrc`, supported `>=24.15.0 <25`; activate it before running pnpm. Exact dependencies in `package.json` and `pnpm-lock.yaml`; no workspace. ESLint, Vitest + Testing Library.
- Frontend follows FEOD (base): layers `app`, `pages`, `modules`, `common`, `globals`, alias `@` → `src`. Profile in `frontend/feod.profile.md`; machine-readable config in `frontend/package.json#feod`; structural rules enforced by `@o-feod/eslint-structure-plugin` in `pnpm lint`. No second `feod.config.json`.
- Database: SQLite file. Path from `LOGOS_DATABASE_PATH`, default `data/logos.sqlite3` relative to the working directory. `.env` is not loaded automatically. Migrations only via explicit `uv run alembic upgrade head`.
- One installation = one company. First integration: Telegram Bot API, not personal Telegram account.
- First admin created by private interactive command, not public registration: `uv run logos-backend create-admin --login <login>`; one row enforced in the DB; rerun never changes the existing admin.
- Backend implemented: single `GET /health` readiness endpoint, `administrators` migration, first-admin CLI. Contract in `docs/backend-contract.md`.
- Frontend implemented: technical readiness screen with real `/health`, loading, distinct backend 503/network/other HTTP failures, manual retry, abort on unmount, unknown-route page and link home. Dev and preview proxy to `127.0.0.1:8000`; stopped backend actually returns proxy HTTP 502. Production requires separate same-origin `/health` routing before SPA fallback; Vite is not the production server.
- No user story implemented: no login, sessions, registration, invitations, channels, messages, or admin HTTP API.
- Commands: `uv sync --locked`, `uv run alembic upgrade head`, `uv run uvicorn logos_backend.app:app --host 127.0.0.1 --port 8000 --workers 1`, `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src tests`. Run from repo root.
- Frontend commands, from `frontend/`: `pnpm install --frozen-lockfile`, `pnpm dev`, `pnpm build`, `pnpm preview`, `pnpm lint`, `pnpm type-check`, `pnpm test`. Build output `frontend/dist/`. Vite reads frontend env files automatically; `VITE_*` is public, never store secrets there.
- Frontend lint/types/build and 18 tests passed; real dev/preview HTTP 200/503/502 and SPA shell fallback checked. Browser tool was denied by user policy (`eval`); user explicitly chose manual browser acceptance. It is not yet confirmed. See `docs/frontend-handoff.md`; do not claim visual or browser interaction checks passed.
- Never invent commands or report unexecuted checks.

## Requirements Sources

- GitHub issues = source of user stories; local story files = verbatim snapshots.
- Before implementing, check relevant issue body, comments, `updatedAt`; follow refresh procedure in `docs/stories/README.md`.
- Accepted ADRs hold explicitly approved project decisions absent from original stories.
- Keep implementation notes + progress outside imported stories.
- Derived rules and suggested sequencing add no new acceptance criteria.
- Resolve conflicts between issue, accepted ADR, mockup explicitly; never silently pick one.
- Mockup links preserved in stories, but images not inspected. Don't infer missing fields, password requirements, permissions, or provider capabilities.

Read only docs relevant to current task. Don't load whole knowledge base needlessly.

## Workflow

When asked to implement user story:

1. Find + read relevant story in `docs/stories/`; verify GitHub source current.
2. Identify acceptance criteria + dependencies.
3. Read relevant ADRs + domain rules.
4. Inspect existing code + patterns.
5. Implement simplest complete solution.
6. Run relevant checks + tests.
7. Summarize done + remaining.

No approval between steps unless significant ambiguity or risk.

Complex tasks: briefly outline approach before implementing. No mandatory plan files.

## Engineering Principles

- Follow existing project conventions.
- Prefer simple, explicit solutions.
- Reuse existing components + utilities.
- Avoid unnecessary abstractions.
- No new dependencies without good reason.
- Don't refactor unrelated code.
- Don't implement features outside current scope.
- Keep changes focused, easy to review.
- Never sacrifice correctness for speed.

## MVP Rules

- Implement only what story requires.
- Prefer working solutions over theoretical flexibility.
- Avoid speculative features + premature optimization.
- Temporary solutions OK when isolated, understandable, safe.
- No shortcuts compromising security, data integrity, or critical business logic.
- Document significant technical compromises briefly.

## Architecture & ADR

Follow existing accepted ADRs.

New ADR only for significant architectural decision affecting future development.

Lightweight format:

- Context
- Decision
- Consequences

No ADRs for minor implementation details. New ADRs stay proposed until approved.

## Testing

- Verify story's acceptance criteria.
- Run relevant existing tests, lint, type checks.
- Add tests for important business logic + regressions.
- No needless tests for trivial code.
- Never claim checks passed unless executed.

## Documentation

- Keep imported user stories unchanged.
- Update docs when behavior or architecture changes.
- Avoid docs duplicating code.
- Keep docs concise, useful.

## Completion

After implementation, give short summary:

- What implemented.
- What verified.
- Remaining issues or tech debt.

Never mark incomplete work complete.