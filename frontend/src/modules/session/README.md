# Session

Текущий субъект (администратор или менеджер) по HttpOnly-cookie сессии: `GET /auth/me`, вход, выход.

## Публичный API

- `SessionProvider` — загружает субъекта до рендера приложения; ошибка связи — экран с повтором.
- `useSession()` — `{ subject, setSubject }`; `setSubject` вызывать после любого ответа с новым `subject` и после выхода.
- `RequireSession` — guard маршрута: `anonymous` / `authenticated` / `administrator`.
- `SessionHeader` — шапка: кто вошёл, «Выйти», ссылка «Сотрудники» для администратора.
- `LoginForm` — менеджер получает шестизначный код через `POST /auth/manager/otp/request` (нейтральный ответ, повтор через 60 с) и подтверждает его через `/auth/manager/otp/verify`; администратор входит по CLI-логину и паролю.

Пользователь не хранится в localStorage: источник истины — только `/auth/me` и ответы входа.
