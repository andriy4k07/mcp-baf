"""Тесты обратных зависимостей (mode=usages) и индексации СКД."""

import pytest

from mcp_baf.dumpindex import DumpIndex, SearchParams, Usage
from mcp_baf.tools.search_code import format_usages

BUILD_TIMEOUT = 30

_DCS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema">\n'
    "<dataSet><name>Набор1</name><query>ВЫБРАТЬ * ИЗ\n"
    "  РегистрНакопления.ТоварыНаСкладах.Остатки КАК Т</query></dataSet>\n"
    "</DataCompositionSchema>\n"
)


def _mk(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def idx(tmp_path):
    _mk(tmp_path, "Documents/Д1/Ext/ObjectModule.bsl",
        "Процедура П()\n  Р = РегистрыНакопления.ТоварыНаСкладах.СоздатьНаборЗаписей();\n"
        "  З = \"ВЫБРАТЬ ИЗ РегистрНакопления.ТоварыНаСкладах\";\n"
        "  Д = РегистрыНакопления.ТоварыНаСкладахДоп;\nКонецПроцедуры\n")
    _mk(tmp_path, "CommonModules/М/Ext/Module.bsl",
        "// AccumulationRegisters.ТоварыНаСкладах\nx = ТоварыНаСкладах;\n")
    _mk(tmp_path, "Reports/О/Templates/Схема/Ext/Template.xml", _DCS)
    _mk(tmp_path, "CommonTemplates/Общ/Ext/Template.xml", _DCS)
    # Не СКД: макет таблицы с тем же текстом не индексируется.
    _mk(tmp_path, "Reports/О/Templates/Таблица/Ext/Template.xml",
        '<?xml version="1.0"?><document>РегистрНакопления.ТоварыНаСкладах</document>')
    index = DumpIndex(str(tmp_path), use_cache=False)
    assert index.wait_ready(BUILD_TIMEOUT)
    yield index
    index.close()


def test_usages_ru_en_and_dcs(idx):
    for q in ("РегистрНакопления.ТоварыНаСкладах", "AccumulationRegister.ТоварыНаСкладах",
              "accumulationregisters.ТоварыНаСкладах"):
        found, modules, hits = idx.find_usages(q)
        got = {u.module: u.lines for u in found}
        assert got["Документ.Д1.МодульОбъекта"] == [2, 3]  # ТоварыНаСкладахДоп не считается
        assert got["ОбщийМодуль.М.Модуль"] == [1]
        assert got["Отчет.О.Макет.Схема.СхемаКомпоновкиДанных"] == [3]  # строка 1 — заголовок набора
        assert got["ОбщийМакет.Общ.СхемаКомпоновкиДанных"] == [3]
        assert (modules, hits) == (4, 5)  # макет таблицы не проиндексирован


def test_usages_filter_and_limit(idx):
    found, _, _ = idx.find_usages(
        "РегистрНакопления.ТоварыНаСкладах", module="СхемаКомпоновкиДанных")
    assert {u.module.split(".")[0] for u in found} == {"Отчет", "ОбщийМакет"}
    found, modules, _ = idx.find_usages("РегистрНакопления.ТоварыНаСкладах", limit=1)
    assert len(found) == 1 and modules == 4 and found[0].lines == [2, 3]  # больше ссылок — первым


def test_usages_bad_query(idx):
    with pytest.raises(ValueError):
        idx.find_usages("ТоварыНаСкладах")


def test_dcs_text_searchable_by_smart(idx):
    _, total = idx.search(SearchParams(query="Остатки", module="СхемаКомпоновкиДанных"))
    assert total == 2


def test_format_usages_truncation():
    out = format_usages([Usage("Документ.Д.МодульОбъекта", list(range(1, 13)))], 3, 12, "Q.X")
    assert "12 (строки 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 и ещё 2)" in out
    assert "Показано 1 из 3 модулей" in out
