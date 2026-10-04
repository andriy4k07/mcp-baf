# Graph Report - mcp-baf  (2026-10-04)

## Corpus Check
- 68 files · ~45,185 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 678 nodes · 1255 edges · 38 communities (36 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 43 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `38c31b56`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MCP Tool Registration Helpers
- 1C Extension Installer
- nfc
- index.py
- Package Init & BSL Tests
- 1C Form XML Parser
- SQLite FTS5 Index Store
- CLI Entry Point & Config
- Index Disk Cache
- Server Assembly & Config
- Form Structure Tool
- 1C HTTP Client
- Metadata Tree Tool
- Form Parser Tests
- Object Structure Tool
- HTTP Audit Tests
- Query Validation Tool
- Manual E2E Check Script
- BSL Data Generator Script
- SearchParams
- Async Transport Stub
- MCP Server Root
- HelpIndex
- docs/README.md
- traced_text
- mcp-baf
- test_objects.py
- Швидкий старт
- Пошук по коду та індекс
- Розробка
- `audit.log` — журнал бізнес-подій (JSONL)
- Конфігурація
- traced_text
- form.py
- test_client.py
- test_bsl.py
- prompts.py
- configuration_info.py

## God Nodes (most connected - your core abstractions)
1. `OneCClient` - 38 edges
2. `traced_text()` - 34 edges
3. `DumpIndex` - 31 edges
4. `create_server()` - 29 edges
5. `Parser` - 20 edges
6. `SearchParams` - 20 edges
7. `Config` - 18 edges
8. `load_config()` - 15 edges
9. `HelpIndex` - 15 edges
10. `_install_from()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `test_cache_reused_and_search_works()` --calls--> `SearchParams`  [INFERRED]
  tests/test_cache.py → src/mcp_baf/dumpindex/index.py
- `test_incremental_add_modify_delete()` --calls--> `SearchParams`  [INFERRED]
  tests/test_cache.py → src/mcp_baf/dumpindex/index.py
- `test_bom_stripped()` --calls--> `SearchParams`  [INFERRED]
  tests/test_dumpindex.py → src/mcp_baf/dumpindex/index.py
- `test_category_filter()` --calls--> `SearchParams`  [INFERRED]
  tests/test_dumpindex.py → src/mcp_baf/dumpindex/index.py
- `test_exact_search_case_insensitive()` --calls--> `SearchParams`  [INFERRED]
  tests/test_dumpindex.py → src/mcp_baf/dumpindex/index.py

## Import Cycles
- None detected.

## Communities (38 total, 2 thin omitted)

### Community 0 - "MCP Tool Registration Helpers"
Cohesion: 0.10
Nodes (25): clamp_limit(), escape_pipe(), format_cell(), Общие помощники для MCP-инструментов., Нормализует пользовательский limit к диапазону [default, maximum]., Экранирует вертикальную черту, чтобы не ломать markdown-таблицы., Преобразует значение ячейки JSON-ответа в строку для markdown-таблицы., format_references() (+17 more)

### Community 1 - "1C Extension Installer"
Cohesion: 0.09
Nodes (38): _build_designer_args(), classify_designer_error(), _error_contains(), extract_platform_minor(), find_platform(), format_version_for_platform(), install(), _install_from() (+30 more)

### Community 2 - "nfc"
Cohesion: 0.16
Nodes (17): NamedTuple, _base_config_module_name(), bsl_path_to_module_name(), ModuleNameParts, nfc(), parse_module_name(), Преобразование путей dump-выгрузки в человекочитаемые имена модулей.  Порт dump/, Приводит строку к Unicode NFC (порт dump.NFC из Go-версии).      macOS распаковы (+9 more)

### Community 3 - "index.py"
Cohesion: 0.16
Nodes (13): _best_line(), _extract_context(), _FileState, _first_line_with_any(), Match, Полнотекстовый индекс BSL-модулей на SQLite FTS5.  Порт dump/index.go из Go-верс, Ищет совпадения в проиндексированных модулях. Диспетчер по mode., Полнотекстовый поиск с BM25-ранжированием через FTS5. (+5 more)

### Community 4 - "Package Init & BSL Tests"
Cohesion: 0.10
Nodes (5): _copy_extension_sources(), Тесты вспомогательной логики installer (без запуска DESIGNER)., test_localize_extension_keeps_bom(), test_localize_extension_ru_is_noop(), test_localize_extension_ua()

### Community 5 - "1C Form XML Parser"
Cohesion: 0.13
Nodes (33): Element, _descend_into_child_items(), display_type(), find_form_files(), FormCommandInfo, FormElementInfo, FormHandlerInfo, FormInfo (+25 more)

### Community 6 - "SQLite FTS5 Index Store"
Cohesion: 0.14
Nodes (7): Connection, DumpIndex, Exception, Собирает состояние всех .bsl файлов: rel_path -> (путь, mtime, size)., Открывает кэш и инкрементально применяет изменения файлов., Удаляет документ из FTS5 с внешним содержимым.          Команде 'delete' нужно с, Индекс поиска по коду модулей из dump-выгрузки конфигурации.      Строится асинх

### Community 7 - "CLI Entry Point & Config"
Cohesion: 0.17
Nodes (21): Namespace, _env_int(), load_config(), parse_args(), Конфигурация MCP-сервера.  Приоритет источников (от низшего к высшему): значения, Собирает конфигурацию: defaults -> env -> CLI-флаги., Читает целое из переменной окружения.      Некорректные или неположительные знач, _version() (+13 more)

### Community 8 - "Index Disk Cache"
Cohesion: 0.22
Nodes (17): cache_path(), index_db_path(), Расположение дискового кэша индекса (порт dump/cache.go).  Кэш каждой dump-выгру, Платформенный каталог кэша пользователя (аналог os.UserCacheDir в Go)., Каталог кэша индекса для данной dump-выгрузки., user_cache_dir(), build(), mk_bsl() (+9 more)

### Community 9 - "Server Assembly & Config"
Cohesion: 0.15
Nodes (16): Доступность HTTP-инструментов по эффективным правам пользователя сервиса., Асинхронный HTTP-клиент для общения с 1С:Предприятие., Config, MCP-сервер для чтения BAF, поиска справки и анализа BSL., create_server(), MCPServer, Сборка MCP-сервера: создание MCPServer и регистрация инструментов., Убирает автогенерированные pydantic'ом "title" из JSON-схемы.      Смысла для мо (+8 more)

### Community 10 - "Form Structure Tool"
Cohesion: 0.29
Nodes (6): format_event_log(), Any, AuditWriter, MCPServer, Инструмент get_event_log: чтение журнала регистрации 1С., register()

### Community 11 - "1C HTTP Client"
Cohesion: 0.19
Nodes (8): AsyncBaseTransport, OneCClient, Any, AuditWriter, Пишет ровно одно событие one_c.http. Тело запроса/ответа не логируется., HTTP-клиент к HTTP-сервису 1С.      Если задан пользователь, ко всем запросам до, GET-запрос к эндпоинту 1С с разбором JSON-ответа., POST-запрос к эндпоинту 1С с JSON-телом и разбором JSON-ответа.

### Community 12 - "Metadata Tree Tool"
Cohesion: 0.24
Nodes (9): filter_noise(), format_metadata_summary(), format_metadata_tree(), _is_noise(), Инструмент get_metadata_tree: объекты конфигурации по категориям., Компактная сводка: названия категорий и количество объектов., Убирает автогенерируемые объекты из дерева метаданных., Полный перечень объектов. Известные категории идут первыми в     стабильном поря (+1 more)

### Community 13 - "Form Parser Tests"
Cohesion: 0.23
Nodes (6): parse_fixture(), Тесты разбора Form.xml.  Фикстуры в testdata/ — реальные файлы dump-выгрузки 1С, test_catalog_list_form(), test_common_form_password(), test_empty_form(), test_register_record_form()

### Community 14 - "Object Structure Tool"
Cohesion: 0.32
Nodes (7): _attr_line(), format_object_structure(), Any, AuditWriter, MCPServer, Инструмент get_object_structure: реквизиты и структура объекта метаданных., register()

### Community 15 - "HTTP Audit Tests"
Cohesion: 0.19
Nodes (9): Context, AccessMCP, AuditWriter, MCPServer, Скрывает недоступные инструменты и проверяет прямые вызовы., Проверка list и прямых calls, обновление прав, отказ при недоступности сервиса., test_fail_closed_and_local_tools_survive(), test_list_cache_call_refresh_and_denial_audit() (+1 more)

### Community 16 - "Query Validation Tool"
Cohesion: 0.29
Nodes (6): format_validate_result(), Any, AuditWriter, MCPServer, Инструмент validate_query: проверка синтаксиса запроса без выполнения., register()

### Community 17 - "Manual E2E Check Script"
Cohesion: 0.47
Nodes (5): main(), make_dump(), Path, Ручная e2e-проверка: запускает сервер по stdio и вызывает все инструменты.  Испо, Создаёт миниатюрную dump-выгрузку для проверки search_code и форм.

### Community 18 - "BSL Data Generator Script"
Cohesion: 0.67
Nodes (3): main(), Генерирует mcp_baf/bsl/_functions_data.py из bsl/functions.go (Go-версия).  Извл, unquote_go()

### Community 19 - "SearchParams"
Cohesion: 0.21
Nodes (15): SearchParams, index(), mk_bsl(), Тесты индекса поиска по dump-выгрузке (SQLite FTS5)., test_bom_stripped(), test_category_filter(), test_empty_dir(), test_exact_search_case_insensitive() (+7 more)

### Community 20 - "Async Transport Stub"
Cohesion: 0.08
Nodes (34): analyze(), _directives(), format_source(), _inspect(), NativeBSLAnalyzer, Собственные базовые проверки и консервативный форматер BSL на Python.  Никаких в, Проверяет пары директив, не пытаясь вычислять условия препроцессора., _semantic() (+26 more)

### Community 22 - "HelpIndex"
Cohesion: 0.07
Nodes (33): HTMLParser, Справочник встроенных функций 1С (порт bsl/functions.go).  Файл сгенерирован скр, Справочник встроенных функций языка 1С (BSL).  Порт пакета bsl из Go-версии. Дан, Ищет функции по имени (русскому или английскому), без учёта регистра., search(), build_synonym_map(), Двуязычные BSL-синонимы для полнотекстового поиска.  Порт dump/analyzer.go (buil, Двунаправленная карта синонимов BSL (в нижнем регистре). (+25 more)

### Community 23 - "docs/README.md"
Cohesion: 0.07
Nodes (33): Architecture, Commands, Development workflow (owner's hard rules), graphify, New local tools and access control, What this is, HTTP-контракти, Архітектура (+25 more)

### Community 25 - "mcp-baf"
Cohesion: 0.11
Nodes (19): 1. Встановити, 2. Встановити розширення в 1С, 3. Запустити HTTP-сервіс 1С, 4. Налаштувати AI-клієнт, `audit.log` — журнал подій (JSONL), mcp-baf, `server.log` — операційний журнал, Доступні інструменти (+11 more)

### Community 26 - "test_objects.py"
Cohesion: 0.20
Nodes (18): AuditLog, _check_extension_version(), Сверяет версию расширения 1С с ожидаемой.      Эндпоинт /version может отсутство, call(), events(), Контракты read-only инструментов: валидация, форматирование, аудит., setup_tools(), test_link_roundtrip_and_escaped_presentation() (+10 more)

### Community 27 - "Швидкий старт"
Cohesion: 0.12
Nodes (17): Вимоги, Встановлення, Далі, Крок 1. Встановити пакет, Крок 2. Встановити розширення в базу 1С, Крок 3. Опублікувати HTTP-сервіс, Крок 4. Налаштувати AI-клієнт, Крок 5. Перевірити (+9 more)

### Community 28 - "Пошук по коду та індекс"
Cohesion: 0.12
Nodes (17): `exact` — точний підрядок, `regex` — регулярний вираз, `smart` — BM25 + синоніми, Версія схеми, Дивіться також, Дисковий кеш, Неблокуючий старт, Нормалізація імен на macOS (+9 more)

### Community 29 - "Розробка"
Cohesion: 0.15
Nodes (13): E2E, Встановлення, Екосистема, Згенерований код, Конвенції коду, Нові контрактні перевірки, Робочий процес, Розробка (+5 more)

### Community 30 - "`audit.log` — журнал бізнес-подій (JSONL)"
Cohesion: 0.17
Nodes (12): `audit.log` — журнал бізнес-подій (JSONL), `server.log` — операційний журнал, stderr — тільки ERROR, `trace_id`: як `tool.call` пов'язується з `one_c.http`, Аудит нових інструментів, Логування та аудит, Приклад JSONL (реальні поля з коду), Ротація (+4 more)

### Community 31 - "Конфігурація"
Cohesion: 0.18
Nodes (11): Далі, Кеш, логи та аудит, Конфігурація, Нові локальні опції та доступ HTTP, Параметри режиму встановлення (`--install`), Параметри роботи сервера, Пошуковий індекс (`--dump`), Приклади (+3 more)

### Community 32 - "traced_text"
Cohesion: 0.13
Nodes (14): Анализ и форматирование переданного текста без изменения исходников., register(), AuditWriter, MCPServer, register(), Any, AuditWriter, Выполняет инструмент со сквозным аудитом и возвращает его текст как есть.      А (+6 more)

### Community 33 - "form.py"
Cohesion: 0.20
Nodes (9): OneCError, Exception, Ошибка взаимодействия с 1С с понятным пользователю текстом., Индекс полнотекстового поиска по dump-выгрузке конфигурации 1С., format_form_structure(), AuditWriter, MCPServer, Инструмент get_form_structure: структура управляемой формы объекта.  HTTP-endpoi (+1 more)

### Community 34 - "test_client.py"
Cohesion: 0.43
Nodes (7): _client(), _events(), Тесты аудита HTTP-вызовов 1С: ровно одно событие one_c.http на запрос., one_c.http наследует trace_id, выставленный traced_text для инструмента., test_one_c_http_inherits_tool_trace_id(), test_one_c_http_logged_on_error(), test_one_c_http_logged_on_success()

### Community 35 - "test_bsl.py"
Cohesion: 0.22
Nodes (4): format_functions(), Тесты справочника встроенных функций BSL и инструмента bsl_syntax_help., test_format_functions(), test_format_multiple_separated()

### Community 36 - "prompts.py"
Cohesion: 0.50
Nodes (3): MCPServer, MCP-prompts для типовых задач разработки 1С (порт prompts/prompts.go).  Каждый p, register()

### Community 37 - "configuration_info.py"
Cohesion: 0.29
Nodes (6): format_configuration_info(), Any, AuditWriter, MCPServer, Инструмент get_configuration_info: общая информация о базе 1С., register()

## Knowledge Gaps
- **98 isolated node(s):** `mcp-baf`, `What this is`, `Commands`, `Architecture`, `Development workflow (owner's hard rules)` (+93 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_server()` connect `Server Assembly & Config` to `traced_text`, `form.py`, `MCP Tool Registration Helpers`, `prompts.py`, `configuration_info.py`, `SQLite FTS5 Index Store`, `CLI Entry Point & Config`, `Form Structure Tool`, `1C HTTP Client`, `Object Structure Tool`, `HTTP Audit Tests`, `Query Validation Tool`, `Async Transport Stub`, `HelpIndex`, `test_objects.py`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `DumpIndex` connect `SQLite FTS5 Index Store` to `MCP Tool Registration Helpers`, `form.py`, `index.py`, `Index Disk Cache`, `Server Assembly & Config`, `SearchParams`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `OneCClient` connect `1C HTTP Client` to `traced_text`, `form.py`, `MCP Tool Registration Helpers`, `test_client.py`, `configuration_info.py`, `Server Assembly & Config`, `Form Structure Tool`, `Metadata Tree Tool`, `Object Structure Tool`, `HTTP Audit Tests`, `Query Validation Tool`, `test_objects.py`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `OneCClient` (e.g. with `AccessMCP` and `Config`) actually correct?**
  _`OneCClient` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DumpIndex` (e.g. with `build()` and `index()`) actually correct?**
  _`DumpIndex` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Parser` (e.g. with `NativeBSLAnalyzer` and `Diagnostic`) actually correct?**
  _`Parser` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `mcp-baf`, `What this is`, `Commands` to the rest of the system?**
  _98 weakly-connected nodes found - possible documentation gaps or missing edges._