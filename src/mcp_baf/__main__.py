"""Точка входа: mcp-baf --base <url> --user <user> --pass <password>."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys

from mcp_baf_audit import default_cache_dir
from mcp_baf.config import load_config, parse_args
from mcp_baf.server import create_server

SERVER_LOG_NAME = "server.log"
SERVER_LOG_MAX_BYTES = 5 * (1 << 20)
SERVER_LOG_BACKUPS = 3


def _setup_logging(debug: bool, cache_dir: str) -> None:
    """Настраивает логирование.

    MCP-клиенты показывают каждую строку stderr как [error], поэтому туда
    попадает только ERROR и выше. Операционный журнал всегда пишется в
    server.log в кэш-каталоге (ротация по размеру, журнал переживает
    рестарты) на уровне INFO; --debug поднимает уровень до DEBUG и
    включает подробности httpx. Бизнес-аудит ведётся отдельно в audit.log
    через mcp-baf-audit.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    root.addHandler(stderr_handler)

    if not debug:
        # httpx дублирует наши строки клиента — оставляем только WARNING.
        for noisy in ("httpx", "httpcore"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    log_dir = cache_dir or default_cache_dir("mcp-baf")
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, SERVER_LOG_NAME),
            maxBytes=SERVER_LOG_MAX_BYTES,
            backupCount=SERVER_LOG_BACKUPS,
            encoding="utf-8",
        )
    except OSError:
        return  # не удалось создать лог-файл — остаёмся на ERROR-only stderr
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(file_handler)


def main() -> None:
    args = parse_args()
    config = load_config(args)
    _setup_logging(config.debug, config.cache_dir)

    # Режим установки расширения.
    if args.install:
        from mcp_baf import installer

        print("Installing MCP extension into 1C database...")
        try:
            installer.install(
                db_path=args.install,
                server_mode=args.server,
                platform_exe=args.platform,
                db_user=args.db_user,
                db_password=args.db_password,
                platform_version=args.platform_version,
                lang=args.lang,
            )
        except installer.InstallError as exc:
            print(f"Installation error: {exc}", file=sys.stderr)
            sys.exit(1)
        print("Extension installed successfully.")
        return

    server = create_server(config)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
