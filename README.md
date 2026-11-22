# Instagram Direct

Небольшой Python-сценарий для чтения последних сообщений через Meta Unified Login.

## Запуск

В локальном `.env`:

```dotenv
META_ACCESS_TOKEN=<System User Token>
META_API_VERSION=v27.0
INSTAGRAM_ACCOUNT_ID=<ID Instagram-аккаунта>
```

При единственном назначенном аккаунте `INSTAGRAM_ACCOUNT_ID` можно не задавать.
Если аккаунтов несколько или список неполный, нужен явный ID.
Переменные терминала имеют приоритет над `.env`.

```console
mise run start
```

`main.py` без аргументов делает два GET-запроса:

1. `/me/assigned_instagram_accounts` — проверяет токен и выбирает аккаунт.
2. `/{account_id}/conversations` — получает диалоги со вложенными сообщениями.

Размер страницы — пять диалогов, запрашивается по 20 сообщений; значения заданы
в `config.py`. Обрабатывается весь фактически возвращённый массив. При наличии
продолжения выводится предупреждение. Автоматического обхода страниц и повторов нет.
Код 0 означает успешное чтение страницы; код 1 — ошибку настроек или API.
Полная история не обещается. Время показывается в формате API с часовым поясом.

HTTP использует существующий `requests`: Bearer-заголовок, тайм-аут 30 секунд,
закрытие ответов/сессии, без редиректов. Loguru выводит сообщения только в консоль.
Сырые HTTP-ошибки, токены и URL из ответов не логируются.

Отправка сообщений, вебхуки, БД и сохранение переписки отсутствуют.
`auth.py` и `publisher.py` также используют Unified Login; обычный запуск их не вызывает.
Старые `INSTAGRAM_TOKEN`, Instagram OAuth и grant types больше не используются.

## Авторизация и публикации из Python

Для получения токена через `auth.obtain_token()` добавьте в локальный `.env`:

```dotenv
APP_ID=<Meta App ID>
APP_SECRET=<Meta App Secret>
META_CONFIG_ID=<Configuration ID для Unified Login>
REDIRECT_URI=https://localhost/
```

Это реквизиты **Meta-приложения**. `REDIRECT_URI` должен точно совпадать с адресом
в конфигурации Meta. Разрешения задаются в конфигурации, а не списком scopes в коде.
Функция открывает браузер, запрашивает URL редиректа, проверяет `state` и адрес,
обменивает код через `graph.facebook.com` и сохраняет `META_ACCESS_TOKEN`.
Отдельный обмен на долгоживущий Instagram-токен `to_long_lived()` удалён:
Unified Login сразу возвращает бизнес-токен; его срок зависит от конфигурации.

`auth.refresh(token)` получает бизнес и системного пользователя через `/me`,
затем запрашивает новый токен на 60 дней через `/{client_business_id}/system_user_access_tokens`.
Нужны `APP_SECRET` и разрешение `business_management` у текущего токена.
Функция возвращает ответ Meta, не сохраняет токен и не отзывает старый автоматически:

```python
new_token = auth.refresh(token)["access_token"]
auth.save_token(new_token)
```

Публикации: `publisher.post_photo()`, `post_reel()`, `post_story()` и `post_carousel()`.
Все принимают `token` — тот же `META_ACCESS_TOKEN`, и необязательный именованный
`account_id`; без него используется `INSTAGRAM_ACCOUNT_ID` из настроек.
Применяется общая `META_API_VERSION`; `/me/media` не используется.
Токену нужны `instagram_basic` и `instagram_content_publish` и доступ к аккаунту.
Медиа передаются публичными URL. Обработка видео ожидается с ограничением времени.
Карусель — от 2 до 20 элементов IMAGE/VIDEO.

Справочники Meta: [миграция на Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/migration-guide/),
[токены](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/authentication),
[обновление бизнес-токена](https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business#bisu-token-api),
[публикация](https://developers.facebook.com/documentation/instagram-platform/content-publishing).
Получение/обновление токенов и публикации проверены только на HTTP-моках.

## Разработка

Python и uv закреплены в `mise.toml`. Зависимости — в `pyproject.toml` и `uv.lock`.

```console
mise run setup
mise run check
```

Тесты используют фиктивные данные, блокируют сеть и загрузку настоящего `.env`.
Запуск приложения обращается к реальному аккаунту и не является тестом.

[Direct](docs/DIRECT.md) · [Архитектура](docs/ARCHITECTURE.md) ·
[Разработка](docs/DEVELOPMENT.md) · [Состояние](PROJECT_STATUS.md) · [Правила](AGENTS.md).
