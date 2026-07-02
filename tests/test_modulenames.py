"""Тесты преобразования путей dump в имена модулей.

Кейсы взяты из Go-версии (dump/index_test.go), чтобы гарантировать
идентичное поведение порта.
"""

import pytest

from mcp_baf.dumpindex.modulenames import (
    bsl_path_to_module_name,
    nfc,
    parse_module_name,
)


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


# ── NFC-нормализация (порт fix(dump) NFC из Go-версии) ──
# NFD-строки записаны escape-последовательностями (база + комбинируемый
# знак), чтобы точные байты пережили пересохранение файла редактором.


def test_nfc_composes_all_decomposable_letters():
    # Все четыре кириллические буквы 1С-идентификаторов, разложимые в NFD:
    # й, ё и их заглавные варианты.
    nfd = "\u0438\u0306 \u0435\u0308 \u0418\u0306 \u0415\u0308"
    assert nfc(nfd) == "\u0439 \u0451 \u0419 \u0401"


@pytest.mark.parametrize("s", ["", "ObjectModule", "Настройки", "Йогурт"])
def test_nfc_returns_nfc_input_unchanged(s):
    assert nfc(s) is s


def test_bsl_path_to_module_name_normalizes_nfd():
    # macOS хранит имена файлов в NFD — имя модуля должно выйти в NFC,
    # иначе оно не совпадёт с именами из запросов и HTTP-ответов 1С.
    nfd_object = "\u0418\u0306огурт"  # "Йогурт" в NFD
    got = bsl_path_to_module_name(f"Catalogs/{nfd_object}/Ext/ObjectModule.bsl")
    assert got == "Справочник.Йогурт.МодульОбъекта"
