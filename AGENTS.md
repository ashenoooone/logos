# Project Instructions

## Goal

Build working MVP as fast as possible. Speed is top priority.

Prioritize shipping speed + simplicity. Keep code readable enough to extend; no overengineering, no premature optimization.

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
- Frontend in `frontend/`: React 19 + Mantine UI 9, TypeScript strict + Vite, pnpm 11.25.0, TanStack Router with code-based routes, TanStack Query for server state. Node.js 24.15.0 in `.nvmrc`, supported `>=24.15.0 <25`; activate it before running pnpm. Exact dependencies in `package.json` and `pnpm-lock.yaml`; no workspace. ESLint, Vitest + Testing Library.
- Frontend follows FEOD (base): layers `app`, `pages`, `modules`, `common`, `globals`, alias `@` → `src`. Profile in `frontend/feod.profile.md`; machine-readable config in `frontend/package.json#feod`; structural rules enforced by `@o-feod/eslint-structure-plugin` in `pnpm lint`. No second `feod.config.json`.
- Database: SQLite file. Path from `LOGOS_DATABASE_PATH`, default `data/logos.sqlite3` relative to the working directory. `.env` is not loaded automatically. Migrations only via explicit `uv run alembic upgrade head`.
- One installation = one company. First integration: Telegram Bot API, not personal Telegram account.
- First admin created by private interactive command, not public registration: `uv run logos-backend create-admin --login <login>`; one row enforced in the DB; rerun never changes the existing admin.
- Backend implemented: `GET /health`, auth/invitations/recovery, manager profile `/account/*` (name, email change with 24 h confirmation link, password change with sign-out of other devices), admin `/admin/channels*` (one Telegram bot by token, background `getUpdates` thread in app lifespan, status connected/error/disconnected), manager inbox `/conversations*` + `/messages/*` (Telegram private chats stored by poller, text/photo/document, attachments in `attachments/` next to SQLite, shared read state, reply with file via raw body ≤20 MiB, delivered/failed + manual retry), tags `/tags*` + `/conversations/{id}/tags*` + admin `/admin/tags*` (case-insensitive unique, manager deletes own, admin any), per-manager sort + saved filters `/conversations/preferences*` + `/conversations/saved-filters*`, migrations 0001–0007, first-admin CLI. Contract in `docs/backend-contract.md`.
- Frontend implemented: session via `/auth/me` + shared CSRF client (`common/api-client.ts`), guards anonymous/authenticated/administrator; manager login `/login` and admin login `/login/admin`; admin `/employees` (list, add, resend/fix invitation); `/invitation` and `/password-reset` (token from `#token`, removed from URL, sent only in body); `/forgot-password` (neutral response, 60 s cooldown). Readiness card kept on authenticated home. Manager `/profile` (name, email, password) and `/email-confirmation` (token from `#token`); `/forgot-password` reachable with or without session. Admin `/channels` (Telegram card, connect form with token check, reconnect, disconnect; status refetched every 10 s). Manager `/inbox` (conversation list + dialog, reply with file, «Не доставлено» + retry; polled every 4 s); header «Входящие N» badge, tab title counter and beep on new incoming via `InboxNavLink` injected into `SessionHeader`. Inbox sort/filters/saved sets + frozen order with «N новых сообщений — Показать» (filtering client-side); tags on dialog + list row (`modules/tags`); admin `/tag-catalog` («Теги»). Dev/preview proxy `/health`, `/auth`, `/admin`, `/invitations`, `/password-reset/`, `/account`, `/conversations`, `/messages`, `/tags`. Production must route same prefixes before SPA fallback; Vite is not the production server.
- #7 + #8 implemented (mockup conflicts with ADR-0007 listed in `docs/open-questions.md`, not yet confirmed); no browser check by agent.
- #5 + #6 implemented; success path with a real bot token (receiving/sending real Telegram messages) not checked by agent.
- #1–#4 implemented (backend + frontend), not accepted: no manual browser acceptance, no end-to-end run with Mailpit by agent yet. No disabling employees, channels, messages.
- Commands: `uv sync --locked`, `uv run alembic upgrade head`, `uv run uvicorn logos_backend.app:app --host 127.0.0.1 --port 8000 --workers 1`, `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src tests`. Run from repo root.
- Frontend commands, from `frontend/`: `pnpm install --frozen-lockfile`, `pnpm dev`, `pnpm build`, `pnpm preview`, `pnpm lint`, `pnpm type-check`, `pnpm test`. Build output `frontend/dist/`. Vite reads frontend env files automatically; `VITE_*` is public, never store secrets there.
- Frontend lint/types/build and 37 tests passed (2026-11-04, auth stage). Proxy split SPA/API checked by real HTTP via Vite dev. Browser tool denied by user policy (`eval`); manual browser acceptance of product screens not yet confirmed. Do not claim visual or browser interaction checks passed.
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
6. Run lint + type checks (+ existing tests touching changed code).
7. Summarize done + remaining.

No approval between steps unless significant ambiguity or risk. Don't stall: pick sensible default, note it in summary.

No mandatory plan files. Outline approach only for genuinely complex tasks, in 2–3 lines.

## Engineering Principles

- Follow existing project conventions.
- Prefer simple, explicit solutions.
- Reuse existing components + utilities.
- Avoid unnecessary abstractions.
- No new dependencies without good reason.
- Don't refactor unrelated code.
- Don't implement features outside current scope.
- Keep changes focused, easy to review.
- Speed over polish, but not over correctness of core flows, security, data integrity.

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

- Default: write no new tests. Lint + type checks are the baseline gate.
- Tests only for critical logic: auth, permissions, password/token handling, data integrity invariants. Minimal coverage — one happy path + key failure case, no exhaustive suites.
- No tests for UI components, routing, simple CRUD, trivial code.
- Existing tests must keep passing; if change breaks one, fix or delete it if it tests removed behavior.
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