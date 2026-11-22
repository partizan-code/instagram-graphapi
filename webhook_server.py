"""Приём проверочных Instagram webhooks без отправки сообщений и хранения переписки."""

import asyncio
import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.requests import ClientDisconnect

from logging_config import UVICORN_LOG_CONFIG, configure_logging, logger

MAX_BODY_BYTES = 1024 * 1024
BODY_TIMEOUT = 10
HOST = "127.0.0.1"
PORT = 8000


def callback_url(tunnel_url: str) -> str:
    """Проверяет публичный HTTPS-адрес, не принимая секреты в URL."""
    value = tunnel_url.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Нужен HTTPS-адрес туннеля без параметров и данных входа.") from None
    if (
        len(value) > 2048
        or any(ord(char) <= 32 or ord(char) == 127 for char in value)
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/", "/webhook")
        or (port is not None and port == 0)
        or "\\" in parsed.netloc
    ):
        raise ValueError("Нужен HTTPS-адрес туннеля без параметров и данных входа.")
    return f"https://{parsed.netloc}/webhook"


def create_app(*, app_secret: str, verify_token: str) -> FastAPI:
    """Создаёт сервер; в тестах передаются только фиктивные секреты."""
    if not app_secret.strip() or not verify_token.strip():
        raise ValueError("Укажите APP_SECRET и WEBHOOK_VERIFY_TOKEN в локальном .env.")
    signing_key = app_secret.encode()
    verification_key = verify_token.encode()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.success("Webhook-сервер запущен на http://{}:{}; остановка — Ctrl+C.", HOST, PORT)
        yield
        logger.info("Webhook-сервер остановлен.")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Ошибка обработки входящего запроса; содержимое не журналируется.")
        return JSONResponse({"detail": "Ошибка обработки запроса."}, status_code=500)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/webhook")
    async def verify(request: Request) -> PlainTextResponse:
        query = request.query_params
        modes = query.getlist("hub.mode")
        tokens = query.getlist("hub.verify_token")
        challenges = query.getlist("hub.challenge")
        if (
            modes != ["subscribe"]
            or len(tokens) != 1
            or not hmac.compare_digest(tokens[0].encode(), verification_key)
            or len(challenges) != 1
            or not challenges[0].isascii()
            or not challenges[0].isdigit()
            or len(challenges[0]) > 128
        ):
            logger.warning("Отклонена проверка callback Meta.")
            return PlainTextResponse("Проверка отклонена.", status_code=403)
        logger.success("Meta подтвердила Callback URL.")
        return PlainTextResponse(challenges[0])

    @app.post("/webhook")
    async def receive(request: Request) -> PlainTextResponse:
        signatures = request.headers.getlist("x-hub-signature-256")
        if len(signatures) != 1:
            logger.warning("Webhook отклонён: отсутствует единственная подпись Meta.")
            return PlainTextResponse("Неверная подпись.", status_code=403)
        body = bytearray()
        try:
            async with asyncio.timeout(BODY_TIMEOUT):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > MAX_BODY_BYTES:
                        return PlainTextResponse("Слишком большой запрос.", status_code=413)
        except TimeoutError:
            return PlainTextResponse("Истекло время приёма запроса.", status_code=408)
        except ClientDisconnect:
            return PlainTextResponse("Соединение прервано.", status_code=400)
        expected = "sha256=" + hmac.new(signing_key, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signatures[0].encode(), expected.encode()):
            logger.warning("Webhook отклонён: подпись Meta не совпадает.")
            return PlainTextResponse("Неверная подпись.", status_code=403)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError, RecursionError):
            return PlainTextResponse("Некорректный JSON.", status_code=400)
        if not isinstance(payload, dict) or payload.get("object") != "instagram":
            return PlainTextResponse("Ожидалось событие Instagram.", status_code=400)
        entries = payload.get("entry")
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            return PlainTextResponse("Некорректный список событий.", status_code=400)
        messages = changes = 0
        for entry in entries:
            messaging = entry.get("messaging", [])
            changed = entry.get("changes", [])
            if any(
                not isinstance(items, list) or any(not isinstance(item, dict) for item in items)
                for items in (messaging, changed)
            ):
                return PlainTextResponse("Некорректный формат событий.", status_code=400)
            messages += sum("message" in event for event in messaging)
            changes += len(changed)
        logger.info(
            "Получен подписанный webhook Instagram: записей {}; сообщений {}; изменений {}.",
            len(entries),
            messages,
            changes,
        )
        return PlainTextResponse("EVENT_RECEIVED")

    return app


def main() -> int:
    """Запуск без аргументов: запрос адреса туннеля и приём событий."""
    import config

    configure_logging()
    try:
        app = create_app(app_secret=config.APP_SECRET, verify_token=config.WEBHOOK_VERIFY_TOKEN)
    except ValueError:
        logger.error("Укажите APP_SECRET и WEBHOOK_VERIFY_TOKEN в локальном .env.")
        return 1
    logger.info("Запустите tuna http 8000 --inspect=false в отдельном терминале.")
    try:
        while True:
            try:
                url = callback_url(input("Вставьте публичный HTTPS-адрес туннеля tuna: "))
                break
            except ValueError:
                logger.warning("Нужен HTTPS-адрес туннеля без параметров и данных входа.")
    except (EOFError, KeyboardInterrupt):
        logger.info("Запуск отменён.")
        return 1
    logger.info("Callback URL для Meta: {}", url)
    logger.info("Verify token возьмите из WEBHOOK_VERIFY_TOKEN в локальном .env.")
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_config=UVICORN_LOG_CONFIG,
            access_log=False,
            proxy_headers=False,
            limit_concurrency=32,
            timeout_keep_alive=5,
            timeout_graceful_shutdown=5,
        )
    )
    try:
        server.run()
    except KeyboardInterrupt:
        return 0
    except (OSError, SystemExit):
        logger.error("Не удалось запустить сервер. Проверьте, что порт 8000 свободен.")
        return 1
    return 0 if server.started else 1


if __name__ == "__main__":
    raise SystemExit(main())
