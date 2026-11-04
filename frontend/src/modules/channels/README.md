# Channels

Раздел администратора «Каналы» (#5): `GET /admin/channels`, `POST /admin/channels/telegram/check`, `POST /admin/channels/telegram`, `POST /admin/channels/telegram/disconnect`.

## Публичный API

- `ChannelsPanel` — карточка Telegram-бота (подключён / ошибка / не подключён), форма подключения по токену с проверкой, переподключение, отключение. Статус опрашивается раз в 10 с.

Токен API не возвращает; в форме поле скрыто. Доступ проверяет guard маршрута; `401` сбрасывает сессию.
