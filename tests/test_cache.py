"""Тесты дискового кэша индекса и инкрементального обновления."""

import os
import sqlite3
import time

from mcp_baf.dumpindex import DumpIndex, SearchParams
from mcp_baf.dumpindex.cache import cache_path, index_db_path

BUILD_TIMEOUT = 30


def mk_bsl(root, rel_path, content):
    path = root / rel_path.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")


def rm_bsl(root, rel_path):
    # Зеркало mk_bsl: на POSIX бэкслеши — часть имени одного файла,
    # на Windows pathlib разбирает их как разделители.
    os.remove(root / rel_path.replace("/", "\\"))


def build(dump_dir, cache_dir, reindex=False):
    idx = DumpIndex(str(dump_dir), cache_dir=str(cache_dir), reindex=reindex)
    assert idx.wait_ready(BUILD_TIMEOUT), idx.build_error()
    assert idx.build_error() is None
    return idx


def test_cache_file_created(tmp_path):
    dump, cache = tmp_path / "dump", tmp_path / "cache"
    mk_bsl(dump, "Catalogs/Тест/Ext/ObjectModule.bsl", "Процедура А()\nКонецПроцедуры\n")
    idx = build(dump, cache)
    idx.close()
    assert os.path.exists(index_db_path(str(dump), str(cache)))


def test_cache_reused_and_search_works(tmp_path):
    dump, cache = tmp_path / "dump", tmp_path / "cache"
    mk_bsl(dump, "Catalogs/Тест/Ext/ObjectModule.bsl", "Процедура А()\nКонецПроцедуры\n")
    build(dump, cache).close()

    # Второй запуск открывает кэш (без полной пересборки).
    idx = build(dump, cache)
    matches, total = idx.search(SearchParams(query="Процедура", mode="exact"))
    assert total == 1
    assert matches[0].module == "Справочник.Тест.МодульОбъекта"
    idx.close()


def test_incremental_add_modify_delete(tmp_path):
    dump, cache = tmp_path / "dump", tmp_path / "cache"
    mk_bsl(dump, "Catalogs/Старый/Ext/ObjectModule.bsl", "СтароеСодержимое = 1;\n")
    mk_bsl(dump, "Catalogs/Меняется/Ext/ObjectModule.bsl", "ДоИзменения = 1;\n")
    build(dump, cache).close()

    # mtime-гранулярность: гарантируем отличие метки времени.
    time.sleep(0.01)

    rm_bsl(dump, "Catalogs/Старый/Ext/ObjectModule.bsl")
    mk_bsl(dump, "Catalogs/Меняется/Ext/ObjectModule.bsl", "ПослеИзменения = 2;\n")
    mk_bsl(dump, "Catalogs/Новый/Ext/ObjectModule.bsl", "НовоеСодержимое = 3;\n")

    idx = build(dump, cache)
    assert idx.module_count() == 2

    _, total = idx.search(SearchParams(query="СтароеСодержимое", mode="exact"))
    assert total == 0
    _, total = idx.search(SearchParams(query="ДоИзменения", mode="exact"))
    assert total == 0
    m, total = idx.search(SearchParams(query="ПослеИзменения", mode="exact"))
    assert total == 1
    m, total = idx.search(SearchParams(query="НовоеСодержимое", mode="exact"))
    assert total == 1
    assert m[0].module == "Справочник.Новый.МодульОбъекта"

    # smart-режим тоже видит изменения (FTS обновлён, не только docs).
    m, total = idx.search(SearchParams(query="НовоеСодержимое"))
    assert total == 1
    idx.close()


def test_reindex_discards_cache(tmp_path):
    dump, cache = tmp_path / "dump", tmp_path / "cache"
    mk_bsl(dump, "Catalogs/Тест/Ext/ObjectModule.bsl", "Процедура А()\nКонецПроцедуры\n")
    build(dump, cache).close()

    # Портим кэш: --reindex должен пересоздать его, а не упасть.
    db_path = index_db_path(str(dump), str(cache))
    with open(db_path, "wb") as f:
        f.write(b"garbage")

    idx = build(dump, cache, reindex=True)
    assert idx.module_count() == 1
    idx.close()


def test_corrupt_cache_rebuilt_automatically(tmp_path):
    dump, cache = tmp_path / "dump", tmp_path / "cache"
    mk_bsl(dump, "Catalogs/Тест/Ext/ObjectModule.bsl", "Процедура А()\nКонецПроцедуры\n")
    build(dump, cache).close()

    db_path = index_db_path(str(dump), str(cache))
    with open(db_path, "wb") as f:
        f.write(b"garbage")

    idx = build(dump, cache)  # без --reindex: кэш битый -> пересборка
    assert idx.module_count() == 1
    idx.close()


def test_schema_version_mismatch_rebuilt(tmp_path):
    dump, cache = tmp_path / "dump", tmp_path / "cache"
    mk_bsl(dump, "Catalogs/Тест/Ext/ObjectModule.bsl", "Процедура А()\nКонецПроцедуры\n")
    build(dump, cache).close()

    db_path = index_db_path(str(dump), str(cache))
    db = sqlite3.connect(db_path)
    with db:
        db.execute("UPDATE meta SET value = '999' WHERE key = 'schema_version'")
    db.close()  # незакрытое соединение держит файл (Windows)

    idx = build(dump, cache)
    assert idx.module_count() == 1
    idx.close()


def test_cache_path_distinct_per_dump_dir(tmp_path):
    a = cache_path(str(tmp_path / "a"), str(tmp_path / "c"))
    b = cache_path(str(tmp_path / "b"), str(tmp_path / "c"))
    assert a != b
