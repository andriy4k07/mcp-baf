"""Точка входа: mcp-baf --base <url> --user <user> --pass <password>."""

from __future__ import annotations

import logging
import os
import sys

from mcp_baf.config import load_config, parse_args
from mcp_baf.dumpindex.cache import user_cache_dir
from mcp_baf.server import create_server


def _setup_logging(debug: bool, cache_dir: str) -> None:
    """Настраивает логирование.

    MCP-клиенты показывают каждую строку stderr как [error], поэтому по
    умолчанию туда попадает только ERROR и выше. С --debug всё уходит в
    файл server.log в кэш-каталоге на уровне INFO.
    """
    if not debug:
        logging.basicConfig(stream=sys.stderr, level=logging.ERROR)
        return

    log_dir = cache_dir or os.path.join(user_cache_dir(), "mcp-baf")
    try:
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(log_dir, "server.log"),
            filemode="w",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    except OSError:
        # Не удалось создать лог-файл — остаёмся на ERROR-only stderr.
        logging.basicConfig(stream=sys.stderr, level=logging.ERROR)


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
