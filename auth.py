"""Авторизация и обновление бизнес-токена через Meta Unified Login."""

import hashlib
import hmac
import os
import secrets
import webbrowser
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from dotenv import set_key

import config
from api import call
from logging_config import logger


def save_token(token: str) -> None:
    """Сохраняет META_ACCESS_TOKEN в .env и окружение текущего процесса."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Не получен токен Meta.")
    set_key(str(config.ENV_PATH), "META_ACCESS_TOKEN", token)
    os.environ["META_ACCESS_TOKEN"] = token


def get_auth_code() -> str:
    """Открывает вход Meta и проверяет URL редиректа, state и code."""
    if not config.APP_ID or not config.META_CONFIG_ID:
        raise RuntimeError("Укажите APP_ID и META_CONFIG_ID для Unified Login.")
    expected = urlsplit(config.REDIRECT_URI)
    if expected.scheme != "https" or not expected.netloc or expected.fragment:
        raise RuntimeError("REDIRECT_URI должен быть HTTPS URL без фрагмента.")
    state = secrets.token_urlsafe(32)
    query = urlencode(
        {
            "client_id": config.APP_ID,
            "config_id": config.META_CONFIG_ID,
            "redirect_uri": config.REDIRECT_URI,
            "response_type": "code",
            "override_default_response_type": "true",
            "state": state,
        }
    )
    logger.info("Открываю браузер. Подтвердите доступ и скопируйте адрес редиректа.")
    webbrowser.open(f"https://www.facebook.com/{config.META_API_VERSION}/dialog/oauth?{query}")
    redirected = urlsplit(input("Вставьте полный URL после авторизации: ").strip())
    params = parse_qs(redirected.query, keep_blank_values=True)
    if (redirected.scheme, redirected.netloc, redirected.path) != (
        expected.scheme,
        expected.netloc,
        expected.path,
    ) or any(params.get(key) != value for key, value in parse_qs(expected.query).items()):
        raise RuntimeError("Адрес редиректа не совпадает с REDIRECT_URI.")
    if params.get("state") != [state]:
        raise RuntimeError("Проверка state не пройдена. Повторите авторизацию.")
    if "error" in params:
        raise RuntimeError("Авторизация Meta отклонена.")
    codes = params.get("code", [])
    if len(codes) != 1 or not codes[0].strip():
        raise RuntimeError("Meta не вернула единственный код авторизации.")
    return codes[0]


def _token_response(payload: dict) -> dict:
    if not isinstance(payload.get("access_token"), str) or not payload["access_token"].strip():
        raise RuntimeError("Meta не вернула токен доступа.")
    return payload


def exchange_code(code: str) -> dict:
    """Обменивает code сразу на Business Integration System User Access Token."""
    config.require_app_credentials()
    return _token_response(
        call(
            "oauth/access_token",
            client_id=config.APP_ID,
            client_secret=config.APP_SECRET,
            redirect_uri=config.REDIRECT_URI,
            code=code,
        )
    )


def refresh(token: str) -> dict:
    """Выпускает новый бизнес-токен на 60 дней; нужен business_management.

    Возвращает ответ Meta. Для сохранения вызовите save_token() явно.
    """
    config.require_app_credentials()
    owner = call("me", token, fields="client_business_id")
    business_id = owner.get("client_business_id")
    system_user_id = owner.get("id")
    if not all(isinstance(value, str) and value for value in (business_id, system_user_id)):
        raise RuntimeError("Meta не вернула client_business_id и ID системного пользователя.")
    proof = hmac.new(config.APP_SECRET.encode(), token.encode(), hashlib.sha256).hexdigest()
    return _token_response(
        call(
            f"{quote(business_id, safe='')}/system_user_access_tokens",
            token,
            method="POST",
            appsecret_proof=proof,
            system_user_id=system_user_id,
            set_token_expires_in_60_days="true",
        )
    )


def obtain_token() -> str:
    """Вход в браузере -> обмен кода -> сохранение META_ACCESS_TOKEN."""
    config.require_app_credentials()
    token = exchange_code(get_auth_code())["access_token"]
    save_token(token)
    logger.success("Авторизация Unified Login прошла успешно. Токен сохранён в .env.")
    return token
