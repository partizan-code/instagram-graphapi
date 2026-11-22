# Чтение Direct

Логика чтения находится в `main.py`:

- `_get()` — общий запрос из `api.py`: GET к `graph.facebook.com` и безопасная диагностика.
- `get_account()` — назначенный токену Instagram-аккаунт, с проверкой явного выбора.
- `show_inbox()` — одна страница диалогов со вложенными последними сообщениями.
- `main()` — настройка Loguru, Bearer-токен и закрываемая HTTP-сессия.

Запрос полей: `id,messages.limit(20){id,message,from,created_time}`.
Выводятся ID диалога/сообщения, отправитель, время и текст. Отсутствующий текст
обозначает вложение или служебное сообщение. Управляющие символы терминала экранируются.
Время выводится как получено от API. Число записей не обрезается по значению limit.

Автоматического обхода страниц, повторов, хранения, отправки и вебхуков нет.
При наличии paging.next приложение предупреждает о неполной выборке, не выводя URL.
Успешное чтение страницы возвращает код 0, ошибка — код 1.

Настройки и запуск: [README](../README.md).
Справочники Meta: [Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/get-started),
[Conversations](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/conversations-api).
