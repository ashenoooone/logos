# Frontend Agent Guide

Scope: everything under `frontend/`. The root [`../AGENTS.md`](../AGENTS.md) still applies;
this file adds frontend-specific rules.

## Engineering principles

### KISS — Keep It Simple

- Solve the current problem with the smallest readable solution.
- Prefer plain functions and explicit code over abstractions, factories and indirection.
- Do not introduce a new layer, hook, context or dependency without a concrete need.
- If a file is hard to explain in one sentence, simplify it.

### DRY — Don't Repeat Yourself

- Reuse existing components, hooks and utilities before writing new ones.
- Extract shared code only when the same behaviour is needed in at least two real places.
- DRY is about knowledge, not lines: two similar snippets that change for different
  reasons should stay separate.
- Never "reuse" by importing another module's internals — share through a module's
  public API or move the entity to `common`.

### YAGNI — You Aren't Gonna Need It

- Implement only what the story and acceptance criteria require.
- No speculative props, options, configuration, generic wrappers or "future" features.
- Delete dead code instead of keeping it "just in case".
- Add a dependency only when the standard library or an existing package cannot do the job.

## Architecture — FEOD

FEOD (Fractal Entity Oriented Design) is built around **modules**, not folders.
Layers exist to keep modules isolated; they are not abstraction levels.
The two pillars are **modularity** and **fractality** (submodules inside modules).

### Layers

```
common → modules → pages → app
global — never imported (available without import, .d.ts via tsconfig)
```

| Layer     | Purpose                                                      | May import                          | Imported by                  |
| --------- | ------------------------------------------------------------ | ----------------------------------- | ---------------------------- |
| `global`  | shims, polyfills, `.d.ts`                                    | —                                   | nobody (wired by tsconfig)   |
| `common`  | small reusable entities, usually one file; staging area      | `common`                            | `modules`, `pages`, `app`    |
| `modules` | isolated business logic with a public API                    | `common`, other modules via `index.ts` | `modules`, `pages`, `app` |
| `pages`   | URL → component, thin                                        | `common`, `modules`                 | `app`                        |
| `app`     | bootstrap, router, layouts, integrations, IoC wiring         | everything below                    | nobody                       |

`common` is a temporary staging area, not a "shared" dump: entities move to a module
once they gain domain meaning.

### Module anatomy

```
src/modules/health/
  index.ts              # the only public API of the module
  api/
  components/
  hooks/
  README.md
```

- `index.ts` is **only** for the module public API. Do not add barrels in `common`.
- A module is not created "for one utility": use `common` or a module submodule.
- Submodules live in `modules/<module>/modules/<submodule>/`; outside code uses the
  parent's public API only.
- Module pages (`modules/<module>/pages/`) are preferred over top-level pages for
  domain-specific URLs.

### Import rules

| Import type                 | Path                                                       |
| --------------------------- | ---------------------------------------------------------- |
| Cross-layer                 | `@/modules/health` (alias `@` → `src`)                     |
| Cross-module                | public API only: `@/modules/health` → `index.ts`           |
| In-level (pages)            | `./home-page`                                              |
| In-module                   | relative: `../hooks/use-health-check`                      |
| `common` → `modules`        | only via IoC (interface + implementation wired in `app`)   |
| npm packages                | allowed anywhere                                           |

- Never import module internals from outside the module
  (`@/modules/health/api/health` is forbidden).
- No zigzag imports between modules; couple through public APIs or IoC.
- Pages and `app` hold no business logic.
- Avoid pseudo-modules such as `utils`, `types`, `constants`; group by meaning.

### Project specifics

- Structure is enforced by `@o-feod/eslint-structure-plugin` during `pnpm lint`.
- Profile: [`feod.profile.md`](feod.profile.md) and `package.json#feod`. Do not create
  `feod.config.json`.
- Routing is manual TanStack Router code in `src/app/router.tsx`.
- Server state goes through TanStack Query: `queryOptions` live next to the API
  functions in `modules/<module>/api/`, the single `QueryClient` is created in
  `src/app/config/query-client.ts`.
- Mantine theme lives in `src/app/config/theme.ts`; shared test setup in
  `src/app/test/`.
- Layers are `app`, `pages`, `modules`, `common`, `globals` (folder `globals` maps to
  the `global` layer).

## Naming

- Files and folders use **kebab-case**: `health-status-card.tsx`, `use-health-check.ts`,
  `home-page.tsx`, `src/modules/health/`.
- React components and exported symbols keep JavaScript conventions inside code:
  `HealthStatusCard`, `useHealthCheck`, `checkHealth`. Kebab-case applies to paths, not
  identifiers.
- Tests are colocated and named `<subject>.test.ts(x)`.
- One component per file, file name matches the exported component in kebab-case.

## Commands

Run from `frontend/` with Node from `.nvmrc` (`24.15.0`) active:

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm build        # tsc --noEmit && vite build
pnpm lint
pnpm type-check
pnpm test
```

Definition of done: `pnpm lint`, `pnpm type-check`, `pnpm test` and `pnpm build` pass.
Report only checks that were actually executed.
