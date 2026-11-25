# Чтение Direct

Логика чтения находится в `main.py`:

- `_get()` — общий запрос из `api.py`: GET к `graph.facebook.com` и безопасная диагностика.
- `get_account()` — назначенный токену Instagram-аккаунт, с проверкой явного выбора.
- `show_inbox()` — одна страница диалогов со вложенными последними сообщениями.
- `main()` — настройка Loguru, Bearer-токен и закрываемая HTTP-сессия.

При успешном запуске выполняются два GET-запроса:

1. `/me/assigned_instagram_accounts` с полями `id,username` — проверка доступа
   и выбор назначенного Instagram-аккаунта.
2. `/{account_id}/conversations` с `platform=instagram` — одна страница диалогов
   со вложенными сообщениями.

`get_account(session, account_id="") -> dict` возвращает аккаунт из полученной
страницы. Без явного ID допустим ровно один аккаунт и отсутствие `paging.next`;
с явным ID он должен быть найден на этой странице.
`show_inbox(session, account_id) -> None` выводит полученную историю,
не возвращая коллекцию сообщений.

Размер страницы — пять диалогов, запрашивается по 20 сообщений; значения заданы
в `config.py` как `DIALOG_LIMIT` и `HISTORY_LIMIT`.
Запрос полей: `id,messages.limit(20){id,message,from,created_time}`.
Выводятся ID диалога/сообщения, отправитель, время и текст. Отсутствующий текст
обозначает вложение или служебное сообщение. Управляющие символы терминала экранируются.
Время выводится как получено от API. Число записей не обрезается по значению limit.

В сценарии чтения нет автоматического обхода страниц, повторов, хранения или
отправки сообщений. Webhook-сервер — [отдельный компонент](WEBHOOKS.md).
При наличии paging.next приложение предупреждает о неполной выборке, не выводя URL.
Успешное чтение страницы возвращает код 0, ошибка — код 1.

Настройки и запуск: [SETUP.md](SETUP.md#чтение-direct).
Справочники Meta: [Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/get-started),
[Миграция запросов Direct на Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/migration-guide/).

[Оглавление документации](README.md) · [Обзор проекта](../README.md)
