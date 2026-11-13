"""Статические гарды изменений Module.bsl (без запуска 1С)."""

import re
from pathlib import Path

MODULE = (
    Path(__file__).parents[1]
    / "src/mcp_baf/extension_src/HTTPServices/MCPService/Ext/Module.bsl"
)


def body_of(source: str, name: str) -> str:
    match = re.search(r"Функция " + name + r"\(Запрос\)(.*?)КонецФункции", source, re.S)
    assert match, name
    return match.group(1)


def test_query_handler_supports_offset_pagination():
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ЗапросPOST")
    assert 'Параметры.Свойство("offset")' in body
    assert 'Результат.Вставить("offset", СмещениеЗапрошено)' in body
    # Пропуск строк страницы выполняется до проверки лимита: иначе offset
    # съедал бы строки самой страницы и она приходила бы короче limit.
    skip = body.index("Если Смещение > 0 Тогда")
    limit = body.index("Если Счетчик >= Лимит Тогда")
    assert skip < limit
    assert "Смещение = Смещение - 1;" in body[skip:limit]


def test_event_log_total_is_returned_count_and_found_is_separate():
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ЖурналРегистрацииPOST")
    assert 'Результат.Вставить("total",  МассивСобытий.Количество());' in body
    assert 'Результат.Вставить("found",  ВсегоЗаписей);' in body
    # total больше не подменяется количеством найденных записей.
    assert 'Результат.Вставить("total",  ВсегоЗаписей);' not in body
    # Неполнота списка считается и по лимиту, и по окну выгрузки.
    assert 'ВсегоЗаписей > МассивСобытий.Количество()' in body
    assert 'ВсегоЗаписей >= КапВыгрузки' in body


def function_body(source: str, signature: str) -> str:
    """Тело функции по точной сигнатуре (для хелперов без параметра Запрос)."""
    match = re.search(re.escape(signature) + r"(.*?)КонецФункции", source, re.S)
    assert match, signature
    return match.group(1)


def test_constant_type_is_mapped_in_metadata_lookup():
    # Constant есть в METADATA_TYPES Python: без строки в BSL-мапе
    # /object/Constant/<Имя> отвечает 404 на существующую константу.
    source = MODULE.read_text(encoding="utf-8-sig")
    body = function_body(source, "Функция НайтиМетаданныеПоТипуИИмени(ТипОбъекта, ИмяОбъекта)")
    assert 'Соответствие.Вставить("Constant",' in body
    assert "Метаданные.Константы" in body


def test_constant_object_returns_its_type():
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ОбъектGET")
    assert "Метаданные.Константы.Найти(ОбъектМД.Имя) = ОбъектМД" in body
    assert "ДобавитьОписаниеТипа(Результат, ОбъектМД.Тип)" in body


def test_object_attributes_carry_structured_type_description():
    # Строка(Тип) теряет имена объектов и длину/точность: рядом обязательны
    # type_names (полные имена), length и precision.
    source = MODULE.read_text(encoding="utf-8-sig")
    helper = function_body(source, "Процедура ДобавитьОписаниеТипа(Описание, ТипОписания)")
    assert 'Описание.Вставить("type_names", ИменаТипов);' in helper
    assert "Метаданные.НайтиПоТипу(Тип)" in helper and ".ПолноеИмя()" in helper
    assert 'Описание.Вставить("length", ТипОписания.ДлинаСтроки);' in helper
    assert 'Описание.Вставить("precision", ТипОписания.Точность);' in helper
    body = body_of(source, "ОбъектGET")
    # Реквизиты шапки, реквизиты ТЧ, измерения и ресурсы — все четыре места.
    assert body.count("ДобавитьОписаниеТипа(") == 5  # + тип константы
    assert "Строка(Реквизит.Тип)" not in body
    assert "Строка(Измерение.Тип)" not in body
    assert "Строка(Ресурс.Тип)" not in body


