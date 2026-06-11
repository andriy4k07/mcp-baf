"""Асинхронный HTTP-клиент для общения с 1С:Предприятие."""

from __future__ import annotations

import json
from typing import Any

import httpx

from mcp_baf.config import Config

_MIB = 1 << 20


class OneCError(Exception):
    """Ошибка взаимодействия с 1С с понятным пользователю текстом."""


class OneCClient:
    """HTTP-клиент к HTTP-сервису 1С.

    Если задан пользователь, ко всем запросам добавляется basic auth.
    Ответ крупнее лимита отбрасывается с понятной ошибкой вместо OOM.
    """

    def __init__(self, config: Config) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._max_response_size = config.max_response_size_mib * _MIB

        auth = None
        if config.user:
            auth = httpx.BasicAuth(config.user, config.password)

        self._http = httpx.AsyncClient(
            auth=auth,
            timeout=httpx.Timeout(config.request_timeout),
            # Закрываем соединение после каждого запроса,
            # чтобы не упираться в лимит сеансов 1С.
            headers={"Connection": "close"},
        )

    async def get(self, endpoint: str) -> Any:
        """GET-запрос к эндпоинту 1С с разбором JSON-ответа."""
        return await self._do("GET", endpoint)

    async def post(self, endpoint: str, body: Any) -> Any:
        """POST-запрос к эндпоинту 1С с JSON-телом и разбором JSON-ответа."""
        return await self._do("POST", endpoint, body)

    async def _do(self, method: str, endpoint: str, body: Any = None) -> Any:
        kwargs: dict[str, Any] = {}
        if body is not None:
            kwargs["json"] = body

        try:
            async with self._http.stream(
                method, self._base_url + endpoint, **kwargs
            ) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread())[:4096].decode("utf-8", "replace")
                    raise OneCError(
                        f"1C returned status {resp.status_code}: {detail}"
                    )

                # Читаем не более limit+1 байт: если поток обрезан потолком,
                # выдаём понятную ошибку вместо невнятной ошибки декодера.
                raw = bytearray()
                async for chunk in resp.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > self._max_response_size:
                        raise OneCError(self._response_too_large_message())
        except httpx.HTTPError as exc:
            raise OneCError(f"executing request to 1C: {exc}") from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise OneCError(f"decoding 1C response: {exc}") from exc

    def _response_too_large_message(self) -> str:
        limit_mib = self._max_response_size // _MIB
        return (
            f"ответ 1С превысил лимит размера ({limit_mib} MiB). "
            "Увеличьте лимит флагом --max-response-size <МиБ> "
            "или переменной окружения mcp_baf_MAX_RESPONSE_SIZE"
        )

    async def aclose(self) -> None:
        await self._http.aclose()
