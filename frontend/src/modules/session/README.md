# Session

Текущий субъект (администратор или менеджер) по HttpOnly-cookie сессии: `GET /auth/me`, вход, выход.

## Публичный API

- `SessionProvider` — загружает субъекта до рендера приложения; ошибка связи — экран с повтором.
- `useSession()` — `{ subject, setSubject }`; `setSubject` вызывать после любого ответа с новым `subject` и после выхода.
- `RequireSession` — guard маршрута: `anonymous` / `authenticated` / `administrator`.
- `SessionHeader` — шапка: кто вошёл, «Выйти», ссылка «Сотрудники» для администратора.
- `LoginForm` — вход менеджера (`kind="manager"`, email) или администратора (`kind="administrator"`, CLI-логин).

Пользователь не хранится в localStorage: источник истины — только `/auth/me` и ответы входа.
