"""Доступность HTTP-инструментов по эффективным правам пользователя сервиса."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import time

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp_baf_audit import AuditWriter, get_trace_id, new_trace_id, set_trace_id

from mcp_baf.client import OneCClient
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

    def __init__(self, *args, access_client: OneCClient, audit: AuditWriter, **kwargs):
        self.access_client = access_client
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
            except Exception as exc:
                self._allowed = set()
                self._access_error = (
                    "Проверка прав /capabilities недоступна. Проверьте подключение, "
                    "права HTTP-пользователя и установите расширение 0.6.0 или новее."
                )
                # Причину отказа нельзя терять: без неё в аудите «нет связи»,
                # «нет расширения» и «нет права» выглядят одинаково. Пишем класс
                # и первые 300 символов ошибки клиента (URL и пароль в него не
                # попадают; тело /capabilities — только текст ошибки 1С); данные
                # базы и секреты в запись не попадают, их редактирует пакет аудита.
                self.access_audit.write(
                    "access.capabilities_unavailable",
                    level="error",
                    trace_id=get_trace_id(),
                    reason=type(exc).__name__,
                    error=str(exc)[:300],
                )

            # Отказ держим недолго, чтобы восстановление связи не ждало 30 с.
            self._expires = time.monotonic() + (30 if self._allowed else 5)
            return self._allowed, self._access_error

    async def list_tools(self):
        tools = await super().list_tools()
        allowed, _ = await self._capabilities()
        self._listed = allowed & set(TOOL_METHODS.values())
        visible =[t for t in tools if t.name not in TOOL_METHODS or TOOL_METHODS[t.name] in allowed]
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
            if TOOL_METHODS[name] not in allowed:
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
