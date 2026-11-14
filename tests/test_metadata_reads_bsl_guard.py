"""Статичні гарди контрактних фіксів B12 (дати, пагінація, статуси, навігація).

BSL у pytest не виконується, тому кожен фікс закріплюється читанням Module.bsl:
конкретні рядки/порядок гілок, а не «десь у модулі з'явився рядок».
"""

import re
from pathlib import Path

MODULE = (
    Path(__file__).parents[1]
    / "src/mcp_baf/extension_src/HTTPServices/MCPService/Ext/Module.bsl"
)


def source() -> str:
    return MODULE.read_text(encoding="utf-8-sig")


def body_of(source: str, name: str) -> str:
    match = re.search(r"Функция " + name + r"\(Запрос\)(.*?)КонецФункции", source, re.S)
    assert match, name
    return match.group(1)


def func_of(source: str, name: str) -> str:
    match = re.search(r"Функция " + name + r"\([^)]*\)(.*?)КонецФункции", source, re.S)
    assert match, name
    return match.group(1)


def test_query_dates_are_iso_not_locale():
    body = func_of(source(), "ПривестиЗначениеКJSON")
    assert 'ТипЗнч(Значение) = Тип("Дата")' in body
    assert "XMLСтрока(Значение)" in body
    # NULL → JSON null: клієнт відрізняє «нема значення» від порожнього рядка.
    assert 'Возврат ""' not in body
    # Строка(Дата) дає локалізоване ДД.ММ.РРРР і більше не є шляхом для дат.
    date_branch = body[body.index('Тип("Дата")'):body.index('Тип("Число")')]
    assert "XMLСтрока(" in date_branch
    assert "Возврат Строка(" not in date_branch


def test_query_dates_with_timezone_offset_are_converted():
    src = source()
    helper = func_of(src, "РазобратьСтрокуДатыISO")
    assert "СмещениеСекундИзХвоста(" in helper
    # Момент зі зміщенням переводиться в місцевий час сеансу, а не обрізається.
    assert "МестноеВремя(" in helper
    assert "ЧасовойПоясСеанса()" in helper
    conv = func_of(src, "ПреобразоватьЗначениеПараметра")
    assert "РазобратьСтрокуДатыISO(" in conv
    assert "Лев(Значение, 19)" not in conv
    # Некорректна дата — явна відмова (400), а не тиха підстановка рядка.
    assert "ВызватьИсключение" in conv
    offsets = func_of(src, "СмещениеСекундИзХвоста")
    assert '"Z"' in offsets
    assert "3600" in offsets
    # Журнал реєстрації приймає той самий набір форматів.
    assert "РазобратьСтрокуДатыISO(" in func_of(src, "РазобратьДатуОтбора")


def test_query_pagination_is_honest():
    body = body_of(source(), "ЗапросPOST")
    assert 'Результат.Вставить("count", Счетчик)' in body
    # total більше не дорівнює розміру сторінки.
    assert 'Результат.Вставить("total", Счетчик)' not in body
    guard = body.index("Если НЕ Усечено Тогда")
    total = body.index('Результат.Вставить("total", СмещениеЗапрошено - Смещение + Счетчик)')
    assert guard < total
    # offset больше числа строк: total = реально прочитанные, а не offset.
    assert 'СмещениеЗапрошено + Счетчик' not in body
    assert 'Если Смещение > 10000 Тогда' in body
    # Код у 4-й позиції: 3-й аргумент — reason, код у ньому дав би error_code=bad_request.
    assert 'ОтветОшибка(400, "offset: не более 10000", "", "offset_too_large")' in body


def test_navigation_mode_resolve_is_implemented():
    src = source()
    body = body_of(src, "НавигацияPOST")
    assert 'Параметры.mode = "resolve"' in body
    assert "РазобратьНавигационнуюСсылку(Параметры.link)" in body
    helper = func_of(src, "РазобратьНавигационнуюСсылку")
    assert "e1cib/data/" in helper
    assert '"ref"' in helper
    # Ім'я типу з розібраної ссылки потрапляє в текст запиту лише після
    # СсылкаИзGUID (там ПроверитьИмяМетаданных + білий список видів).
    assert body.index("СсылкаИзGUID(Вид, Идентификатор)") < body.index('" + Вид + " КАК Т')
    assert 'СсылкаИзGUID(Параметры.kind' not in body


