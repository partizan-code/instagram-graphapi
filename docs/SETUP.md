# Настройка окружения и Meta

## Локальное окружение

Установите [mise](https://mise.jdx.dev/getting-started.html), клонируйте репозиторий
и выполняйте команды из его корня:

```console
mise trust
mise install
mise run setup
```

`mise.toml` закрепляет Python 3.13.18 и uv 0.8.18. Задача `setup` выполняет
`uv sync --locked`; окружение хранится вне проекта, согласно
`UV_PROJECT_ENVIRONMENT`. Подробнее об инструментах — в [DEVELOPMENT.md](DEVELOPMENT.md).

Создайте `.env` в корне по [.env.example](../.env.example). `config.py` загружает
этот файл, не заменяя уже заданные переменные окружения. Не добавляйте `.env`
и полученные токены в Git.

## Подготовка Meta

Для интеграции используется Instagram API with Unified Login на
`graph.facebook.com`. Нужны Meta-приложение с Facebook Login for Business и
сценарием **Manage messaging & content on Instagram**, business portfolio и
Instagram professional account. В конфигурации Meta выбираются разрешения и
доступные ресурсы; её идентификатор передаётся как `META_CONFIG_ID`.
Пошаговые требования — в [официальном руководстве Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/get-started).

Токен Unified Login — Business Integration System User Access Token
(в Dashboard: System-user access token). С ним `/me` обозначает системного
пользователя, а не Instagram-аккаунт. ID аккаунта получается через
`/me/assigned_instagram_accounts`; публикации адресуются этому ID, а не `/me`.
См. [аутентификацию Meta](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/authentication).

## Переменные окружения

| Переменная | Когда нужна | Значение |
| --- | --- | --- |
| `META_ACCESS_TOKEN` | Чтение Direct и публикации | Бизнес-токен Unified Login с доступом к назначенному аккаунту |
| `META_API_VERSION` | Запросы Graph API и URL входа | Общая версия API, по умолчанию `v27.0` |
| `INSTAGRAM_ACCOUNT_ID` | Явный выбор аккаунта; публикации без `account_id` | ID Instagram-аккаунта, не системного пользователя |
| `APP_ID` | Получение и выпуск нового токена | ID Meta-приложения |
| `APP_SECRET` | Получение/выпуск токена и webhook | Секрет того же Meta-приложения |
| `META_CONFIG_ID` | Вход через браузер | Configuration ID Facebook Login for Business |
| `REDIRECT_URI` | Получение токена | HTTPS URL из конфигурации Meta, по умолчанию `https://localhost/` |
| `WEBHOOK_VERIFY_TOKEN` | Webhook-сервер | Отдельная случайная строка для проверки callback, не access token |

Реквизиты прежнего Instagram OAuth и `INSTAGRAM_TOKEN` не используются.
Разрешения задаются в Meta-конфигурации, а не списком scopes в коде.

### Чтение Direct

Минимальные настройки:

```dotenv
META_ACCESS_TOKEN=<бизнес-токен Unified Login>
META_API_VERSION=v27.0
INSTAGRAM_ACCOUNT_ID=<ID Instagram-аккаунта>
```

Токену нужны доступ к аккаунту и разрешения для чтения сообщений, включая
`instagram_basic` и `instagram_manage_messages`. При единственном назначенном
аккаунте без признаков продолжения `INSTAGRAM_ACCOUNT_ID` можно оставить пустым.
При нескольких аккаунтах или неполной странице назначений нужен явный ID;
он должен присутствовать в полученной странице аккаунтов.

```console
mise run start
```

Команда обращается к реальному аккаунту и выводит доступную переписку в консоль.
Подробности запросов, вывода и кодов завершения — в [DIRECT.md](DIRECT.md).

### Получение и выпуск токенов

Для получения задайте `APP_ID`, `APP_SECRET`, `META_CONFIG_ID` и `REDIRECT_URI`.
Для `refresh()` нужны `APP_ID`, `APP_SECRET`, текущий бизнес-токен с
`business_management` и доступ к бизнесу. `REDIRECT_URI` должен совпадать с
настройками Meta; callback webhooks — отдельный адрес.
Вызовы Python API — в [AUTHENTICATION.md](AUTHENTICATION.md).

### Публикации и webhooks

Публикациям нужны `instagram_basic`, `instagram_content_publish`, доступ к
аккаунту и публичные URL медиа. См. [PUBLISHING.md](PUBLISHING.md).

Webhook-серверу нужны `APP_SECRET` и `WEBHOOK_VERIFY_TOKEN`. Клиент tuna
устанавливается и при необходимости авторизуется отдельно; `mise run setup`
его не устанавливает. Туннель, callback и подписки — в [WEBHOOKS.md](WEBHOOKS.md).

## Проверка настройки

`mise run check` проверяет код изолированно и не подтверждает права или срок
действия реального токена. Доступность операций зависит от режима приложения,
конфигурации и разрешений Meta. Зафиксированные результаты реальных и локальных
проверок — в [состоянии проекта](../PROJECT_STATUS.md).

[Оглавление документации](README.md) · [Обзор проекта](../README.md)
