import asyncio
import hashlib
import hmac
import json
from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

import webhook_server
from logging_config import configure_logging

SECRET = "fake-app-secret"
VERIFY_TOKEN = "fake-verify-token"


@pytest.fixture
def client(isolated_session):
    app = webhook_server.create_app(app_secret=SECRET, verify_token=VERIFY_TOKEN)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    session = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    lifespan = app.router.lifespan_context(app)
    isolated_session.run(lifespan.__aenter__())

    def request(method, path, **kwargs):
        # pytest swaps capture streams between fixture setup and the test call.
        configure_logging()
        return isolated_session.run(session.request(method, path, **kwargs))

    try:
        yield SimpleNamespace(app=app, get=partial(request, "GET"), post=partial(request, "POST"))
    finally:
        configure_logging()
        isolated_session.run(session.aclose())
        isolated_session.run(lifespan.__aexit__(None, None, None))


def signed(body: bytes) -> dict[str, str]:
    signature = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"x-hub-signature-256": "sha256=" + signature}


def test_verification_returns_plain_challenge_without_logging_secrets(client, capsys):
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "123456789",
        },
    )
    assert response.status_code == 200
    assert response.text == "123456789"
    assert response.headers["content-type"].startswith("text/plain")
    output = capsys.readouterr().err
    assert "Meta подтвердила" in output
    assert VERIFY_TOKEN not in output
    assert "123456789" not in output


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"},
        {"hub.mode": "other", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "123"},
        {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN},
        {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "<html>"},
        [
            ("hub.mode", "subscribe"),
            ("hub.verify_token", VERIFY_TOKEN),
            ("hub.verify_token", VERIFY_TOKEN),
            ("hub.challenge", "123"),
        ],
    ],
)
def test_rejects_invalid_verification(client, params):
    assert client.get("/webhook", params=params).status_code == 403


def test_signed_message_is_acknowledged_without_logging_private_data(client, capsys):
    body = json.dumps(
        {
            "object": "instagram",
            "entry": [
                {
                    "id": "private-account-id",
                    "messaging": [
                        {
                            "sender": {"id": "private-sender-id"},
                            "message": {"mid": "private-mid", "text": "private-message"},
                        }
                    ],
                }
            ],
        }
    ).encode()
    response = client.post("/webhook", content=body, headers=signed(body))
    assert response.status_code == 200
    assert response.text == "EVENT_RECEIVED"
    output = capsys.readouterr().err
    assert "записей 1; сообщений 1; изменений 0" in output
    for private in ("private-", SECRET, VERIFY_TOKEN):
        assert private not in output


@pytest.mark.parametrize("headers", [{}, {"x-hub-signature-256": "sha256=wrong"}])
def test_unsigned_requests_are_rejected_without_logging_body(client, headers, capsys):
    response = client.post("/webhook", content=b"private-message", headers=headers)
    assert response.status_code == 403
    assert "private-message" not in capsys.readouterr().err


def test_signature_covers_exact_body_bytes(client):
    body = b'{"object":"instagram","entry":[]}'
    assert client.post("/webhook", content=body + b" ", headers=signed(body)).status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"\xff",
        b"[]",
        b'{"object":"page","entry":[]}',
        b'{"object":"instagram","entry":{}}',
        b'{"object":"instagram","entry":[null]}',
        b'{"object":"instagram","entry":[{"messaging":{}}]}',
        b'{"object":"instagram","entry":[{"changes":[null]}]}',
    ],
)
def test_signed_malformed_payload_is_rejected(client, body):
    assert client.post("/webhook", content=body, headers=signed(body)).status_code == 400


def test_change_notification_is_acknowledged(client, capsys):
    body = b'{"object":"instagram","entry":[{"changes":[{"field":"messages"}]}]}'
    assert client.post("/webhook", content=body, headers=signed(body)).status_code == 200
    assert "изменений 1" in capsys.readouterr().err


def test_oversized_body_is_rejected(client, monkeypatch):
    monkeypatch.setattr(webhook_server, "MAX_BODY_BYTES", 10)
    body = b"a" * 11
    assert client.post("/webhook", content=body, headers=signed(body)).status_code == 413


def test_slow_body_times_out(client, monkeypatch):
    monkeypatch.setattr(webhook_server, "BODY_TIMEOUT", 0.001)

    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.02)
            yield b"body"

    response = client.post("/webhook", content=SlowBody(), headers=signed(b"body"))
    assert response.status_code == 408


def test_unexpected_error_does_not_expose_exception_or_payload(client, capsys):
    @client.app.get("/fail")
    async def fail():
        raise RuntimeError("private-error")

    response = client.get("/fail?token=private-token")
    assert response.status_code == 500
    assert "private" not in response.text
    output = capsys.readouterr().err
    assert "private" not in output, output


def test_health_does_not_expose_configuration_or_docs(client):
    assert client.get("/health").json() == {"status": "ok"}
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("secret, token", [("", VERIFY_TOKEN), (SECRET, ""), (" ", " ")])
def test_missing_credentials_prevent_start(secret, token):
    with pytest.raises(ValueError, match="APP_SECRET.*WEBHOOK_VERIFY_TOKEN"):
        webhook_server.create_app(app_secret=secret, verify_token=token)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.ru.tuna.am",
        "https://example.ru.tuna.am/",
        "https://example.ru.tuna.am/webhook",
    ],
)
def test_callback_uses_tunnel_address(url):
    assert webhook_server.callback_url(url) == "https://example.ru.tuna.am/webhook"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.ru.tuna.am",
        "https://user:private-password@example.ru.tuna.am",
        "https://example.ru.tuna.am/?token=private-token",
        "https://example.ru.tuna.am/#private-token",
        "https://example.ru.tuna.am/other",
        "https://example.ru.tuna.am:bad",
        "https://example.ru.tuna.am:0",
        "https://[invalid",
        "https://example.ru.tuna.am\n.evil.test",
        "",
    ],
)
def test_callback_rejects_invalid_or_sensitive_urls(url):
    with pytest.raises(ValueError) as error:
        webhook_server.callback_url(url)
    assert "private" not in str(error.value)


def test_start_prompts_for_tunnel_and_disables_uvicorn_logs(monkeypatch, capsys):
    import config

    monkeypatch.setattr(config, "WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)
    prompt = Mock(return_value="https://example.ru.tuna.am")
    monkeypatch.setattr("builtins.input", prompt)
    server = Mock(started=True)
    factory = Mock(return_value=server)
    monkeypatch.setattr(webhook_server.uvicorn, "Server", factory)
    assert webhook_server.main() == 0
    assert "HTTPS" in prompt.call_args.args[0]
    server.run.assert_called_once_with()
    settings = factory.call_args.args[0]
    assert settings.host == "127.0.0.1" and settings.port == 8000
    assert settings.access_log is False
    assert settings.proxy_headers is False
    assert settings.log_config == webhook_server.UVICORN_LOG_CONFIG
    output = capsys.readouterr().err
    assert "https://example.ru.tuna.am/webhook" in output
    assert SECRET not in output and VERIFY_TOKEN not in output


def test_cancelled_console_input_does_not_start_server(monkeypatch):
    import config

    monkeypatch.setattr(config, "WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError))
    server = Mock()
    monkeypatch.setattr(webhook_server.uvicorn, "Server", server)
    assert webhook_server.main() == 1
    server.assert_not_called()
