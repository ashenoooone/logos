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

## Current Baseline

- Accepted choices recorded in `docs/adr/0001-project-baseline.md`.
- Backend: Python / FastAPI. Frontend: React / Mantine UI. Database: SQLite.
- One installation = one company. First integration: Telegram Bot API, not personal Telegram account.
- First admin created by private deployment command, not public registration.
- Repo currently docs only. No app, dependency manifests, migrations, or runnable checks yet.
- When technical init implemented: replace this status, document real commands. Never invent commands or report unexecuted checks.

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