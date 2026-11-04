# Account

Профиль менеджера (#4): имя, email, пароль.

## Публичный API

- `ProfilePanel` — экран `/profile`: `POST /account/name`, `POST /account/email` (письмо со ссылкой на новый адрес; до подтверждения вход по старому), `POST /account/password` (текущий пароль, политика 1.2, «Выйти на других устройствах» включено по умолчанию; текущая сессия сохраняется).
- `EmailConfirmationFlow` — экран `/email-confirmation`: токен из `#token=…`, `POST /account/email/confirm`; `410` — «Ссылка устарела».