def test_post_handlers_split_rights_and_internal_failures():
    src = source()
    for handler in ("НавигацияPOST", "СсылкиPOST", "ПраваМетаданныхPOST"):
        body = body_of(src, handler)
        assert 'ОтветОшибка(500' in body, handler
        assert '"internal"' in body, handler
    for handler in ("НавигацияPOST", "СсылкиPOST"):
        assert '"no_read_right"' in body_of(src, handler), handler
    query = body_of(src, "ЗапросPOST")
    assert '"query_error"' in query
    assert '"no_read_right"' in query
    assert "ЕстьПравоЧтения(" in src
    # Сирий ОписаниеОшибки() (внутрішні імена/рядки модуля) більше не віддається.
    assert "ОписаниеОшибки()" not in src


def test_form_reports_unavailable_structure():
    body = body_of(source(), "ФормаGET")
    assert 'Результат.Вставить("elements_available", ЭлементыДоступны)' in body
    assert 'Результат.Вставить("commands_available", КомандыДоступны)' in body
    assert 'Результат.Вставить("elements_reason", ПричинаЭлементов)' in body
    assert 'Результат.Вставить("commands_reason", ПричинаКоманд)' in body
    # Порожні Исключение більше не ковтають збій: ставиться прапорець.
    assert "ЭлементыДоступны = Ложь" in body
    assert "КомандыДоступны = Ложь" in body
    assert "Исключение\n    КонецПопытки" not in body


def test_configuration_mode_is_unknown_not_empty():
    body = body_of(source(), "КонфигурацияGET")
    assert 'РежимИБ = "unknown"' in body
    assert 'РежимИБ = ""' not in body


def test_eventlog_exclude_system_requires_boolean():
    body = body_of(source(), "ЖурналРегистрацииPOST")
    assert 'ТипЗнч(Параметры.exclude_system) <> Тип("Булево")' in body
    assert '"exclude_system: ожидается boolean"' in body


def call_args(source: str, start: int) -> list[str]:
    """Позиційні аргументи виклику, що починається з позиції start (після дужки)."""
    depth, i = 1, start
    while depth:
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
        i += 1
    args, current, depth, quoted = [], "", 0, False
    for char in source[start:i - 1]:
        if char == '"':
            quoted = not quoted
        if not quoted:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                args.append(current.strip())
                current = ""
                continue
        current += char
    args.append(current.strip())
    return args


def test_error_code_never_sits_in_reason_slot():
    # Контракт: ОтветОшибка(статус, текст, reason, error_code, request_id).
    # Машинний код у 3-й позиції потрапляє в reason, а error_code падає на дефолт
    # від статусу — саме так контракт і розходився з #100/#101.
    src = source()
    misplaced = []
    for match in re.finditer(r"ОтветОшибка\(", src):
        args = call_args(src, match.end())
        if len(args) == 3 and re.fullmatch(r'"[a-z0-9_]+"', args[2]):
            misplaced.append(src.count("\n", 0, match.start()) + 1)
    assert not misplaced, misplaced


def test_metadata_rights_admin_gate_has_error_code():
    body = body_of(source(), "ПраваМетаданныхPOST")
    assert 'ОтветОшибка(403, "Проверка другого пользователя/ролей требует административных прав", "", "admin_rights_required")' in body


def test_query_access_denied_matches_ua_ru_en_texts():
    body = body_of(source(), "ЗапросPOST")
    for text in ("Недостаточно прав", "Недостатньо прав", "Insufficient rights"):
        assert f'ВРег("{text}")' in body, text


def test_input_errors_are_400_before_internal_try():
    src = source()
    for handler in ("НавигацияPOST", "СсылкиPOST", "ПраваМетаданныхPOST"):
        body = body_of(src, handler)
        first_try = body.index("    Попытка\n")
        head = body[:first_try]
        assert "РазобратьТелоЗапроса(Запрос)" in head, handler
        assert 'ОтветОшибка(400' in head and '"invalid_argument"' in head, handler
    # Неизвестный тип метаданных (Неопределено из ЕстьПравоЧтения) — 400, а не крах.
    for handler in ("НавигацияPOST", "СсылкиPOST"):
        assert "Если ПраваЧтения = Неопределено" in body_of(src, handler), handler
