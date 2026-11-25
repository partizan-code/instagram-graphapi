# Авторизация и управление токеном

`auth.py` реализует Meta Unified Login на основе Facebook Login for Business.
HTTP-операции идут через `api.py` на `graph.facebook.com` с общей
`META_API_VERSION`. Обычный запуск `main.py` не вызывает эти функции.
Реквизиты и настройки — в [SETUP.md](SETUP.md).

## Получение токена

```python
import auth
from logging_config import configure_logging

configure_logging()
token = auth.obtain_token()
```

`obtain_token() -> str` выполняет следующие шаги:

1. Проверяет наличие `APP_ID` и `APP_SECRET`.
2. Вызывает `get_auth_code() -> str`: формирует вход с `META_CONFIG_ID`,
   случайным `state` и `REDIRECT_URI`, открывает браузер и запрашивает полный
   URL редиректа в консоли.
3. Проверяет HTTPS-настройку redirect URI, совпадение схемы, адреса, пути и
   настроенных query-параметров, единственный правильный `state`, отсутствие
   ошибки и единственный непустой `code`.
4. Вызывает `exchange_code(code: str) -> dict`: обменивает код через
   `/oauth/access_token` с реквизитами Meta-приложения и проверяет `access_token`.
5. Вызывает `save_token(token: str) -> None`: записывает `META_ACCESS_TOKEN`
   в локальный `.env` и окружение текущего процесса.

Локальный HTTP-сервер для OAuth-редиректа не запускается: URL переносится
пользователем из браузера. Он содержит код входа; не публикуйте его и не
добавляйте в логи. `REDIRECT_URI` должен совпадать с конфигурацией Meta.

Unified Login возвращает Business Integration System User Access Token.
Отдельного обмена через `to_long_lived()` нет; срок токена зависит от
конфигурации. Токен не выводится в журнал.
Описание типа и срока токена — в [документации Meta](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/authentication).

## Явный выпуск нового бизнес-токена

```python
import os

import auth
from logging_config import configure_logging

configure_logging()
new_token = auth.refresh(os.environ["META_ACCESS_TOKEN"])["access_token"]
auth.save_token(new_token)
```

`refresh(token: str) -> dict`:

- Запрашивает `/me?fields=client_business_id` и получает ID бизнеса и системного
  пользователя. Не подставляет вместо бизнеса Instagram ID или system-user ID.
- Вычисляет `appsecret_proof` как HMAC-SHA256 токена с `APP_SECRET`.
- Отправляет POST к `/{client_business_id}/system_user_access_tokens` с proof,
  `system_user_id` и `set_token_expires_in_60_days=true`.
- Проверяет наличие нового `access_token` и возвращает ответ Meta.

Нужны `APP_ID`, `APP_SECRET` и разрешение `business_management` у текущего токена.
Код запрашивает токен на 60 дней; фактический результат определяет Meta.
Сохранение нового токена и отзыв старого не выполняются автоматически.
Автоматического обновления по расписанию или проверки срока действия нет.
Справочник: [Business Integration System User Access Token Management API](https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business#bisu-token-api).

## Проверки и ограничения

Вход проверяется с подменой браузера и ввода URL; HTTP-обмен и выпуск токена —
на моках, сохранение — во временном `.env`. Ошибки `state`, чужой адрес,
повторяющийся или отсутствующий код отклоняются до обмена. Вызовы реального
входа и выпуска токена не подтверждены этими тестами.

Ранее использовавшиеся Instagram OAuth, `INSTAGRAM_TOKEN`, scopes и grant types
не относятся к текущему потоку. Контекст перехода — в
[состоянии проекта](../PROJECT_STATUS.md), справочник —
[миграция Meta на Unified Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/migration-guide/).

[Оглавление документации](README.md) · [Обзор проекта](../README.md)
