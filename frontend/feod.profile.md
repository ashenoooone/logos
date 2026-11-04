---
feod-profile: 1
---

# FEOD profile

> Overrides the defaults of the feod skill. To change it, run the skill's init flow again.

| Parameter | Value |
|-----------|-------|
| modification | base |
| multiapp | no |
| framework | react (spa) |
| srcRoot / alias | src / @ |
| layers | app, pages, modules, common, globals |
| pages | keep |
| modulePages | yes |
| fileBasedRouting | no (manual TanStack Router) |
| privatePageModules (`pages/_name/`) | allow |
| common.allowIndex | false |
| modules.allowDeepImports | false |
| singleFileModules | no |
| transitModules | none |
| uiKit | Mantine (external package); theme in app/config |
| layouts | app only |
| ioc | required for cross-module links |
| ddd | no |
| lint | eslint + @o-feod/eslint-structure-plugin (wired) |

## Project notes

- The FEOD root is `frontend/`; the Python backend lives outside this profile.
- Routes are declared manually in `src/app/router.tsx` (TanStack Router code-based routing).
- `src/app/test/` holds the shared Vitest setup and the app-level integration test.
- The structural `feod` section lives in `frontend/package.json`; do not add `feod.config.json`.
