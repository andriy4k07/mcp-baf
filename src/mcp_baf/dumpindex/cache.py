"""Расположение дискового кэша индекса (порт dump/cache.go).

Кэш каждой dump-выгрузки живёт в каталоге, имя которого — первые 16
hex-символов sha256 от абсолютного пути выгрузки:

    Windows: %LocalAppData%/mcp-baf/<hash>/
    Linux:   ~/.cache/mcp-baf/<hash>/  (или $XDG_CACHE_HOME)
    macOS:   ~/Library/Caches/mcp-baf/<hash>/
"""

from __future__ import annotations

import hashlib
import os
import sys

INDEX_DB_NAME = "index.db"


def user_cache_dir() -> str:
    """Платформенный каталог кэша пользователя (аналог os.UserCacheDir в Go)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return base
        return os.path.expanduser(r"~\AppData\Local")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Caches")
    return os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")


def cache_path(dump_dir: str, cache_dir: str = "") -> str:
    """Каталог кэша индекса для данной dump-выгрузки."""
    abs_dir = os.path.abspath(dump_dir)
    digest = hashlib.sha256(abs_dir.encode("utf-8")).hexdigest()[:16]
    base = cache_dir or os.path.join(user_cache_dir(), "mcp-baf")
    return os.path.join(base, digest)


def index_db_path(dump_dir: str, cache_dir: str = "") -> str:
    return os.path.join(cache_path(dump_dir, cache_dir), INDEX_DB_NAME)
