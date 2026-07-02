"""Тесты индекса поиска по dump-выгрузке (SQLite FTS5)."""

import codecs

import pytest

from mcp_baf.dumpindex import DumpIndex, SearchParams

BUILD_TIMEOUT = 30


def mk_bsl(root, rel_path, content, bom=False):
    path = root / rel_path.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    if bom:
        data = codecs.BOM_UTF8 + data
    path.write_bytes(data)


@pytest.fixture
def index(tmp_path):
    mk_bsl(
        tmp_path,
        "Catalogs/Номенклатура/Ext/ObjectModule.bsl",
        "Процедура ПередЗаписью()\n"
        "    Позиция = СтрНайти(Наименование, \"тест\");\n"
        "КонецПроцедуры\n",
        bom=True,
    )
    mk_bsl(
        tmp_path,
        "Documents/Реализация/Ext/ObjectModule.bsl",
        "Процедура ОбработкаПроведения()\n"
        "    // проведение документа реализации\n"
        "    ДвиженияСформированы = Истина;\n"
        "КонецПроцедуры\n",
    )
    mk_bsl(
        tmp_path,
        "Catalogs/Номенклатура/Ext/ManagerModule.bsl",
        "Функция ПолучитьСписок() Экспорт\n"
        "    Возврат Новый Массив;\n"
        "КонецФункции\n",
    )
    idx = DumpIndex(str(tmp_path), use_cache=False)
    assert idx.wait_ready(BUILD_TIMEOUT), "index build timed out"
    yield idx
    idx.close()


def test_module_count(index):
    assert index.module_count() == 3


def test_smart_search(index):
    matches, total = index.search(SearchParams(query="проведение документа"))
    assert total >= 1
    assert matches[0].module == "Документ.Реализация.МодульОбъекта"
    assert matches[0].score > 0
    assert "проведение документа" in matches[0].context


def test_smart_synonym_english_finds_russian(index):
    # Поиск по английскому имени находит русские вхождения: StrFind -> СтрНайти.
    matches, total = index.search(SearchParams(query="StrFind"))
    assert total >= 1
    assert matches[0].module == "Справочник.Номенклатура.МодульОбъекта"
    assert "СтрНайти" in matches[0].context


def test_exact_search_case_insensitive(index):
    matches, total = index.search(SearchParams(query="стрнайти", mode="exact"))
    assert total == 1
    assert matches[0].line == 2


def test_regex_search(index):
    matches, total = index.search(
        SearchParams(query=r"Функция \w+\(\) Экспорт", mode="regex")
    )
    assert total == 1
    assert matches[0].module == "Справочник.Номенклатура.МодульМенеджера"


def test_regex_invalid(index):
    with pytest.raises(ValueError, match="invalid regex"):
        index.search(SearchParams(query="[unclosed", mode="regex"))


def test_category_filter(index):
    _, total = index.search(
        SearchParams(query="Процедура", mode="exact", category="Документ")
    )
    assert total == 1


def test_module_filter(index):
    matches, _ = index.search(
        SearchParams(query="Экспорт", mode="exact", module="МодульМенеджера")
    )
    assert len(matches) == 1
    assert "МодульМенеджера" in matches[0].module


def test_limit_and_total(index):
    # По одному заголовку Процедура/Функция в каждом из трёх модулей.
    matches, total = index.search(
        SearchParams(query="Процедура|Функция", mode="regex", limit=2)
    )
    assert len(matches) == 2
    assert total == 3


def test_empty_dir(tmp_path):
    idx = DumpIndex(str(tmp_path), use_cache=False)
    assert idx.wait_ready(BUILD_TIMEOUT)
    assert idx.module_count() == 0
    matches, total = idx.search(SearchParams(query="что-нибудь"))
    assert matches == [] and total == 0
    idx.close()


def test_bom_stripped(index):
    matches, _ = index.search(SearchParams(query="ПередЗаписью", mode="exact"))
    assert matches[0].line == 1
    assert matches[0].context.startswith("Процедура")


def test_nfd_dump_names_resolve_to_nfc(tmp_path):
    # macOS распаковывает выгрузку с NFD-именами (Й = И + комбинируемый знак).
    # Имена модулей и фильтры должны сходиться в NFC, иначе фильтр по
    # NFC-значению никогда не найдёт NFD-ключ из пути на диске.
    nfd_object = "И\u0306огурт"  # "Йогурт" в NFD
    mk_bsl(
        tmp_path,
        f"InformationRegisters/{nfd_object}/Ext/RecordSetModule.bsl",
        "Процедура ПередЗаписью(Отказ, Замещение)\nКонецПроцедуры\n",
    )
    idx = DumpIndex(str(tmp_path), use_cache=False)
    assert idx.wait_ready(BUILD_TIMEOUT)
    try:
        # Фильтры переданы в NFD (например, скопированы из macOS-выгрузки) —
        # search() нормализует аргументы так же, как ключи индекса.
        matches, total = idx.search(
            SearchParams(
                query="ПередЗаписью",
                mode="exact",
                category="РегистрСведении\u0306",   # "РегистрСведений" в NFD
                module="МодульНабораЗаписеи\u0306",  # "МодульНабораЗаписей" в NFD
            )
        )
        assert total == 1
        # Имя модуля в результате — NFC ("Йогурт" одним символом Й).
        assert matches[0].module == "РегистрСведений.Йогурт.МодульНабораЗаписей"
    finally:
        idx.close()