def test_select_guard_is_shared_and_strips_leading_comments():
    # Python-гард (query_keyword) срезает комментарии перед запросом; BSL обязан
    # вести себя так же, иначе такой запрос проходит клиент и падает в 1С.
    source = MODULE.read_text(encoding="utf-8-sig")
    guard = function_body(source, "Функция ЭтоВыборка(ТекстЗапроса)")
    assert 'Пара = "//"' in guard and 'Пара = "/*"' in guard
    # Комментарии пропускаются и посреди запроса, слово — по символам (как регекс Python).
    assert "ВРег(Символ) <> НРег(Символ)" in guard
    assert 'ВРег(ПервоеСлово) = "ВЫБРАТЬ" ИЛИ ВРег(ПервоеСлово) = "SELECT"' in guard
    # Оба хендлера используют один гард; старый префиксный чек ушёл.
    assert "НЕ ЭтоВыборка(ТекстЗапроса)" in body_of(source, "ЗапросPOST")
    validate = body_of(source, "ПроверкаЗапросаPOST")
    assert "НЕ ЭтоВыборка(ТекстЗапроса)" in validate
    assert 'Ошибки.Добавить("not_select");' in validate
    assert "Лев(Префикс, 7)" not in source


def test_eventlog_noise_filter_window_is_not_narrowed_by_level():
    # При заданном Уровне окно выгрузки раньше сужалось до Лимит, и фильтр шума
    # мог отбросить все записи → пустой список при живом журнале.
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ЖурналРегистрацииPOST")
    assert 'И НЕ Отбор.Свойство("Уровень")' not in body
    assert "Если ИсключатьСистемные Тогда" in body
    assert "КапВыгрузки = Мин(Лимит * 20, 10000);" in body
    # Добор: повторная выгрузка с расширенным окном вместо пустого ответа.
    assert "МассивСобытий.Очистить();" in body
    assert "КапВыгрузки = Мин(КапВыгрузки * 4, 10000);" in body
    assert 'Результат.Вставить("filtered_empty"' in body


def test_eventlog_unknown_level_is_rejected():
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ЖурналРегистрацииPOST")
    assert "Если Уровень = Неопределено Тогда" in body
    assert 'ОтветОшибка(400, "level: Ошибка, Предупреждение, Информация, Примечание")' in body


def test_form_handler_honors_form_query_param():
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ФормаGET")
    # ПараметрыЗапроса — ФиксированноеСоответствие, Свойство() на живой базе падает.
    assert 'ПараметрыЗапроса.Получить("form")' in body
    assert "ПараметрыЗапроса.Свойство" not in body
    assert "НайтиФормуОбъекта(ОбъектМД, ИмяФормы)" in body
    assert 'ОтветОшибка(404, "Form not found")' in body


def test_metadata_handler_supports_filter_param():
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "МетаданныеGET")
    assert 'ПараметрыЗапроса.Получить("filter")' in body
    assert "ПараметрыЗапроса.Свойство" not in body
    assert "КоллекцииКВыгрузке" in body
    assert 'ОтветОшибка(400, "filter: неизвестная коллекция метаданных: " + Фильтр)' in body


def test_references_use_one_query_per_table_instead_of_per_field():
    # N+1: запрос выполнялся на каждый реквизит каждого объекта метаданных.
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "СсылкиPOST")
    assert "Для Каждого К Из Кандидаты Цикл" not in body
    assert "ГруппыТаблиц" in body
    assert 'Выборка["ПолеСовпадения"]' in body
    assert '" ИЛИ "' in body
    # Один ВЫБОР с несколькими КОГДА: "ВЫБОР" внутри цикла ломал запрос на 2+ полях.
    assert 'Маркеры = "ВЫБОР";' in body
    assert 'Маркеры + " КОГДА Т."' in body
    assert '"ВЫБОР КОГДА' not in body
    # Запрос остаётся под правами и RLS и привязан к цели.
    assert 'ВЫБРАТЬ РАЗРЕШЕННЫЕ РАЗЛИЧНЫЕ ПЕРВЫЕ ' in body
    assert 'УстановитьПараметр("Цель", Цель)' in body
