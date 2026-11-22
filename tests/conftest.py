"""Keep the entire test session isolated from local secrets and network access."""

import json
import os
import socket
from unittest.mock import MagicMock, Mock, patch

import dotenv
import pytest
import requests

from logging_config import configure_logging, logger


@pytest.fixture(autouse=True)
def console_logging(capsys):
    configure_logging()
    yield
    logger.remove()


@pytest.fixture(scope="session", autouse=True)
def isolated_session():
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in tests")

    with (
        patch.dict(
            os.environ,
            {
                "APP_ID": "test-app",
                "APP_SECRET": "test-secret",
                "INSTAGRAM_TOKEN": "test-token",
                "META_ACCESS_TOKEN": "test-meta-token",
                "META_CONFIG_ID": "test-config",
                "INSTAGRAM_ACCOUNT_ID": "12345",
            },
            clear=True,
        ),
        patch.object(dotenv, "load_dotenv", return_value=False),
        patch.object(requests.sessions.Session, "request", side_effect=blocked),
        patch.object(socket.socket, "connect", side_effect=blocked),
        patch.object(socket.socket, "connect_ex", side_effect=blocked),
        patch.object(socket, "getaddrinfo", side_effect=blocked),
    ):
        yield


@pytest.fixture
def graph(monkeypatch):
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    monkeypatch.setattr(requests, "Session", Mock(return_value=session))
    return session


@pytest.fixture
def reply():
    def make(payload, status=200):
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(payload).encode()
        response.close = Mock()
        return response

    return make
