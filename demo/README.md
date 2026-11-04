# LOGOS · Sprint Review 01 (Slidev)

```sh
cd demo
pnpm install
pnpm dev      # http://localhost:3030, презентер-режим с заметками: /presenter
pnpm build    # статическая сборка в dist/
```

Экспорт в PDF/PNG (`pnpm export`) требует Chromium для Playwright: `pnpm exec playwright install chromium`.

- `slides.md` — слайды и заметки докладчика (`<!-- ... -->` в конце слайда, `[клик]` — где листать).
- `style.css` — цвета и формы из `frontend/src/app/config/theme.ts` и `global.css`.
- `components/Story.vue` — слайд пользовательской истории.
- `public/mockups/` — макеты из YouGile из исходной презентации.
