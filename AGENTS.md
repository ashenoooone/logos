# Project Instructions

## Goal

Build a working MVP as quickly as possible without
turning the codebase into an unmaintainable mess.

Prioritize simplicity, correctness, and maintainability
over premature optimization and overengineering.

## Project Knowledge

Project documentation is stored locally:

- `docs/stories/` — user stories and acceptance criteria.
- `docs/adr/` — architectural decisions.
- `docs/domain/` — business rules and domain knowledge.

Read only the documentation relevant to the current task.
Do not load the entire knowledge base unnecessarily.

## Workflow

When asked to implement a user story:

1. Find and read the relevant story in `docs/stories/`.
2. Identify acceptance criteria and dependencies.
3. Read relevant ADRs and domain rules.
4. Inspect the existing code and patterns.
5. Implement the simplest complete solution.
6. Run relevant checks and tests.
7. Summarize what was done and what remains.

Do not require approval between steps unless
there is a significant ambiguity or risk.

For complex tasks, briefly outline the approach
before implementation. No mandatory plan files.

## Engineering Principles

- Follow existing project conventions.
- Prefer simple, explicit solutions.
- Reuse existing components and utilities.
- Avoid unnecessary abstractions.
- Do not introduce new dependencies without a good reason.
- Do not refactor unrelated code.
- Do not implement features outside the current scope.
- Keep changes focused and easy to review.
- Do not sacrifice correctness for speed.

## MVP Rules

- Implement only what the story requires.
- Prefer working solutions over theoretical flexibility.
- Avoid speculative features and premature optimization.
- Temporary solutions are acceptable when they are
  isolated, understandable, and safe.
- Do not introduce shortcuts that compromise security,
  data integrity, or critical business logic.
- Document significant technical compromises briefly.

## Architecture & ADR

Follow existing accepted ADRs.

Create a new ADR only when making a significant
architectural decision that affects future development.

Use a lightweight format:

- Context
- Decision
- Consequences

Do not create ADRs for minor implementation details.
New ADRs should remain proposed until approved.

## Testing

- Verify the story's acceptance criteria.
- Run relevant existing tests, lint, and type checks.
- Add tests for important business logic and regressions.
- Do not add unnecessary tests for trivial code.
- Never claim checks passed unless executed.

## Documentation

- Keep imported user stories unchanged.
- Update documentation when behavior or architecture changes.
- Avoid documentation that duplicates the code.
- Keep documentation concise and useful.

## Completion

After implementation, provide a short summary:

- What was implemented.
- What was verified.
- Any remaining issues or technical debt.

Do not mark incomplete work as complete.
