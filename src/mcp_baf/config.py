"""Конфигурация MCP-сервера.

Приоритет источников (от низшего к высшему): значения по умолчанию,
переменные окружения, флаги командной строки.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://localhost:8080/hs/mcp-baf"

# Лимит размера ответа 1С по умолчанию, в мебибайтах (MiB).
# 128 MiB покрывает крупные базы с расширениями, оставаясь потолком против OOM.
DEFAULT_MAX_RESPONSE_SIZE_MIB = 128

# Таймаут HTTP-запроса к 1С по умолчанию, в секундах. Запас нужен
# для передачи крупных ответов /extensions (сотни мегабайт).
DEFAULT_REQUEST_TIMEOUT = 300


@dataclass
class Config:
    base_url: str = DEFAULT_BASE_URL
    user: str = ""
    password: str = ""
    max_response_size_mib: int = DEFAULT_MAX_RESPONSE_SIZE_MIB
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    # Путь к выгрузке конфигурации (DumpConfigToFiles); включает search_code.
    dump_dir: str = ""
    # Каталог кэша индекса и логов (по умолчанию платформенный кэш).
    cache_dir: str = ""
    # Принудительная пересборка кэша индекса.
    reindex: bool = False
    # Подробное логирование в файл server.log в кэш-каталоге.
    debug: bool = False
    # Управление прогрессом на stderr: True => выводить (терминальный запуск).
    show_progress: bool = False


def _env_int(name: str, default: int) -> int:
    """Читает целое из переменной окружения.

    Некорректные или неположительные значения игнорируются —
    остаётся значение по умолчанию (как в Go-версии).
    """
    value = os.environ.get(name, "")
    try:
        n = int(value)
    except ValueError:
        return default
    return n if n > 0 else default


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp-baf",
        description="MCP server for 1C:Enterprise HTTP service",
    )
    parser.add_argument("--base", default="", help="Base URL of 1C HTTP service")
    parser.add_argument("--user", default="", help="1C HTTP service user")
    parser.add_argument(
        "--pass", "--password", dest="password", default="",
        help="1C HTTP service password",
    )
    parser.add_argument(
        "--dump", default="",
        help="Path to DumpConfigToFiles output (enables search_code)",
    )
    parser.add_argument(
        "--cache-dir", default="",
        help="Directory for index cache and logs (default: platform cache dir)",
    )
    parser.add_argument(
        "--reindex", action="store_true",
        help="Force rebuild of search index cache",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose logging to file (server.log in cache dir). "
             "Also suppresses the stderr progress indicator.",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress all stderr progress output even in a terminal. "
             "Takes precedence over --verbose. Also activated by mcp_baf_NO_TTY=1.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Force progress output to stderr even when stdin is a pipe "
             "(useful for MCP client debugging). Overridden by --quiet.",
    )
    # Режим установки расширения.
    parser.add_argument(
        "--install", default="", metavar="DB_PATH",
        help="Install extension into 1C database at given path",
    )
    parser.add_argument(
        "--lang", default="ua", choices=("ua", "ru"),
        help="Language of extension synonyms for --install: "
             "ua (Ukrainian, default) or ru (Russian)",
    )
    parser.add_argument(
        "--server", action="store_true",
        help=r"Treat --install value as server connection string (server\database)",
    )
    parser.add_argument(
        "--platform", default="",
        help="Path to 1C platform executable (auto-detected if omitted)",
    )
    parser.add_argument(
        "--platform-version", default="",
        help="1C platform version override (e.g. 8.3.13), "
             "auto-detected from path if omitted",
    )
    parser.add_argument(
        "--db-user", default="",
        help="1C database user for DESIGNER (install mode)",
    )
    parser.add_argument(
        "--db-password", default="",
        help="1C database password for DESIGNER (install mode)",
    )
    parser.add_argument(
        "--max-response-size", type=int, default=0, metavar="MIB",
        help="Maximum size of a 1C HTTP response, in mebibytes (MiB). "
             f"Default: {DEFAULT_MAX_RESPONSE_SIZE_MIB}.",
    )
    parser.add_argument(
        "--request-timeout", type=int, default=0, metavar="SECONDS",
        help="Timeout for an HTTP request to 1C, in seconds. "
             f"Default: {DEFAULT_REQUEST_TIMEOUT}.",
    )
    parser.add_argument(
        "--version", action="version", version=f"mcp-baf {_version()}",
    )
    return parser.parse_args(argv)


def _version() -> str:
    from mcp_baf import __version__

    return __version__


def load_config(args: argparse.Namespace) -> Config:
    """Собирает конфигурацию: defaults -> env -> CLI-флаги."""
    cfg = Config(
        base_url=os.environ.get("mcp_baf_BASE_URL", DEFAULT_BASE_URL),
        user=os.environ.get("mcp_baf_USER", ""),
        password=os.environ.get("mcp_baf_PASSWORD", ""),
        max_response_size_mib=_env_int(
            "mcp_baf_MAX_RESPONSE_SIZE", DEFAULT_MAX_RESPONSE_SIZE_MIB
        ),
        request_timeout=_env_int("mcp_baf_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT),
    )

    if args.base:
        cfg.base_url = args.base
    if args.user:
        cfg.user = args.user
    if args.password:
        cfg.password = args.password
    if args.dump:
        cfg.dump_dir = args.dump
    if args.max_response_size > 0:
        cfg.max_response_size_mib = args.max_response_size
    if args.request_timeout > 0:
        cfg.request_timeout = args.request_timeout

    cfg.cache_dir = args.cache_dir or os.environ.get("mcp_baf_CACHE_DIR", "")
    cfg.reindex = args.reindex
    cfg.debug = args.debug

    # Эффективный TTY-режим: показывать прогресс при терминальном запуске.
    # --verbose форсирует вывод, --quiet и mcp_baf_NO_TTY=1 подавляют,
    # --debug уводит всё в файл вместо stderr.
    show = sys.stdin.isatty()
    if args.verbose:
        show = True
    if args.quiet or os.environ.get("mcp_baf_NO_TTY") == "1":
        show = False
    cfg.show_progress = show and not args.debug

    return cfg
