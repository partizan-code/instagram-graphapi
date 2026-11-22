import json
from unittest.mock import MagicMock, Mock

import pytest
import requests

import main


def response(payload, status=200):
    reply = requests.Response()
    reply.status_code = status
    reply._content = json.dumps(payload).encode()
    reply.close = Mock()
    return reply


def accounts(*ids):
    return {"data": [{"id": value, "username": f"account_{value}"} for value in ids]}


@pytest.fixture
def session(monkeypatch):
    instance = MagicMock(spec=requests.Session)
    instance.headers = {}
    instance.__enter__.return_value = instance
    instance.__exit__.return_value = False
    instance.get.side_effect = [response(accounts("12345")), response({"data": []})]
    monkeypatch.setattr(main.requests, "Session", Mock(return_value=instance))
    return instance


def test_main_uses_two_bearer_gets_and_closes_resources(session, capsys):
    replies = [response(accounts("12345")), response({"data": []})]
    session.get.side_effect = replies
    assert main.main() == 0
    first, second = session.get.call_args_list
    assert first.args == ("https://graph.facebook.com/v27.0/me/assigned_instagram_accounts",)
    assert first.kwargs["params"] == {"fields": "id,username"}
    assert second.args == ("https://graph.facebook.com/v27.0/12345/conversations",)
    assert second.kwargs["params"] == {
        "platform": "instagram",
        "fields": "id,messages.limit(20){id,message,from,created_time}",
        "limit": 5,
    }
    assert session.headers == {"Authorization": "Bearer test-meta-token"}
    for call in (first, second):
        assert call.kwargs["timeout"] == 30 and call.kwargs["allow_redirects"] is False
        assert "access_token" not in call.kwargs["params"]
    for reply in replies:
        reply.close.assert_called_once()
    session.__exit__.assert_called_once()
    session.post.assert_not_called()
    assert "test-meta-token" not in capsys.readouterr().err


def test_all_messages_are_displayed_with_safe_text_and_partial_warnings(session, capsys):
    messages = [
        {
            "id": "m1",
            "message": "Добрый день!",
            "from": {"id": "customer", "username": "example"},
            "created_time": "2026-11-22T12:00:00+0000",
        },
        {"id": "m2", "message": "Hello\x1b[31m\rworld"},
        {"id": "m3"},
        {"id": "m4", "message": "Fourth"},
    ]
    session.get.side_effect = [
        response(accounts("12345")),
        response(
            {
                "data": [
                    {
                        "id": "conversation",
                        "messages": {
                            "data": messages,
                            "paging": {"next": "private-url-with-token"},
                        },
                    }
                ],
                "paging": {"next": "another-private-url"},
            }
        ),
    ]
    assert main.main() == 0
    output = capsys.readouterr().err
    for message in messages:
        assert message["id"] in output
    assert "Добрый день!" in output and "customer" in output and "@example" in output
    assert "2026-11-22T12:00:00+0000" in output
    assert "[Вложение или сообщение без текста]" in output
    assert "другие сообщения" in output and "другие страницы диалогов" in output
    assert "private" not in output and "\x1b" not in output and "\r" not in output
    assert session.get.call_count == 2


def test_explicit_account_is_used_instead_of_first(session, monkeypatch):
    import config

    monkeypatch.setattr(config, "INSTAGRAM_ACCOUNT_ID", "54321")
    session.get.side_effect = [response(accounts("12345", "54321")), response({"data": []})]
    assert main.main() == 0
    assert session.get.call_args.args[0].endswith("/54321/conversations")


@pytest.mark.parametrize(
    "payload",
    [
        accounts(),
        accounts("12345", "54321"),
        {
            **accounts("12345"),
            "paging": {"next": "private-url"},
        },
    ],
)
def test_ambiguous_or_incomplete_account_list_requires_id(session, monkeypatch, capsys, payload):
    import config

    monkeypatch.setattr(config, "INSTAGRAM_ACCOUNT_ID", "")
    session.get.side_effect = [response(payload)]
    assert main.main() == 1
    assert "INSTAGRAM_ACCOUNT_ID" in capsys.readouterr().err
    assert session.get.call_count == 1


def test_only_assigned_account_is_used_without_explicit_id(session, monkeypatch):
    import config

    monkeypatch.setattr(config, "INSTAGRAM_ACCOUNT_ID", "")
    assert main.main() == 0
    assert session.get.call_args.args[0].endswith("/12345/conversations")


def test_unknown_explicit_id_does_not_read_conversations(session, monkeypatch, capsys):
    import config

    monkeypatch.setattr(config, "INSTAGRAM_ACCOUNT_ID", "99999")
    assert main.main() == 1
    assert "не найден" in capsys.readouterr().err
    assert session.get.call_count == 1


@pytest.mark.parametrize(("status", "code"), [(400, 190), (403, 10), (500, 1), (429, 4)])
def test_api_errors_are_safe_and_not_retried(session, capsys, status, code):
    reply = response(
        {
            "error": {
                "code": code,
                "error_subcode": 123,
                "message": "private-response-test-meta-token",
            }
        },
        status,
    )
    session.get.side_effect = [reply]
    assert main.main() == 1
    output = capsys.readouterr().err
    assert f"HTTP={status}; code={code}; subcode=123" in output
    assert "private" not in output and "test-meta-token" not in output
    assert session.get.call_count == 1
    reply.close.assert_called_once()
    session.__exit__.assert_called_once()


def test_network_error_never_logs_exception_with_token(session, capsys):
    session.get.side_effect = requests.ConnectionError("private-url-test-meta-token")
    assert main.main() == 1
    output = capsys.readouterr().err
    assert "Не удалось связаться" in output and "test-meta-token" not in output


@pytest.mark.parametrize("payload", [[], {"data": "private-invalid-list"}])
def test_invalid_response_is_not_reported_as_empty_inbox(session, capsys, payload):
    session.get.side_effect = [response(payload)]
    assert main.main() == 1
    assert "private" not in capsys.readouterr().err


def test_invalid_json_closes_response_without_logging_body(session, capsys):
    reply = response({})
    reply._content = b"private-invalid-json"
    session.get.side_effect = [reply]
    assert main.main() == 1
    output = capsys.readouterr().err
    assert "некорректный JSON" in output and "private" not in output
    reply.close.assert_called_once()


def test_meta_token_is_required_without_legacy_fallback(session, monkeypatch, capsys):
    monkeypatch.delenv("META_ACCESS_TOKEN")
    assert main.main() == 1
    assert "META_ACCESS_TOKEN" in capsys.readouterr().err
    main.requests.Session.assert_not_called()
