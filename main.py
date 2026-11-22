"""Чтение последних сообщений Instagram Direct через Meta Unified Login."""

import os
from urllib.parse import quote

import requests

from api import request as _get
from logging_config import configure_logging, logger


def _display(value: object) -> str:
    return "".join(
        char if ord(char) >= 32 and not 127 <= ord(char) < 160 else repr(char)[1:-1]
        for char in str(value)
    )


def _records(payload: dict) -> list[dict]:
    records = payload.get("data")
    if not isinstance(records, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in records
    ):
        raise RuntimeError("Meta вернула некорректный список объектов.")
    return records


def get_account(session: requests.Session, account_id: str = "") -> dict:
    payload = _get(session, "me/assigned_instagram_accounts", fields="id,username")
    accounts = _records(payload)
    if account_id:
        matches = [account for account in accounts if account["id"] == account_id]
        if not matches:
            raise RuntimeError(
                "Указанный INSTAGRAM_ACCOUNT_ID не найден на странице назначенных аккаунтов."
            )
        return matches[0]
    if len(accounts) != 1 or payload.get("paging", {}).get("next"):
        raise RuntimeError("Укажите INSTAGRAM_ACCOUNT_ID из списка назначенных аккаунтов.")
    return accounts[0]


def show_inbox(session: requests.Session, account_id: str) -> None:
    from config import DIALOG_LIMIT, HISTORY_LIMIT

    payload = _get(
        session,
        f"{quote(account_id, safe='')}/conversations",
        platform="instagram",
        fields=f"id,messages.limit({HISTORY_LIMIT}){{id,message,from,created_time}}",
        limit=DIALOG_LIMIT,
    )
    conversations = _records(payload)
    if not conversations:
        logger.info("На полученной странице доступных диалогов нет.")
    for conversation in conversations:
        logger.info("Диалог: {}", _display(conversation["id"]))
        history = conversation.get("messages", {})
        for message in reversed(_records(history)):
            sender = message.get("from") or {}
            logger.info(
                "[{}] @{} (ID: {}), сообщение {}: {}",
                _display(message.get("created_time", "время неизвестно")),
                _display(sender.get("username", "неизвестно")),
                _display(sender.get("id", "неизвестно")),
                _display(message["id"]),
                _display(message.get("message") or "[Вложение или сообщение без текста]"),
            )
        if history.get("paging", {}).get("next"):
            logger.warning("У диалога есть другие сообщения; показана только полученная страница.")
    if payload.get("paging", {}).get("next"):
        logger.warning("Есть другие страницы диалогов; показана только полученная страница.")


def main() -> int:
    configure_logging()
    try:
        from config import INSTAGRAM_ACCOUNT_ID

        token = os.environ.get("META_ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Укажите META_ACCESS_TOKEN в .env или окружении.")
        with requests.Session() as session:
            session.headers["Authorization"] = f"Bearer {token}"
            account = get_account(session, INSTAGRAM_ACCOUNT_ID)
            logger.success(
                "Instagram-аккаунт: @{} (ID: {}).",
                _display(account.get("username", "неизвестно")),
                _display(account["id"]),
            )
            show_inbox(session, account["id"])
        return 0
    except (RuntimeError, OSError) as error:
        logger.error(
            "{}",
            str(error)
            if isinstance(error, RuntimeError)
            else "Не удалось прочитать настройки .env.",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
