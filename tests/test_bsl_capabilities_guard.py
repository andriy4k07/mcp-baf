"""Статичний гард Module.bsl і карт доступів.

BSL у pytest не виконується, тому контракт перевіряється читанням вихідників
розширення: /capabilities, обробники, права, аудит відмови /capabilities.
"""

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from mcp_baf.access import TOOL_METHODS

ROOT = Path(__file__).parents[1]
EXTENSION = ROOT/'src/mcp_baf/extension_src'
MODULE = EXTENSION/'HTTPServices/MCPService/Ext/Module.bsl'
ACCESS = ROOT/'src/mcp_baf/access.py'
MD = {'m': 'http://v8.1c.ru/8.3/MDClasses'}


def module_text() -> str:
    return MODULE.read_text(encoding='utf-8-sig')


def body(name: str) -> str:
    """Тіло функції <name>(Запрос) без КонецФункции."""
    match = re.search(r'Функция ' + name + r'\(Запрос\)(.*?)КонецФункции', module_text(), re.S)
    assert match, f'нет обработчика {name}'
    return str(match.group(1))


def test_extensions_route_is_gone_and_capabilities_match_tools():
    # Выгрузка .cfe по HTTP удалена: маршрута, обработчика и права быть не должно.
    declared = dict(re.findall(r'Карта\.Вставить\("(\w+)", "([\w.-]+)"\)', body('ВозможностиGET')))
    assert set(declared.values()) == set(TOOL_METHODS.values())
    root = ET.parse(EXTENSION/'HTTPServices/MCPService.xml').getroot()
    assert 'Расширения' not in {t.find('m:Properties/m:Name', MD).text
                                for t in root.findall('.//m:URLTemplate', MD)}
    assert 'РасширенияGET' not in module_text()
    assert 'Расширения' not in (EXTENSION/'Roles/MCP_ОсновнаяРоль/Ext/Rights.xml').read_text(encoding='utf-8')
    assert 'Расширения' not in (EXTENSION/'ConfigDumpInfo.xml').read_text(encoding='utf-8')


def test_method_available_keeps_out_param_and_reason_order():
    match = re.search(r'Функция МетодДоступен\(([^)]*)\)(.*?)КонецФункции', module_text(), re.S)
    assert match
    assert 'ПричинаОтказа = ""' in match.group(1)  # значение по умолчанию — это не запись
    text = match.group(2)
    # Out-параметр нельзя обнулять на входе: причина отказа иначе теряется.
    assert not [line for line in text.splitlines() if line.strip() == 'ПричинаОтказа = "";']
    # Порядок этапов критичен: причина указывает, где именно отказ.
    codes = ['service_not_found', 'template_not_found', 'method_not_found', 'method_use_denied']
    positions = [text.index(f'ПричинаОтказа = "{code}"') for code in codes]
    assert positions == sorted(positions)
    assert text.index('Возврат Истина') > positions[-1]


def test_version_route_obeys_method_right_like_other_routes():
    assert 'МетодДоступен("Версия", "GET")' in body('ВерсияGET')
    assert 'ОтветОшибка(403, "Нет права использования метода")' in body('ВерсияGET')


def test_capabilities_denial_is_audited_without_secrets():
    source = ACCESS.read_text(encoding='utf-8')
    assert 'access.capabilities_unavailable' in source
    assert 'reason=type(exc).__name__' in source
    assert 'error=str(exc)[:300]' in source
    # Отказ логируется в ветке except, а не только меняет текст ошибки.
    denied = source[source.index('except Exception as exc:'):]
    assert denied.index('access.capabilities_unavailable') < denied.index('self._expires')
    assert 'password' not in denied[:denied.index('self._expires')]


def test_metadata_rights_accepts_english_and_russian_type_names():
    # /metadata-rights раньше требовал русское полное имя, а /object и /form —
    # английский тип; один и тот же объект давал 400 «не найден». Теперь тип
    # нормализуется общей картой, как у /object.
    text = body('ПраваМетаданныхPOST')
    assert 'КаноническийТипМетаданных(Части[0])' in text
    assert 'НайтиМетаданныеПоТипуИИмени(ТипОбъекта, Части[1])' in text
    assert 'НайтиПоПолномуИмени(П.metadata_object)' not in text
    # Типовые права и примечания сравнивают каноническое английское имя.
    assert 'ТипОбъекта = "Catalog" ИЛИ ТипОбъекта = "Document"' in text
    assert 'ТипОбъекта = "Document"' in text
    assert 'Части[0] = "Справочник"' not in text
    aliases = re.search(r'Функция КаноническийТипМетаданных\(ТипОбъекта\)(.*?)КонецФункции', module_text(), re.S)
    assert aliases
    pairs = dict(re.findall(r'Вставить\("([^"]+)",\s+"([^"]+)"\)', aliases.group(1)))
    assert len(pairs) >= 15
    # Псевдонимы не расходятся с картой коллекций: русский префикс ведёт к её ключу.
    shared = re.search(r'Функция НайтиМетаданныеПоТипуИИмени\(ТипОбъекта, ИмяОбъекта\)(.*?)КонецФункции', module_text(), re.S)
    assert shared
    collections = set(re.findall(r'Вставить\("(\w+)"', shared.group(1)))
    assert set(pairs.values()) <= collections
    assert {'Справочник', 'Документ', 'РегистрСведений'} <= set(pairs)


def test_eventlog_requires_admin_right_explicitly():
    # Роль даёт только Use на метод; права на данные у неё нет. Чтение журнала
    # требует администрирования, поэтому гейт стоит до выгрузки и даёт 403.
    text = body('ЖурналРегистрацииPOST')
    gate = 'ПравоДоступа("Администрирование", Метаданные)'
    assert gate in text
    assert text.index(gate) < text.index('ВыгрузитьЖурналРегистрации(')
    assert 'eventlog_access_denied' in text[text.index(gate):]
    assert 'ОтветОшибка(403, "Чтение журнала регистрации требует административных прав"' in text
