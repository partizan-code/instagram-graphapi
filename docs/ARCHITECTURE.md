# Архитектура

Плоская структура, без CLI, классов клиента, моделей и БД.

| Файл | Назначение |
| --- | --- |
| `main.py` | Чтение аккаунта и последней страницы Direct через Meta Unified Login |
| `config.py` | Загрузка .env, параметры API и размеры страниц |
| `api.py` | Общие GET/POST к graph.facebook.com, Bearer, тайм-аут, безопасные ошибки |
| `logging_config.py` | Общий Loguru logger, только консоль |
| `auth.py` | Unified Login: вход с config_id/state, обмен кода, сохранение и обновление токена |
| `publisher.py` | Отдельные функции публикации фото/Reels/Stories/каруселей |
| `webhook_server.py` | Отдельный FastAPI/Uvicorn-приёмник с проверкой подписи Meta |
| `tests/` | Изолированные проверки с HTTP-моками и заблокированной сетью |

Чтение: META_ACCESS_TOKEN → graph.facebook.com → assigned_instagram_accounts →
Instagram account ID → conversations со вложенными messages.
Обычный запуск не вызывает авторизацию, продление токена или публикацию.
Авторизация открывает facebook.com, HTTP-операции используют graph.facebook.com.
Публикации адресуются Instagram account ID; `/me` обозначает системного пользователя.
Секреты, сырые исключения HTTP и URL пагинации в журнал не передаются.

Webhooks: tuna HTTPS → `127.0.0.1:8000/webhook` → проверка challenge либо
HMAC-SHA256 → счётчики событий в общем Loguru logger. Сервер запускается задачей
`webhook` без аргументов и запрашивает адрес туннеля через `input()`; задача
`tunnel` запускает tuna с отключённой инспекцией. HTTP-журналы Uvicorn отключены
через общую конфигурацию логирования. Отправки и хранения переписки нет.
[Настройка Meta](WEBHOOKS.md).

[Подробности Direct](DIRECT.md). [Текущее состояние и ограничения](../PROJECT_STATUS.md).
