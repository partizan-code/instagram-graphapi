# Проверка Instagram webhooks через tuna

Отдельный диагностический сервер `webhook_server.py` принимает события FastAPI через
Uvicorn. Он не обращается к Graph API, не отправляет ответы в Direct и не хранит
переписку. `main.py` и `mise run start` по-прежнему читают диалоги.

## Запуск

1. Установите зависимости существующей задачей `mise run setup`.
2. В локальном `.env` задайте `APP_SECRET` именно Meta-приложения и
   `WEBHOOK_VERIFY_TOKEN` — свою случайную строку. Это отдельный проверочный секрет,
   не `META_ACCESS_TOKEN`, не `APP_SECRET` и не ключ tuna. Не отправляйте секреты в чат.
3. В первом терминале запустите туннель:

   ```console
   mise run tunnel
   ```

   Задача выполняет `tuna http 8000 --inspect=false`. При необходимости заранее
   авторизуйте установленный клиент tuna. Инспекция HTTP отключена, чтобы запросы
   с перепиской и проверочным токеном не отображались в инспекторе tuna.
4. Во втором терминале запустите сервер:

   ```console
   mise run webhook
   ```

5. На запрос `Вставьте публичный HTTPS-адрес туннеля tuna:` вставьте адрес из первого
   терминала, например `https://example.ru.tuna.am`. Сервер выведет готовый
   `https://example.ru.tuna.am/webhook`. Неверный адрес можно ввести повторно.

Сервер слушает только `127.0.0.1:8000`; наружу доступен через туннель.
`GET /health` отвечает `{"status":"ok"}`. Остановка — Ctrl+C в обоих терминалах.
При изменении динамического адреса обновите Callback URL в Meta.

## Настройка Meta

Для используемого проектом **Unified Login**:

1. Откройте **Use cases → Manage messaging & content on Instagram → Customize →
   API setup with Unified login → Configure webhooks**.
2. Укажите выведенный Callback URL и значение `WEBHOOK_VERIFY_TOKEN` из `.env`
   в поле **Verify token**, затем **Verify and save**. Не используйте OAuth
   `REDIRECT_URI`: callback входа и webhook выполняют разные задачи.
3. После проверки появится запись `Meta подтвердила Callback URL.`.
4. Подпишитесь на поле `messages` и нажмите **Test**. При принятом подписанном
   событии сервер выведет `Получен подписанный webhook Instagram` и счётчики.
   Если подпись отклонена, проверьте, что `APP_SECRET` принадлежит этому приложению.
5. Для реальных событий также нужна подписка самого Instagram-аккаунта на приложение:
   `POST /{INSTAGRAM_ACCOUNT_ID}/subscribed_apps` с `subscribed_fields=messages`
   через `graph.facebook.com`, бизнес-токеном этого подключения и разрешением
   `instagram_manage_messages`. Сервер не выполняет эту операцию автоматически.
6. Отправьте тестовое сообщение подключённому аккаунту из Instagram. Отсутствие
   события при успешном Dashboard Test нужно разбирать отдельно: режим/публикация
   приложения, разрешения, подписка аккаунта и **Allow access to messages**.

Dashboard Test подтверждает доставку проверочного события, но не подтверждает
работу с реальными покупателями. В текущей документации Meta для уведомлений
пользователей требуется опубликованное приложение / Live; для production access —
Business Verification. Development-проверка не заменяет App Review.

## Обработка запросов

- `GET /webhook`: проверка `hub.mode`, `hub.verify_token`, возврат числового
  `hub.challenge` обычным текстом.
- `POST /webhook`: HMAC-SHA256 по исходному телу с `APP_SECRET`, сравнение
  `X-Hub-Signature-256`, проверка JSON и объекта `instagram`, быстрый ответ 200.
- При отсутствии/ошибке подписи — 403, неверном JSON/структуре — 400,
  теле больше 1 МиБ — 413, превышении 10 секунд чтения тела — 408.
- В Loguru попадают только результат проверки и количества записей/сообщений/
  изменений. Тексты, ID, заголовки, параметры запросов и сырые ошибки не выводятся.
  HTTP access/error-журналы Uvicorn отключены централизованно. Swagger отключён.
- Это приёмник для диагностики: повторы Meta могут увеличить счётчики; дедупликации,
  очереди и автоматических ответов нет.

## Проверки

`mise run check` запускает Ruff и изолированные pytest. Webhook-тесты используют
httpx ASGITransport с фиктивными ключами, без HTTP-сервера, загрузки настоящего
`.env`, Graph API или tuna. На Windows служебная пара сокетов цикла событий
создаётся до включения общего запрета подключений; запрет действует во всех тестах.

Источники: [Meta Webhooks](https://developers.facebook.com/documentation/instagram-platform/webhooks/setup),
[Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/get-started),
[tuna HTTP](https://tuna.am/docs/tunnels/http/).
