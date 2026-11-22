"""Публикация фото, Reels, Stories и каруселей через Instagram API."""

import time
from urllib.parse import quote

import config
from api import call


def _account_id(account_id: str) -> str:
    account_id = account_id or config.INSTAGRAM_ACCOUNT_ID
    if not account_id:
        raise RuntimeError("Для публикации укажите INSTAGRAM_ACCOUNT_ID или account_id.")
    return quote(account_id, safe="")


def _check_status(container_id: str, token: str) -> str:
    """Статус контейнера: IN_PROGRESS / FINISHED / ERROR / EXPIRED."""
    data = call(quote(container_id, safe=""), token, fields="status_code")
    status = data.get("status_code")
    if status in ("ERROR", "EXPIRED"):
        raise RuntimeError(f"Ошибка обработки контейнера: {status}.")
    return status


def create_container(token: str, caption: str = "", *, account_id: str = "", **media_kwargs) -> str:
    """Создаёт контейнер публикации. Возвращает creation_id."""
    payload = dict(media_kwargs)
    if caption:
        payload["caption"] = caption

    return call(f"{_account_id(account_id)}/media", token, method="POST", **payload)["id"]


def publish_container(container_id: str, token: str, *, account_id: str = "") -> str:
    """Публикует готовый контейнер. Возвращает id поста."""
    return call(
        f"{_account_id(account_id)}/media_publish",
        token,
        method="POST",
        creation_id=container_id,
    )["id"]


def _wait_ready(container_id: str, token: str, timeout: int = 300) -> None:
    """Ждёт обработки контейнера (нужно для видео/Reels)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _check_status(container_id, token) == "FINISHED":
            return
        time.sleep(10)
    raise TimeoutError(f"Контейнер {container_id} не обработался за {timeout} сек")


def post_photo(caption: str, image_url: str, token: str, *, account_id: str = "") -> str:
    """Фото в ленту (публичный URL, JPEG до 8 МБ)."""
    container_id = create_container(token, caption, account_id=account_id, image_url=image_url)
    return publish_container(container_id, token, account_id=account_id)


def post_reel(
    caption: str, video_url: str, token: str, wait_timeout: int = 600, *, account_id: str = ""
) -> str:
    """Reels: видео MP4/MOV до 1 ГБ, 3 сек – 15 мин.
    Обработка асинхронная — ждём FINISHED."""
    container_id = create_container(
        token,
        caption,
        account_id=account_id,
        media_type="REELS",
        video_url=video_url,
        share_to_feed="true",
    )
    _wait_ready(container_id, token, timeout=wait_timeout)
    return publish_container(container_id, token, account_id=account_id)


def post_story(
    image_url: str | None = None,
    video_url: str | None = None,
    token: str = "",
    *,
    account_id: str = "",
) -> str:
    """Сторис: ровно один параметр — image_url или video_url. Без caption."""
    if bool(image_url) == bool(video_url):
        raise ValueError("Укажите либо image_url, либо video_url (не оба)")

    kwargs = {"media_type": "STORIES"}
    if image_url:
        kwargs["image_url"] = image_url
    else:
        kwargs["video_url"] = video_url

    container_id = create_container(token, account_id=account_id, **kwargs)
    if video_url:
        _wait_ready(container_id, token)
    return publish_container(container_id, token, account_id=account_id)


def post_carousel(caption: str, media: list[dict], token: str, *, account_id: str = "") -> str:
    """Карусель из 2–20 элементов.

    media = [
        {"type": "IMAGE", "url": "https://..."},
        {"type": "VIDEO", "url": "https://..."},
        ...
    ]
    """
    if not 2 <= len(media) <= 20:
        raise ValueError("Карусель в Instagram: от 2 до 20 элементов")
    if any(item.get("type") not in ("IMAGE", "VIDEO") or not item.get("url") for item in media):
        raise ValueError("Для каждого элемента карусели нужны type (IMAGE/VIDEO) и url.")

    children = []
    for item in media:
        kwargs = {"is_carousel_item": "true"}
        if item["type"] == "IMAGE":
            kwargs["image_url"] = item["url"]
        else:
            kwargs["media_type"] = "VIDEO"
            kwargs["video_url"] = item["url"]

        child_id = create_container(token, account_id=account_id, **kwargs)
        if item["type"] == "VIDEO":
            _wait_ready(child_id, token)
        children.append(child_id)

    carousel_id = create_container(
        token,
        caption,
        account_id=account_id,
        media_type="CAROUSEL",
        children=",".join(children),
    )
    return publish_container(carousel_id, token, account_id=account_id)
