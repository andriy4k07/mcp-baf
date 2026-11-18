"""Доступность HTTP-инструментов по эффективным правам пользователя сервиса."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import re
import time

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp_baf_audit import AuditWriter, get_trace_id, new_trace_id, set_trace_id

from mcp_baf.client import OneCClient, OneCError
from mcp_baf.tools.common import CLIENT_VISIBLE_ERRORS, traced_text

# Ключи соответствуют GET /capabilities; локальные инструменты здесь отсутствуют.
TOOL_METHODS = {
    "get_metadata_tree": "metadata.GET",
    "get_object_structure": "object.GET",
    "get_form_structure": "form.GET",
    "get_configuration_info": "configuration.GET",
    "execute_query": "query.POST",
    "validate_query": "validate-query.POST",
    "get_event_log": "eventlog.POST",
    "find_object_references": "refs.POST",
    "get_object_link": "object-link.POST",
    "get_metadata_rights": "metadata-rights.POST",
}


# Техжурнал читается локально: при недоступной 1С get_event_log остаётся
# только с source=techlog (диагностика упавшей базы). Явный отказ 1С
# (есть reason) по-прежнему закрывает инструмент целиком.
OFFLINE_TOOL, OFFLINE_ARG, OFFLINE_VALUE = "get_event_log", "source", "techlog"


# reason из тела ошибки 1С: {"error": ..., "reason": "method_use_denied"}.
# Клиент отдаёт тело как текст сообщения, поэтому код причины достаём из него.
_REASON_RE = re.compile(r'"reason"\s*:\s*"([^"]+)"')


def capabilities_failure_reason(exc: BaseException) -> str:
    """Код причины отказа `/capabilities` (`reason` из тела 1С), если он есть.

    Без него в аудите и тексте ошибки «нет связи», «нет расширения» и «нет
    права использования метода» выглядят одинаково.
    """
    match = _REASON_RE.search(str(exc))
    return match.group(1) if match else ""


_STATUS_RE = re.compile(r"^1C returned status (\d+)")
_STATUS_CAUSES = {
    401: "невірний логін/пароль HTTP-користувача",
    404: "немає HTTP-сервісу/розширення за --base",
}


def capabilities_failure_cause(exc: BaseException) -> str:
    """Короткая безопасная причина сбоя `/capabilities` для агента.

    Транспортный текст уже прошёл scrub_error_detail в клиенте; для HTTP-статуса
    берём только код: тело ответа 1С может содержать данные базы.
    """
    text = str(exc)
    if isinstance(exc, TimeoutError) and not text:
        return "таймаут ответа 1С (15 с)"
    if not isinstance(exc, OneCError):
        return ""
    if match := _STATUS_RE.match(text):
        status = int(match.group(1))
        hint = _STATUS_CAUSES.get(status)
        return f"HTTP {status}" + (f" ({hint})" if hint else "")
    prefix = "executing request to 1C: "
    if text.startswith(prefix):
        return text[len(prefix):][:150]
    return ""


def strip_schema_titles(schema: dict) -> None:
    """Убирает автогенерированные pydantic'ом "title" из JSON-схемы.

    Смысла для модели они не несут ("object_name" -> "Object Name"), но
    раздувают init-payload. Чистятся только узлы схемы; ключи словаря
    properties (имена параметров) не трогаются.
    """
    schema.pop("title", None)
    props = schema.get("properties")
    if isinstance(props, dict):
        for sub in props.values():
            if isinstance(sub, dict):
                strip_schema_titles(sub)
    for key in ("items", "additionalProperties"):
        sub = schema.get(key)
        if isinstance(sub, dict):
            strip_schema_titles(sub)
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        subs = schema.get(key)
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, dict):
                    strip_schema_titles(sub)
    defs = schema.get("$defs")
    if isinstance(defs, dict):
        for sub in defs.values():
            if isinstance(sub, dict):
                strip_schema_titles(sub)


class AccessMCP(MCPServer):
    """Скрывает недоступные инструменты и проверяет прямые вызовы."""

    def __init__(self, *args, access_client: OneCClient, audit: AuditWriter,
                 techlog_offline: bool = False, **kwargs):
        self.access_client = access_client
        self.techlog_offline = techlog_offline
        self._access_reason = ""
        self.access_audit = audit
        self._allowed: set[str] = set()
        self._expires = 0.0
        self._access_lock = asyncio.Lock()
        self._access_error = ""
        # Набор прав, по которому клиенту последний раз отдан tools/list.
        self._listed: set[str] | None = None
        self._recheck: asyncio.Task | None = None
        super().__init__(*args, **kwargs)

    async def _notify_if_changed(self, context: Context | None) -> None:
        """Шлёт tools/list_changed, если права разошлись с отданным списком.

        Клиент кэширует tools/list: после сбоя /capabilities он иначе не
        увидит HTTP-инструменты до переподключения. Сессия доступна только из
        контекста запроса, поэтому уведомление уходит из call_tool.
        """
        relevant = self._allowed & set(TOOL_METHODS.values())
        if context is None or self._listed is None or self._listed == relevant:
            return
        self._listed = relevant
        # Уведомление — best effort: его сбой не должен ломать сам вызов.
        with contextlib.suppress(Exception):
            await context.notify_tools_changed()  # subscriptions/listen (2026-07-28+)
        with contextlib.suppress(Exception):
            # Старые протоколы; на новом SDK сам отбрасывает такую копию.
            await context.session.send_tool_list_changed()

    async def _recheck_access(self, context: Context | None) -> None:
        await self._capabilities()
        await self._notify_if_changed(context)

    async def _capabilities(self) -> tuple[set[str], str]:
        # Кэш общий для list и call: право на метод всё равно проверяет сам
        # обработчик расширения (403), а второй запрос на каждый вызов
        # удваивал бы число сеансов базы.
        async with self._access_lock:
            if time.monotonic() < self._expires:
                return self._allowed, self._access_error
            try:
                # Первый запрос после простоя поднимает сеанс 1С: при коротком
                # таймауте клиент кэширует список без HTTP-инструментов.
                result = await asyncio.wait_for(self.access_client.get("/capabilities"), 15)
                methods = result["methods"]
                if not isinstance(methods, list) or not all(isinstance(x, str) for x in methods):
                    raise ValueError("invalid capabilities response")
                self._allowed = set(methods)
                self._access_error = ""
                self._access_reason = ""
            except Exception as exc:
                self._allowed = set()
                reason_code = capabilities_failure_reason(exc)
                self._access_reason = reason_code
                self._access_error = (
                    "Проверка прав /capabilities недоступна. Проверьте подключение, "
                    "права HTTP-пользователя и установите расширение 0.6.0 или новее."
                    + (f" Причина 1С: {reason_code}." if reason_code else "")
                )
                if cause := capabilities_failure_cause(exc):
                    self._access_error += f" Причина: {cause}."
                if self.techlog_offline and not reason_code:
                    self._access_error += ' Доступно без 1С: get_event_log(source="techlog").'
                # Причину отказа нельзя терять: без неё в аудите «нет связи»,
                # «нет расширения» и «нет права» выглядят одинаково. Пишем класс
                # и первые 300 символов ошибки клиента (URL и пароль в него не
                # попадают; тело /capabilities — только текст ошибки 1С); данные
                # базы и секреты в запись не попадают, их редактирует пакет аудита.
                self.access_audit.write(
                    "access.capabilities_unavailable",
                    level="error",
                    trace_id=get_trace_id(),
                    reason_code=reason_code,
                    reason=type(exc).__name__,
                    error=str(exc)[:300],
                )

            # Отказ держим недолго, чтобы восстановление связи не ждало 30 с.
            self._expires = time.monotonic() + (30 if self._allowed else 5)
            return self._allowed, self._access_error

    async def has_method(self, method: str) -> bool:
        """Есть ли у пользователя HTTP-метод (кэш /capabilities); для необязательных подсказок."""
        allowed, _ = await self._capabilities()
        return method in allowed

    def _offline(self) -> bool:
        """1С недоступна (не явный отказ), а техжурнал настроен."""
        return self.techlog_offline and bool(self._access_error) and not self._access_reason

    async def list_tools(self):
        tools = await super().list_tools()
        allowed, _ = await self._capabilities()
        self._listed = allowed & set(TOOL_METHODS.values())
        visible = [
            t for t in tools
            if t.name not in TOOL_METHODS or TOOL_METHODS[t.name] in allowed
            or (t.name == OFFLINE_TOOL and self._offline())
        ]
        # Схемы чистим здесь, а не через приватный _tool_manager: list_tools —
        # публичный метод SDK и единственный источник payload tools/list.
        # Снимаем deepcopy, потому что вложенные dict'ы MCPTool делят объекты
        # с внутренней схемой SDK; мутировать её нельзя. Валидация вызовов
        # идёт по fn_metadata и этой схемы не касается.
        for tool in visible:
            schema = copy.deepcopy(tool.input_schema)
            strip_schema_titles(schema)
            tool.input_schema = schema
        return visible

    async def call_tool(self, name: str, arguments: dict, context: Context | None = None):
        # Каждый вызов — отдельная операция: contextvar переживает вызов в
        # сессии, и без сброса все вызовы делили бы один trace_id.
        previous = get_trace_id()
        set_trace_id(new_trace_id())
        try:
            return await self._call_tool(name, arguments, context)
        finally:
            set_trace_id(previous)

    async def _call_tool(self, name: str, arguments: dict, context: Context | None):
        if name in TOOL_METHODS:
            # HTTP-проверка наследует trace инструмента; успешную проверку
            # не выдаём за второй tool.call, отказ пишем без аргументов/данных.
            allowed, error = await self._capabilities()
            await self._notify_if_changed(context)
            offline_ok = (
                name == OFFLINE_TOOL and self._offline()
                and arguments.get(OFFLINE_ARG) == OFFLINE_VALUE
            )
            if TOOL_METHODS[name] not in allowed and not offline_ok:
                async def denied():
                    raise ToolError(error or "Нет права использования HTTP-метода инструмента.")
                return await traced_text(self.access_audit, name, denied, args={"access_denied": True})
        elif (
            self._access_error and time.monotonic() >= self._expires
            and (self._recheck is None or self._recheck.done())
        ):
            # После сбоя клиент видит только локальные инструменты и HTTP не
            # зовёт; права перепроверяем в фоне, не задерживая локальный вызов.
            self._recheck = asyncio.create_task(self._recheck_access(context))
        try:
            return await super().call_tool(name, arguments, context)
        except UnexpectedToolError as exc:
            # Часть инструментов проверяет аргументы до traced_text — их
            # ожидаемые ошибки доходят сюда обёрнутыми; раскрываем в единой точке.
            if isinstance(exc.__cause__, CLIENT_VISIBLE_ERRORS):
                raise ToolError(str(exc.__cause__)) from exc.__cause__
            raise