def test_query_handlers_parse_body_inside_try():
    # Невалидный JSON и отсутствие query — ошибка входа (400), а не платформенный
    # 500: разбор тела и доступ к полю обязаны стоять внутри Попытка.
    source = MODULE.read_text(encoding="utf-8-sig")
    for name in ("ЗапросPOST", "ПроверкаЗапросаPOST"):
        body = body_of(source, name)
        parse = body.index('Параметры = РазобратьJSON(Запрос.ПолучитьТелоКакСтроку());')
        assert body.index("Попытка") < parse
        assert body.index("Исключение", parse) > parse
        assert body.index("КонецПопытки", parse) > parse
        assert 'ОтветОшибка(400, "invalid JSON body", "", "invalid_json")' in body
        assert 'Параметры.Свойство("query")' in body
        assert 'ОтветОшибка(400, "query is required", "", "missing_query")' in body
        # null/массив в теле не должен доходить до Параметры.query.
        assert 'ТипЗнч(Параметры) <> Тип("Структура")' in body


def test_eventlog_export_is_wrapped_in_try():
    # Отказ прав на администрирование данных или недоступный журнал — 500 с
    # устойчивым кодом, а не неперехваченный платформенный текст.
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ЖурналРегистрацииPOST")
    call = body.index("ВыгрузитьЖурналРегистрации(")
    assert body.rindex("Попытка", 0, call) > body.index("Параметры.Свойство(\"user\")")
    exception = body.index("Исключение", call)
    assert body.index("КонецПопытки", call) > exception
    assert 'Возврат ОтветОшибка(500' in body[call:]
    assert '"eventlog_unavailable"' in body[call:]
    # Полный текст платформы уходит в журнал регистрации, не клиенту.
    assert 'ЗаписатьОшибкуВЖурнал("eventlog_unavailable"' in body[call:]


def test_error_response_carries_stable_code_and_request_id():
    source = MODULE.read_text(encoding="utf-8-sig")
    match = re.search(r"Функция ОтветОшибка\(.*?КонецФункции", source, re.S)
    assert match
    body = match.group(0)
    assert 'Данные = Новый Структура("error,error_code,request_id"' in body
    assert 'Ответ.Заголовки.Вставить("X-Request-Id", ИдентификаторЗапроса)' in body
    assert "КодОшибкиПоУмолчанию(КодСостояния)" in body
    for code in ("invalid_json", "missing_query", "invalid_query",
                 "eventlog_unavailable", "access_denied"):
        assert f'"{code}"' in source


def test_no_raw_platform_error_text_reaches_client():
    # ОписаниеОшибки() содержит путь модуля и номер строки: клиенту он не нужен,
    # а полный текст остаётся в журнале регистрации.
    source = MODULE.read_text(encoding="utf-8-sig")
    assert "ОписаниеОшибки()" not in source
    assert "КраткоеПредставлениеОшибки(ИнформацияОбОшибке())" in source
    assert source.count("ПодробноеПредставлениеОшибки(ИнформацияОбОшибке())") == 1
    # Журнал может быть недоступен — запись не должна валить обработчик.
    journal = source[source.index("Процедура ЗаписатьОшибкуВЖурнал"):]
    journal = journal[:journal.index("КонецПроцедуры")]
    assert "Попытка" in journal and "Исключение" in journal
    assert 'ЗаписьЖурналаРегистрации("MCP.Ошибка"' in journal


def test_eventlog_user_filter_checks_type_before_concatenation():
    source = MODULE.read_text(encoding="utf-8-sig")
    body = body_of(source, "ЖурналРегистрацииPOST")
    guard = body.index('ТипЗнч(Параметры.user) <> Тип("Строка")')
    assert guard < body.index('" + Параметры.user')


def test_access_denied_text_is_uniform():
    source = MODULE.read_text(encoding="utf-8-sig")
    # Один и тот же отказ по праву метода — один и тот же текст.
    assert "Нет права использования метода или включён привилегированный режим" not in source
    assert source.count('ОтветОшибка(403, "Нет права использования метода")') >= 9
