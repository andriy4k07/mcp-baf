"""Разбор Form.xml из dump-выгрузки конфигурации (порт dump/formparser.go).

Dump использует схему xcf/logform:

    <Form xmlns="http://v8.1c.ru/8.3/xcf/logform" ...>
      <Title><v8:item><v8:lang>ru</v8:lang><v8:content>...</v8:content></v8:item></Title>
      <Events><Event name="OnOpen">ПриОткрытии</Event></Events>
      <ChildItems>
        <InputField name="Поле1">
          <DataPath>Объект.Поле1</DataPath>
          <Events><Event name="OnChange">Поле1ПриИзменении</Event></Events>
        </InputField>
        <UsualGroup name="Группа"><ChildItems>...рекурсивно...</ChildItems></UsualGroup>
      </ChildItems>
      <Commands><Command name="Сохранить"><Action>СохранитьВыполнить</Action></Command></Commands>
    </Form>

Особенности:
- имя элемента берётся из атрибута name, а не из дочернего <Name>;
- <ChildItems> рекурсивны — элементы любой глубины разворачиваются в плоский список;
- события формы (<Events> верхнего уровня) попадают в handlers, события
  элементов — в events соответствующего элемента, без дублирования.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from mcp_baf.dumpindex.extroots import discover_extension_roots
from mcp_baf.dumpindex.modulenames import OBJECT_TYPE_TO_DUMP_DIR, nfc
from mcp_baf.dumpindex.xmlguard import UnsafeXML, parse_bytes, parse_file


@dataclass
class FormHandlerInfo:
    event: str
    handler: str


@dataclass
class FormElementInfo:
    name: str
    type: str  # имя XML-тега (InputField, Table, ...)
    title: str = ""
    data_path: str = ""
    events: list[FormHandlerInfo] = field(default_factory=list)


@dataclass
class FormCommandInfo:
    name: str
    action: str


@dataclass
class FormInfo:
    name: str = ""
    title: str = ""
    elements: list[FormElementInfo] = field(default_factory=list)
    commands: list[FormCommandInfo] = field(default_factory=list)
    handlers: list[FormHandlerInfo] = field(default_factory=list)


# XML-теги, которые считаются значимыми элементами формы.
FORM_ELEMENT_TAGS = frozenset({
    "InputField", "LabelField", "CheckBoxField", "RadioButtonField",
    "NumberField", "TextDocumentField", "SpreadsheetDocumentField",
    "PictureField", "Table", "FormattedDocumentField", "PlannerField",
    "DendrogramField", "ChartField", "GanttChartField", "PeriodField",
    "ProgressBarField", "TrackBarField", "CalendarField", "HTMLDocumentField",
    "Button", "UsualGroup", "Pages", "Page", "CommandBar", "Popup",
    "ColumnGroup", "LabelDecoration", "PictureDecoration", "Hyperlink",
    "Addition", "ButtonGroup",
})

# Служебные теги-декорации, которые никогда не попадают в список элементов.
SERVICE_ELEMENT_TAGS = frozenset({
    "ContextMenu", "ExtendedTooltip", "ShortTooltip",
    "SearchStringAddition", "ViewStatusAddition", "SearchControlAddition",
})

# «Прозрачные» контейнеры: сама обёртка не интересна, но её вложенные
# ChildItems содержат настоящие элементы (кнопки командной панели).
TRANSPARENT_CONTAINER_TAGS = frozenset({"AutoCommandBar"})

# XML-тип элемента -> русское отображаемое имя.
ELEMENT_TYPE_DISPLAY_NAME = {
    "InputField": "ПолеВвода",
    "LabelField": "ПолеНадписи",
    "CheckBoxField": "ФлажокПоле",
    "RadioButtonField": "ПолеПереключателя",
    "NumberField": "ПолеЧисла",
    "TextDocumentField": "ПолеТекстовогоДокумента",
    "SpreadsheetDocumentField": "ПолеТабличногоДокумента",
    "PictureField": "ПолеКартинки",
    "Table": "ТаблицаФормы",
    "Button": "Кнопка",
    "ButtonGroup": "ГруппаКнопок",
    "UsualGroup": "ОбычнаяГруппа",
    "Pages": "Страницы",
    "Page": "Страница",
    "CommandBar": "КоманднаяПанель",
    "LabelDecoration": "ДекорацияНадпись",
    "PictureDecoration": "ДекорацияКартинка",
    "Hyperlink": "Гиперссылка",
}


def display_type(element_type: str) -> str:
    """Русское имя типа элемента, либо исходный тег если он неизвестен."""
    return ELEMENT_TYPE_DISPLAY_NAME.get(element_type, element_type)


def _forms_in(base: str, dir_name: str, object_name: str, common: bool) -> dict[str, str]:
    """Формы объекта в одном корне выгрузки: Designer, EDT, EDT с src/ внутри base."""
    root = os.path.realpath(base) + os.sep
    result: dict[str, str] = {}
    for prefix in ("", "src"):
        obj_dir = os.path.join(base, prefix, dir_name, object_name)
        # Общая форма — сама объект: <CommonForms>/<Имя>/Form.form, без каталога Forms.
        forms_dir = obj_dir if common else os.path.join(obj_dir, "Forms")
        if os.path.isdir(forms_dir):
            break
    else:
        return result
    entries = [""] if common else os.listdir(forms_dir)
    for entry in entries:
        form_dir = os.path.join(forms_dir, entry)
        form_xml = os.path.join(form_dir, "Ext", "Form.xml")
        if not os.path.isfile(form_xml):
            form_xml = os.path.join(form_dir, "Form.form")  # EDT
        # Симлинки наружу корня выгрузки не читаем.
        if os.path.isfile(form_xml) and os.path.realpath(form_xml).startswith(root):
            # Ключ — NFC-имя формы (macOS отдаёт listdir в NFD, а form_name
            # из запроса приходит в NFC); путь хранит сырое имя с диска.
            key = nfc(entry or object_name)
            if key in result and result[key] != form_xml:
                # Два разных файла с диска сошлись в одно NFC-имя: отдать
                # один «первому попавшемуся» значит молча показать чужую
                # форму — отвергаем оба как неоднозначные.
                raise ValueError(
                    f"ambiguous form names for {object_name!r}: "
                    f"{result[key]!r} and {form_xml!r} normalize to {key!r}"
                )
            result[key] = form_xml
    return result


def find_form_files(
    dump_dir: str, object_type: str, object_name: str
) -> dict[str, str]:
    """Находит все формы объекта (Form.xml / Form.form) в dump-выгрузке.

    Возвращает словарь имя формы -> абсолютный путь к файлу.
    Пустой словарь — у объекта нет директории Forms (это не ошибка).
    Формы вложенных проектов (расширения, EDT-проекты в обёртке) получают
    ключ ``ext.<имя>.<форма>`` как у модулей; основная EDT-конфигурация
    в обёртке — без префикса. Формы корня --dump приоритетнее вложенных.
    ``CommonForm``: object_name — имя общей формы, ключ — то же имя.
    """
    common = object_type == "CommonForm"
    dir_name = "CommonForms" if common else OBJECT_TYPE_TO_DUMP_DIR.get(object_type)
    if dir_name is None:
        raise ValueError(f"unknown object type {object_type!r} for dump lookup")

    if ".." in object_name or "/" in object_name or "\\" in object_name:
        raise ValueError(
            f"invalid object name {object_name!r}: contains path traversal characters"
        )

    result = _forms_in(dump_dir, dir_name, object_name, common)
    # shortcut: вложенные проекты ищутся каждый вызов (манифесты читаются заново,
    # бюджет extroots ограничивает стоимость); кэшировать, если станет медленно.
    for rel, ext_name in discover_extension_roots(dump_dir).items():
        prefix = f"ext.{ext_name}." if ext_name else ""
        for form, path in _forms_in(os.path.join(dump_dir, rel), dir_name, object_name, common).items():
            result.setdefault(prefix + form, path)
    return result


def parse_form_xml(path: str) -> FormInfo:
    """Разбирает Form.xml (Designer) или Form.form (EDT): элементы, команды, обработчики."""
    root = parse_file(path)
    if path.endswith(".form"):
        return _parse_edt_form(root)
    return _parse_form_root(root)


# Типы элементов EDT (xsi:type) без собственного <type>: сам xsi:type и есть тип.
_EDT_XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"


def _edt_text(elem: ET.Element, tag: str) -> str:
    for c in elem:
        if _local(c) == tag:
            return (c.text or "").strip()
    return ""


def _edt_title(elem: ET.Element) -> str:
    # <title><key>ru</key><value>Текст</value></title>
    for c in elem:
        if _local(c) == "title":
            return _edt_text(c, "value")
    return ""


def _edt_handlers(elem: ET.Element) -> list[FormHandlerInfo]:
    return [
        FormHandlerInfo(event=_edt_text(c, "event"), handler=_edt_text(c, "name"))
        for c in elem
        if _local(c) == "handlers" and _edt_text(c, "event") and _edt_text(c, "name")
    ]


def _edt_items(container: ET.Element) -> list[FormElementInfo]:
    """Плоский список элементов EDT-формы: <items> рекурсивно, включая autoCommandBar."""
    out: list[FormElementInfo] = []
    for c in container:
        local = _local(c)
        if local == "autoCommandBar":
            out.extend(_edt_items(c))
        elif local == "items":
            xsi = (c.get(_EDT_XSI) or "").rsplit(":", 1)[-1].removeprefix("Form")
            kind = _edt_text(c, "type") or xsi
            dp = ""
            for d in c:
                if _local(d) == "dataPath":
                    dp = _edt_text(d, "segments")
            out.append(FormElementInfo(
                name=_edt_text(c, "name"), type=kind,
                title=_edt_title(c), data_path=dp, events=_edt_handlers(c),
            ))
            out.extend(_edt_items(c))
    return out


def _parse_edt_form(root: ET.Element) -> FormInfo:
    """Минимальный разбор EDT Form.form (формат g5.1c.ru/v8/dt/form).

    shortcut: проверено только на синтетической форме по схеме EDT, не на
    реальном дампе; незнакомые теги игнорируются.
    """
    form = FormInfo(title=_edt_title(root), handlers=_edt_handlers(root))
    try:
        form.elements = _edt_items(root)
    except RecursionError:
        raise UnsafeXML("форма слишком глубоко вложена, разбор не поддерживается") from None
    for c in root:
        if _local(c) == "formCommands":
            action = ""
            for a in c:
                if _local(a) == "action":
                    action = next(
                        (_edt_text(h, "name") for h in a if _local(h) == "handler"), "")
            form.commands.append(FormCommandInfo(name=_edt_text(c, "name"), action=action))
    return form


def parse_form_xml_data(data: bytes | str) -> FormInfo:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return _parse_form_root(parse_bytes(data))


def _local(elem: ET.Element) -> str:
    """Локальное имя тега без namespace ({ns}Tag -> Tag)."""
    tag = elem.tag
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_form_root(root: ET.Element) -> FormInfo:
    try:
        return _parse_form_root_unbounded(root)
    except RecursionError:
        # Патологически вложенная форма: рекурсивный разбор не безопасен.
        raise UnsafeXML("форма слишком глубоко вложена, разбор не поддерживается") from None


def _parse_form_root_unbounded(root: ET.Element) -> FormInfo:
    form = FormInfo()
    if _local(root) != "Form":
        # Корень не <Form> — ищем первый <Form> в документе.
        for elem in root.iter():
            if _local(elem) == "Form":
                root = elem
                break
        else:
            return form

    for child in root:
        local = _local(child)
        if local == "Title":
            form.title = _read_localized(child)
        elif local == "Events":
            form.handlers = _parse_events(child)
        elif local == "ChildItems":
            form.elements.extend(_parse_child_items(child))
        elif local == "Commands":
            form.commands = _parse_commands(child)
        elif local in FORM_ELEMENT_TAGS:
            # UI-элемент прямо под <Form> без обёртки <ChildItems> (редкость).
            form.elements.extend(_parse_element(child))

    return form


def _parse_child_items(container: ET.Element) -> list[FormElementInfo]:
    """Разворачивает <ChildItems> в плоский список элементов (рекурсивно)."""
    elements: list[FormElementInfo] = []
    for child in container:
        local = _local(child)
        if local in SERVICE_ELEMENT_TAGS:
            continue
        if local in TRANSPARENT_CONTAINER_TAGS:
            elements.extend(_descend_into_child_items(child))
        elif local in FORM_ELEMENT_TAGS:
            elements.extend(_parse_element(child))
        # Неизвестные теги пропускаются без записи.
    return elements


def _descend_into_child_items(container: ET.Element) -> list[FormElementInfo]:
    """Возвращает элементы из <ChildItems> прозрачного контейнера,
    не записывая сам контейнер."""
    elements: list[FormElementInfo] = []
    for child in container:
        if _local(child) == "ChildItems":
            elements.extend(_parse_child_items(child))
    return elements


def _parse_element(elem: ET.Element) -> list[FormElementInfo]:
    """Разбирает один элемент формы; возвращает его и вложенные элементы."""
    info = FormElementInfo(name=elem.get("name", ""), type=_local(elem))
    nested: list[FormElementInfo] = []

    for child in elem:
        local = _local(child)
        if local == "Title":
            info.title = _read_localized(child)
        elif local == "DataPath":
            info.data_path = (child.text or "").strip()
        elif local == "Events":
            # События уровня элемента принадлежат только ему; вложенные
            # ChildItems сохранят свои события у собственных элементов.
            info.events = _parse_events(child)
        elif local == "ChildItems":
            nested.extend(_parse_child_items(child))
        elif local in TRANSPARENT_CONTAINER_TAGS:
            # Например, Table с <AutoCommandBar><ChildItems>...</ChildItems>
            # — кнопки панели всплывают в плоский список.
            nested.extend(_descend_into_child_items(child))

    return [info, *nested]


def _parse_commands(container: ET.Element) -> list[FormCommandInfo]:
    commands = []
    for child in container:
        if _local(child) != "Command":
            continue
        name = child.get("name", "")
        if not name:
            continue
        action = ""
        for sub in child:
            if _local(sub) == "Action":
                action = (sub.text or "").strip()
        commands.append(FormCommandInfo(name=name, action=action))
    return commands


def _parse_events(container: ET.Element) -> list[FormHandlerInfo]:
    handlers = []
    for child in container:
        if _local(child) != "Event":
            continue
        event = child.get("name", "")
        handler = (child.text or "").strip()
        if event and handler:
            handlers.append(FormHandlerInfo(event=event, handler=handler))
    return handlers


def _read_localized(elem: ET.Element) -> str:
    """Читает локализованную строку 1С (v8:LocalStringType).

    Возвращает первый непустой вариант: прямой текст элемента либо
    <v8:item><v8:content> (обычно русский текст).
    """
    text = (elem.text or "").strip()
    if text:
        return text
    for child in elem:
        if _local(child) != "item":
            continue
        for sub in child:
            if _local(sub) == "content":
                content = (sub.text or "").strip()
                if content:
                    return content
    return ""
