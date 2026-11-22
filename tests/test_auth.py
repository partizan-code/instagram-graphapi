import os
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.fixture
def login(monkeypatch):
    import auth

    monkeypatch.setattr(auth.secrets, "token_urlsafe", lambda size: "test-state")
    browser = Mock()
    monkeypatch.setattr(auth.webbrowser, "open", browser)
    monkeypatch.setattr(
        "builtins.input", lambda prompt: "https://localhost/?code=test-code&state=test-state"
    )
    return browser


def test_save_token_updates_file_and_process_environment(tmp_path, monkeypatch):
    import auth
    import config

    env_file = tmp_path / ".env"
    env_file.write_text("APP_ID=test-app\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    monkeypatch.setenv("META_ACCESS_TOKEN", "old-test-token")

    auth.save_token("new-test-token")

    assert os.environ["META_ACCESS_TOKEN"] == "new-test-token"
    assert "META_ACCESS_TOKEN='new-test-token'" in env_file.read_text(encoding="utf-8")
    assert "APP_ID=test-app" in env_file.read_text(encoding="utf-8")


def test_login_uses_configuration_and_state(login):
    import auth

    assert auth.get_auth_code() == "test-code"
    url = urlsplit(login.call_args.args[0])
    assert url.netloc == "www.facebook.com" and url.path == "/v27.0/dialog/oauth"
    assert parse_qs(url.query) == {
        "client_id": ["test-app"],
        "config_id": ["test-config"],
        "redirect_uri": ["https://localhost/"],
        "response_type": ["code"],
        "override_default_response_type": ["true"],
        "state": ["test-state"],
    }


@pytest.mark.parametrize("setting", ["APP_ID", "META_CONFIG_ID"])
def test_missing_oauth_settings_fail_before_browser_opens(monkeypatch, login, setting):
    import auth
    import config

    monkeypatch.setattr(config, setting, "")

    with pytest.raises(RuntimeError, match=setting):
        auth.get_auth_code()
    login.assert_not_called()


@pytest.mark.parametrize(
    "url, message",
    [
        ("https://other.invalid/?code=private&state=test-state", "REDIRECT_URI"),
        ("https://localhost/wrong?code=private&state=test-state", "REDIRECT_URI"),
        ("https://localhost/?code=private&state=wrong", "state"),
        ("https://localhost/?code=private", "state"),
        ("https://localhost/?state=test-state", "код авторизации"),
        ("https://localhost/?code=a&code=b&state=test-state", "код авторизации"),
        ("https://localhost/?error=private&state=test-state", "отклонена"),
    ],
)
def test_login_rejects_untrusted_or_failed_callback(login, monkeypatch, url, message):
    import auth

    monkeypatch.setattr("builtins.input", lambda prompt: url)
    with pytest.raises(RuntimeError, match=message) as error:
        auth.get_auth_code()
    assert "private" not in str(error.value)


def test_code_exchange_directly_obtains_and_saves_meta_token(
    graph, reply, login, tmp_path, monkeypatch
):
    import auth
    import config

    env_file = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    monkeypatch.setenv("META_ACCESS_TOKEN", "old-test-token")
    response = reply({"access_token": "new-test-token"})
    graph.get.return_value = response
    assert auth.obtain_token() == "new-test-token"
    graph.get.assert_called_once_with(
        "https://graph.facebook.com/v27.0/oauth/access_token",
        params={
            "client_id": "test-app",
            "client_secret": "test-secret",
            "redirect_uri": "https://localhost/",
            "code": "test-code",
        },
        timeout=30,
        allow_redirects=False,
    )
    graph.post.assert_not_called()
    assert graph.headers == {}
    response.close.assert_called_once()
    assert "META_ACCESS_TOKEN='new-test-token'" in env_file.read_text(encoding="utf-8")
    assert "INSTAGRAM_TOKEN" not in env_file.read_text(encoding="utf-8")


def test_business_token_refresh_uses_owner_and_proof_without_saving(graph, reply):
    import hashlib
    import hmac

    import auth

    graph.get.return_value = reply({"id": "system-user", "client_business_id": "client-business"})
    response = reply({"access_token": "refreshed-token"})
    graph.post.return_value = response
    original = os.environ["META_ACCESS_TOKEN"]
    assert auth.refresh(original) == {"access_token": "refreshed-token"}
    graph.get.assert_called_once_with(
        "https://graph.facebook.com/v27.0/me",
        params={"fields": "client_business_id"},
        timeout=30,
        allow_redirects=False,
    )
    graph.post.assert_called_once_with(
        "https://graph.facebook.com/v27.0/client-business/system_user_access_tokens",
        data={
            "appsecret_proof": hmac.new(
                b"test-secret", original.encode(), hashlib.sha256
            ).hexdigest(),
            "system_user_id": "system-user",
            "set_token_expires_in_60_days": "true",
        },
        timeout=30,
        allow_redirects=False,
    )
    assert graph.headers == {"Authorization": f"Bearer {original}"}
    assert os.environ["META_ACCESS_TOKEN"] == original
    response.close.assert_called_once()


def test_refresh_cannot_fall_back_to_system_user_or_instagram_id(graph, reply):
    import auth

    graph.get.return_value = reply({"id": "system-user"})
    with pytest.raises(RuntimeError, match="client_business_id"):
        auth.refresh("test-token")
    graph.post.assert_not_called()


def test_refresh_permission_error_is_safe_and_never_saves_token(graph, reply):
    import auth

    graph.get.return_value = reply({"id": "system-user", "client_business_id": "client-business"})
    graph.post.return_value = reply({"error": {"code": 10, "message": "private-token"}}, 403)
    original = os.environ["META_ACCESS_TOKEN"]
    with pytest.raises(RuntimeError, match="HTTP=403; code=10") as error:
        auth.refresh(original)
    assert "private" not in str(error.value)
    assert os.environ["META_ACCESS_TOKEN"] == original


def test_failed_exchange_leaves_saved_token_untouched(graph, reply, login, tmp_path, monkeypatch):
    import auth
    import config

    env_file = tmp_path / ".env"
    env_file.write_text("META_ACCESS_TOKEN=existing-test-token\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    graph.get.return_value = reply({"expires_in": 3600})
    with pytest.raises(RuntimeError, match="не вернула токен"):
        auth.obtain_token()
    assert env_file.read_text(encoding="utf-8") == "META_ACCESS_TOKEN=existing-test-token\n"
