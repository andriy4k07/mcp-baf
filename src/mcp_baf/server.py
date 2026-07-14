"""Сборка MCP-сервера: создание FastMCP и регистрация инструментов."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from mcp_baf_audit import AuditLog
from mcp_baf import prompts
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.dumpindex import DumpIndex
from mcp_baf.tools import (
    bsl_help,
    configuration_info,
    eventlog,
    form,
    metadata,
    object_structure,
    query,
    search_code,
    validate_query,
)

logger = logging.getLogger(__name__)

# Версия расширения 1С, с которой совместим этот сервер.
EXPECTED_EXTENSION_VERSION = "0.4.2"

_INSTRUCTIONS = (
    "MCP-сервер для ЧТЕНИЯ базы 1С:Предприятие (BAF) через HTTP-сервис: "
    "метаданные, запросы, полнотекстовый поиск по коду, журнал регистрации, "
    "справка BSL. Записи в базу нет.\n"
    "Порядок работы с незнакомой базой: get_configuration_info (что за "
    "конфигурация) -> get_metadata_tree (какие объекты есть) -> "
    "get_object_structure (точные имена реквизитов/табличных частей) -> "
    "validate_query -> execute_query. Имена объектов и полей бери из этих "
    "инструментов, не угадывай.\n"
    "Код конфигурации ищи через search_code (требует запуска с --dump); "
    "синтаксис встроенных функций BSL — bsl_syntax_help; структура форм — "
    "get_form_structure (полная тоже требует --dump); ошибки и действия "
    "пользователей — get_event_log."
)


def _strip_schema_titles(schema: dict) -> None:
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
                _strip_schema_titles(sub)
    for key in ("items", "additionalProperties"):
        sub = schema.get(key)
        if isinstance(sub, dict):
            _strip_schema_titles(sub)
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        subs = schema.get(key)
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, dict):
                    _strip_schema_titles(sub)
    defs = schema.get("$defs")
    if isinstance(defs, dict):
        for sub in defs.values():
            if isinstance(sub, dict):
                _strip_schema_titles(sub)


async def _check_extension_version(client: OneCClient, audit: AuditLog) -> None:
    """Сверяет версию расширения 1С с ожидаемой.

    Эндпоинт /version может отсутствовать в старых расширениях —
    в этом случае проверка молча пропускается.
    """
    try:
        info = await asyncio.wait_for(client.get("/version"), timeout=3)
    except Exception:  # noqa: BLE001 — любая ошибка означает «пропустить»
        return
    version = info.get("version", "") if isinstance(info, dict) else ""
    if version != EXPECTED_EXTENSION_VERSION:
        logger.error(
            "Extension version mismatch: got %s, expected %s. "
            'Update: mcp-baf --install "path\\to\\db"',
            version, EXPECTED_EXTENSION_VERSION,
        )
        audit.write(
            "extension_version_mismatch",
            got=version, expected=EXPECTED_EXTENSION_VERSION,
        )


def create_server(config: Config) -> FastMCP:
    audit = AuditLog(
        config.cache_dir, config.audit_max_size_mib, config.audit_archives,
        service="mcp-baf",
    )
    # Клиент получает audit → каждый вызов 1С оставляет событие one_c.http,
    # наследующее trace_id текущего инструмента (см. tools.common.traced_text).
    client = OneCClient(config, audit=audit)

    # Индекс строится в фоновом потоке — сервер стартует, не дожидаясь его.
    index = None
    if config.dump_dir:
        index = DumpIndex(
            config.dump_dir,
            cache_dir=config.cache_dir,
            reindex=config.reindex,
            show_progress=config.show_progress,
        )

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
        from mcp_baf import __version__

        # Пароль в аудит не попадает — только адрес и имя пользователя.
        audit.write(
            "server_start",
            version=__version__, base_url=config.base_url, user=config.user,
        )
        version_check = asyncio.create_task(
            _check_extension_version(client, audit)
        )
        try:
            yield
        finally:
            version_check.cancel()
            await client.aclose()
            if index is not None:
                index.close()
            audit.write("server_stop")

    mcp = FastMCP(
        name="mcp-baf",
        instructions=_INSTRUCTIONS,
        lifespan=lifespan,
    )

    # Порядок регистрации совпадает с Go-версией (server/server.go).
    metadata.register(mcp, client, audit)
    object_structure.register(mcp, client, audit)
    query.register(mcp, client, audit)
    if index is not None:
        search_code.register(mcp, index, audit)
    # dump-директория позволяет form-инструменту обогащать ответ из Form.xml.
    form.register(mcp, client, audit, config.dump_dir)
    validate_query.register(mcp, client, audit)
    eventlog.register(mcp, client, audit)
    configuration_info.register(mcp, client, audit)
    bsl_help.register(mcp, audit)
    prompts.register(mcp)

    # Схемы чистятся после регистрации всех инструментов; валидацию вызовов
    # это не задевает (она идёт по fn_metadata, а не по этому dict).
    for tool in mcp._tool_manager._tools.values():  # noqa: SLF001
        _strip_schema_titles(tool.parameters)

    return mcp
