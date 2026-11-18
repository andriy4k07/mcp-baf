"""Схемы компоновки данных (СКД) как псевдо-модули индекса и поиск использований.

Template.xml отчётов/обработок/общих макетов с корнем DataCompositionSchema
превращается в текст из запросов наборов данных (<query>) и имён объектов
(<dataSetObject>); дальше он индексируется как обычный модуль типа
СхемаКомпоновкиДанных. Номера строк в результатах относятся к этому
извлечённому тексту, а не к исходному XML.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from mcp_baf.dumpindex.modulenames import METADATA_TYPES
from mcp_baf.dumpindex.xmlguard import UnsafeXML, parse_bytes

# Корень СКД должен встретиться в самом начале файла; остальные Template.xml
# (табличные документы, двоичные данные) отсекаются без разбора XML.
ROOT_PROBE = 4096
_ROOT_MARKER = b"<DataCompositionSchema"


def is_dcs_candidate(head: bytes) -> bool:
    return _ROOT_MARKER in head[:ROOT_PROBE]


def extract_dcs_text(data: bytes) -> str | None:
    """Текст запросов СКД или None, если файл — не схема / не разбирается."""
    if not is_dcs_candidate(data):
        return None
    try:
        root = parse_bytes(data.removeprefix(b"\xef\xbb\xbf"))
    except (UnsafeXML, ET.ParseError):
        return None
    out: list[str] = []
    for parent in root.iter():
        for child in parent:
            tag = child.tag.rpartition("}")[2]
            if tag not in ("query", "dataSetObject") or not (child.text or "").strip():
                continue
            name = parent.findtext("{*}name") or ""
            out.append(f"// {tag} {name}".rstrip())
            out.append(child.text.strip().replace("\r\n", "\n").replace("\r", "\n"))
    return "\n".join(out) if out else None


# Русские названия коллекций (мн.ч.) для типов из METADATA_TYPES.
_RU_PLURAL = {
    "Справочник": "Справочники", "Документ": "Документы", "Обработка": "Обработки",
    "Отчет": "Отчеты", "РегистрСведений": "РегистрыСведений",
    "РегистрНакопления": "РегистрыНакопления", "РегистрБухгалтерии": "РегистрыБухгалтерии",
    "РегистрРасчета": "РегистрыРасчета", "ПланСчетов": "ПланыСчетов",
    "ПланВидовХарактеристик": "ПланыВидовХарактеристик", "ПланВидовРасчета": "ПланыВидовРасчета",
    "ПланОбмена": "ПланыОбмена", "БизнесПроцесс": "БизнесПроцессы", "Задача": "Задачи",
    "Перечисление": "Перечисления", "Константа": "Константы",
}


def type_aliases(token: str) -> list[str]:
    """Все написания типа метаданных (ru/en, ед./мн.ч.), если token — одно из них."""
    low = token.lower()
    for en_one, en_many, ru_one in METADATA_TYPES:
        names = [en_one, en_many, ru_one, _RU_PLURAL[ru_one]]
        if low in (n.lower() for n in names):
            return names
    return []


def usage_pattern(query: str) -> tuple[re.Pattern[str], str]:
    """Regex ссылки `Тип.Имя` по всем написаниям типа и имя объекта для FTS-префильтра."""
    type_token, _, name = query.strip().partition(".")
    name = name.strip()
    aliases = type_aliases(type_token.strip())
    if not aliases or not re.fullmatch(r"\w+", name):
        raise ValueError(
            "query для mode=usages: Тип.Имя, например РегистрНакопления.ТоварыНаСкладах "
            "или AccumulationRegisters.ТоварыНаСкладах"
        )
    alt = "|".join(re.escape(a) for a in aliases)
    return re.compile(rf"(?<![\w.])(?:{alt})\s*\.\s*{re.escape(name)}(?!\w)", re.IGNORECASE), name
