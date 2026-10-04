"""Доступность HTTP-инструментов по эффективным правам пользователя сервиса."""

from __future__ import annotations

import asyncio
import time

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_baf_audit import AuditWriter, get_trace_id, new_trace_id, set_trace_id

from mcp_baf.client import OneCClient
from mcp_baf.tools.common import traced_text

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


class AccessMCP(MCPServer):
    """Скрывает недоступные инструменты и проверяет прямые вызовы."""

    def __init__(self, *args, access_client: OneCClient, audit: AuditWriter, **kwargs):
        self.access_client = access_client
        self.access_audit = audit
        self._allowed: set[str] = set()
        self._expires = 0.0
        self._access_lock = asyncio.Lock()
        self._access_error = ""
        super().__init__(*args, **kwargs)

    async def _capabilities(self, *, fresh: bool = False) -> set[str]:
        async with self._access_lock:
            if not fresh and time.monotonic() < self._expires:
                return self._allowed
            try:
                result = await asyncio.wait_for(self.access_client.get("/capabilities"), 5)
                methods = result["methods"]
                if not isinstance(methods, list) or not all(isinstance(x, str) for x in methods):
                    raise ValueError("invalid capabilities response")
                self._allowed = set(methods)
                self._access_error = ""
            except Exception:
                self._allowed = set()
                self._access_error = (
                    "Проверка прав /capabilities недоступна. Проверьте подключение, "
                    "права HTTP-пользователя и установите расширение 0.5.5 или новее."
                )
            self._expires = time.monotonic() + 30
            return self._allowed

    async def list_tools(self):
        tools = await super().list_tools()
        allowed = await self._capabilities()
        return [t for t in tools if t.name not in TOOL_METHODS or TOOL_METHODS[t.name] in allowed]

    async def call_tool(self, name: str, arguments: dict, context: Context | None = None):
        if name in TOOL_METHODS:
            # HTTP-проверка наследует trace инструмента; успешную проверку
            # не выдаём за второй tool.call, отказ пишем без аргументов/данных.
            set_trace_id(get_trace_id() or new_trace_id())
            allowed = await self._capabilities(fresh=True)
            if TOOL_METHODS[name] not in allowed:
                async def denied():
                    raise ToolError(self._access_error or "Нет права использования HTTP-метода инструмента.")
                return await traced_text(self.access_audit, name, denied, args={"access_denied": True})
        return await super().call_tool(name, arguments, context)
