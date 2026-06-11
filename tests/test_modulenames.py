"""Тесты преобразования путей dump в имена модулей.

Кейсы взяты из Go-версии (dump/index_test.go), чтобы гарантировать
идентичное поведение порта.
"""

import pytest

from mcp_baf.dumpindex.modulenames import bsl_path_to_module_name, parse_module_name


@pytest.mark.parametrize(
    ("path", "want"),
    [
        ("Catalogs/Номенклатура/Ext/ObjectModule.bsl", "Справочник.Номенклатура.МодульОбъекта"),
        ("Documents/Реализация/Ext/ObjectModule.bsl", "Документ.Реализация.МодульОбъекта"),
        ("DataProcessors/Обработка1/Ext/ObjectModule.bsl", "Обработка.Обработка1.МодульОбъекта"),
        ("Documents/Док/Forms/ФормаДок/Ext/Module.bsl", "Документ.Док.Форма.ФормаДок.МодульФормы"),
        # CommonModules: Module.bsl — это "Модуль", не "МодульФормы".
        ("CommonModules/ОбщийМодуль1/Ext/Module.bsl", "ОбщийМодуль.ОбщийМодуль1.Модуль"),
        # Расширения получают префикс ext.<имя>.
        (
            "Расширения/TestExt/CommonModules/CM1/Ext/Module.bsl",
            "ext.TestExt.ОбщийМодуль.CM1.Модуль",
        ),
        (
            "Расширения/TestExt/DataProcessors/DP1/Ext/ObjectModule.bsl",
            "ext.TestExt.Обработка.DP1.МодульОбъекта",
        ),
        # Common-типы без множественного Forms/Commands сегмента — плоские ключи.
        ("CommonForms/Форма1/Ext/Module.bsl", "ОбщаяФорма.Форма1.МодульФормы"),
        ("CommonCommands/Команда1/Ext/CommandModule.bsl", "ОбщаяКоманда.Команда1.МодульКоманды"),
        # Windows-разделители нормализуются.
        (r"Catalogs\Валюты\Ext\ManagerModule.bsl", "Справочник.Валюты.МодульМенеджера"),
    ],
)
def test_bsl_path_to_module_name(path, want):
    assert bsl_path_to_module_name(path) == want


def test_parse_module_name_form_path():
    parts = parse_module_name("Документ.Док.Форма.ФормаДок.МодульФормы")
    assert parts.category == "Документ"
    assert parts.name == "Док"
    assert parts.module == "МодульФормы"


def test_parse_module_name_simple():
    parts = parse_module_name("Справочник.Номенклатура.МодульОбъекта")
    assert parts == ("Справочник", "Номенклатура", "МодульОбъекта")
