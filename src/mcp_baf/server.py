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
    client = OneCClient(config)
    audit = AuditLog(
        config.cache_dir, config.audit_max_size_mib, config.audit_archives,
        service="mcp-baf",
    )

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
        instructions=(
            "MCP-сервер для работы с базой 1С:Предприятие через HTTP-сервис."
        ),
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

    return mcp
