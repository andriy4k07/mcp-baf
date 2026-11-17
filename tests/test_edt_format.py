"""EDT-формат (<project>/src/<Категория>/...): имена модулей, индекс, формы."""

import os

import pytest

from mcp_baf.dumpindex import DumpIndex, SearchParams, formparser
from mcp_baf.dumpindex.modulenames import bsl_path_to_module_name, resolve_module_name

EDT = os.path.join(os.path.dirname(__file__), "testdata", "edt")


@pytest.mark.parametrize("rel,expected", [
    ("src/CommonModules/Утиліти/Module.bsl", "ОбщийМодуль.Утиліти.Модуль"),
    ("src/Documents/Заказ/ObjectModule.bsl", "Документ.Заказ.МодульОбъекта"),
    ("src/Documents/Заказ/Forms/Ф/Module.bsl", "Документ.Заказ.Форма.Ф.МодульФормы"),
    ("Documents/Заказ/Forms/Ф/Module.bsl", "Документ.Заказ.Форма.Ф.МодульФормы"),
])
def test_edt_module_names(rel, expected):
    assert bsl_path_to_module_name(rel) == expected
    assert resolve_module_name(rel, {}) == expected


@pytest.mark.parametrize("root", [EDT, os.path.join(EDT, "src")])
def test_index_edt_project_root_and_src(root):
    idx = DumpIndex(root, use_cache=False)
    try:
        assert idx.wait_ready(30)
        assert idx.module_count() == 3
        matches, _ = idx.search(SearchParams(query="ПередЗаписью", mode="exact"))
        assert [m.module for m in matches] == ["Документ.Заказ.МодульОбъекта"]
    finally:
        idx.close()


@pytest.mark.parametrize("root", [EDT, os.path.join(EDT, "src")])
def test_edt_form_structure(root):
    files = formparser.find_form_files(root, "Document", "Заказ")
    assert list(files) == ["ФормаДокумента"]
    info = formparser.parse_form_xml(files["ФормаДокумента"])
    assert info.title == "Заказ"
    assert [(h.event, h.handler) for h in info.handlers] == [("OnOpen", "ПриОткрытии")]
    names = {e.name: e for e in info.elements}
    assert list(names) == ["Шапка", "Контрагент", "Товары", "ТоварыДобавить"]
    f = names["Контрагент"]
    assert (f.type, f.title, f.data_path) == ("InputField", "Покупець", "Объект.Контрагент")
    assert f.events[0].handler == "КонтрагентПриИзменении"
    assert names["Товары"].type == "Table"
    assert [(c.name, c.action) for c in info.commands] == [("Заполнить", "ЗаполнитьВыполнить")]
