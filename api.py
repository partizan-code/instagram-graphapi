"""Общие HTTP-запросы к Meta Graph API без вывода секретов."""

import requests


def request(session: requests.Session, path: str, *, method: str = "GET", **params: object) -> dict:
    from config import GRAPH_BASE, HTTP_TIMEOUT, META_API_VERSION

    send = session.get if method == "GET" else session.post
    try:
        with send(
            f"{GRAPH_BASE}/{META_API_VERSION}/{path}",
            **{"params" if method == "GET" else "data": params},
            timeout=HTTP_TIMEOUT,
            allow_redirects=False,
        ) as response:
            try:
                payload = response.json()
            except ValueError:
                raise RuntimeError(
                    f"Meta вернула некорректный JSON [HTTP={response.status_code}]."
                ) from None
            if not isinstance(payload, dict):
                raise RuntimeError("Meta вернула неожиданный формат ответа.")
            if not 200 <= response.status_code < 300 or "error" in payload:
                error = payload.get("error")
                error = error if isinstance(error, dict) else {}
                codes = "; ".join(
                    f"{key}={value if type(value) is int else 'нет данных'}"
                    for key, value in (
                        ("code", error.get("code")),
                        ("subcode", error.get("error_subcode")),
                    )
                )
                raise RuntimeError(f"Ошибка Meta API [HTTP={response.status_code}; {codes}].")
            return payload
    except requests.RequestException:
        raise RuntimeError("Не удалось связаться с Meta API.") from None


def call(path: str, token: str = "", *, method: str = "GET", **params: object) -> dict:
    with requests.Session() as session:
        if token:
            session.headers["Authorization"] = f"Bearer {token}"
        return request(session, path, method=method, **params)
