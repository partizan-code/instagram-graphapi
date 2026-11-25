# Публикация медиа из Python

`publisher.py` создаёт медиаконтейнеры через `/{account_id}/media` и публикует
их через `/{account_id}/media_publish`. Все HTTP-вызовы проходят через `api.py`.
`main.py` публикации не вызывает. Функции ниже выполняют реальные операции
при вызове; примеры не являются тестами.

## Подготовка

- Тот же `META_ACCESS_TOKEN` Unified Login с доступом к Instagram-аккаунту и
  разрешениями `instagram_basic` и `instagram_content_publish`.
- `INSTAGRAM_ACCOUNT_ID` в настройках либо именованный аргумент `account_id`.
  Это Instagram ID, а не `/me`, который обозначает системного пользователя.
- Медиа на публично доступных URL: файлы получает Meta, локальные пути не подходят.

Общая версия API берётся из `META_API_VERSION`. Доступность форматов зависит от
аккаунта и требований Meta; актуальные требования и квоты см. в
[Content Publishing](https://developers.facebook.com/documentation/instagram-platform/content-publishing).
Код не проверяет все ограничения форматов и не запрашивает квоту публикаций.

## Сигнатуры API

| Функция | Результат и поведение |
| --- | --- |
| `post_photo(caption: str, image_url: str, token: str, *, account_id: str = "") -> str` | Фото в ленте; возвращает ID публикации |
| `post_reel(caption: str, video_url: str, token: str, wait_timeout: int = 600, *, account_id: str = "") -> str` | Reels с `share_to_feed=true`; ожидает готовности контейнера |
| `post_story(image_url: str \| None = None, video_url: str \| None = None, token: str = "", *, account_id: str = "") -> str` | Ровно один из `image_url` и `video_url`, без caption; возвращает ID публикации |
| `post_carousel(caption: str, media: list[dict], token: str, *, account_id: str = "") -> str` | Карусель из 2–20 элементов с `type` IMAGE/VIDEO и непустым `url`; возвращает ID публикации |
| `create_container(token: str, caption: str = "", *, account_id: str = "", **media_kwargs) -> str` | Создание контейнера; возвращает creation ID |
| `publish_container(container_id: str, token: str, *, account_id: str = "") -> str` | Публикация готового контейнера; возвращает ID публикации |

У всех функций явный `account_id` имеет приоритет над настройкой. При отсутствии
обоих значений запрос создания публикации не выполняется.

## Примеры

Выполняйте в окружении проекта. Замените URL образцов на собственные публичные
медиа; каждый вызов ниже создаёт отдельную публикацию.

```python
import os

import publisher

token = os.environ["META_ACCESS_TOKEN"]
photo_id = publisher.post_photo(
    "Фото в ленте", "https://media.example.com/photo.jpg", token
)
reel_id = publisher.post_reel(
    "Короткое видео", "https://media.example.com/reel.mp4", token, wait_timeout=600
)
story_id = publisher.post_story(
    image_url="https://media.example.com/story.jpg", token=token
)
carousel_id = publisher.post_carousel(
    "Подборка",
    [
        {"type": "IMAGE", "url": "https://media.example.com/photo.jpg"},
        {"type": "VIDEO", "url": "https://media.example.com/video.mp4"},
    ],
    token,
)
```

Импорт `publisher` загружает `config.py` и локальный `.env`.
При обработке исключений не выводите токен, сырые HTTP-ответы и настройки.
Для журналирования используйте общий logger из `logging_config.py`.

## Обработка контейнеров

Для Reels, видео Stories и видеоэлементов карусели опрашивается `status_code`
контейнера с интервалом 10 секунд. `FINISHED` разрешает публикацию; `ERROR` и
`EXPIRED` приводят к `RuntimeError`. При истечении времени ожидания возникает
`TimeoutError`: по умолчанию 600 секунд для Reels и 300 для остальных видео.
Это предел цикла ожидания, а не строгий срок всей операции: HTTP-вызовы имеют
свои тайм-ауты. У фото и родительского контейнера карусели отдельного ожидания нет.

Карусель последовательно создаёт дочерние контейнеры, затем родительский
`CAROUSEL` с их ID. Автоматических повторов, отката или удаления уже созданных
контейнеров при ошибке нет.

## Проверки

Тесты проверяют параметры всех типов медиа, явный выбор аккаунта, Bearer-заголовок,
общую версию API, закрытие ответов, ошибки контейнера и предел ожидания.
Используются HTTP-моки и фиктивные URL; реальные публикации не выполнялись в
зафиксированных проверках. См. [DEVELOPMENT.md](DEVELOPMENT.md#изоляция-проверок) и
[состояние проекта](../PROJECT_STATUS.md).

[Оглавление документации](README.md) · [Обзор проекта](../README.md)
