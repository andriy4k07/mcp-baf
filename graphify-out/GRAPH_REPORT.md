# Graph Report - mcp-baf  (2026-10-05)

## Corpus Check
- 68 files · ~46,717 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 695 nodes · 1289 edges · 37 communities (35 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 42 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8dc4a587`
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
- test_bsl.py
- configuration_info.py
- dumpindex/__init__.py

## God Nodes (most connected - your core abstractions)
1. `OneCClient` - 38 edges
2. `traced_text()` - 35 edges
3. `DumpIndex` - 31 edges
4. `create_server()` - 29 edges
5. `SearchParams` - 20 edges
6. `Parser` - 19 edges
7. `Config` - 19 edges
8. `HelpIndex` - 17 edges
9. `_install_from()` - 16 edges
10. `load_config()` - 15 edges

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

## Communities (37 total, 2 thin omitted)

### Community 0 - "MCP Tool Registration Helpers"
Cohesion: 0.11
Nodes (23): OneCError, Exception, Асинхронный HTTP-клиент для общения с 1С:Предприятие., Ошибка взаимодействия с 1С с понятным пользователю текстом., clamp_limit(), escape_pipe(), format_cell(), Общие помощники для MCP-инструментов. (+15 more)

### Community 1 - "1C Extension Installer"
Cohesion: 0.08
Nodes (43): _build_designer_args(), classify_designer_error(), _designer_log_is_fatal(), _error_contains(), extract_platform_minor(), find_platform(), format_version_for_platform(), install() (+35 more)

### Community 2 - "nfc"
Cohesion: 0.13
Nodes (20): NamedTuple, _FileState, Полнотекстовый индекс BSL-модулей на SQLite FTS5.  Порт dump/index.go из Go-верс, Состояние одного .bsl файла на диске (для diff манифеста)., _base_config_module_name(), bsl_path_to_module_name(), ModuleNameParts, nfc() (+12 more)

### Community 3 - "index.py"
Cohesion: 0.22
Nodes (7): _best_line(), _extract_context(), _first_line_with_any(), Ищет совпадения в проиндексированных модулях. Диспетчер по mode., Полнотекстовый поиск с BM25-ранжированием через FTS5., Построчный поиск (режимы regex и exact)., Строка с наибольшим числом различных токенов запроса (0 — нет совпадений).

### Community 4 - "Package Init & BSL Tests"
Cohesion: 0.09
Nodes (5): _copy_extension_sources(), Тесты вспомогательной логики installer (без запуска DESIGNER)., test_localize_extension_keeps_bom(), test_localize_extension_ru_is_noop(), test_localize_extension_ua()

### Community 5 - "1C Form XML Parser"
Cohesion: 0.13
Nodes (33): Element, _descend_into_child_items(), display_type(), find_form_files(), FormCommandInfo, FormElementInfo, FormHandlerInfo, FormInfo (+25 more)

### Community 6 - "SQLite FTS5 Index Store"
Cohesion: 0.14
Nodes (7): Connection, DumpIndex, Exception, Собирает состояние всех .bsl файлов: rel_path -> (путь, mtime, size)., Открывает кэш и инкрементально применяет изменения файлов., Удаляет документ из FTS5 с внешним содержимым.          Команде 'delete' нужно с, Индекс поиска по коду модулей из dump-выгрузки конфигурации.      Строится асинх

### Community 7 - "CLI Entry Point & Config"
Cohesion: 0.17
Nodes (20): Namespace, _env_int(), load_config(), parse_args(), Собирает конфигурацию: defaults -> env -> CLI-флаги., Читает целое из переменной окружения.      Некорректные или неположительные знач, _version(), main() (+12 more)

### Community 8 - "Index Disk Cache"
Cohesion: 0.22
Nodes (17): cache_path(), index_db_path(), Расположение дискового кэша индекса (порт dump/cache.go).  Кэш каждой dump-выгру, Платформенный каталог кэша пользователя (аналог os.UserCacheDir в Go)., Каталог кэша индекса для данной dump-выгрузки., user_cache_dir(), build(), mk_bsl() (+9 more)

### Community 9 - "Server Assembly & Config"
Cohesion: 0.22
Nodes (12): AsyncBaseTransport, AuditWriter, Config, Конфигурация MCP-сервера.  Приоритет источников (от низшего к высшему): значения, create_server(), MCPServer, test_tool_schemas_prompts_and_expected_errors(), Тесты состава MCP-сервера и аудита жизненного цикла. (+4 more)

### Community 10 - "Form Structure Tool"
Cohesion: 0.13
Nodes (14): Анализ и форматирование переданного текста без изменения исходников., register(), Any, AuditWriter, Выполняет инструмент со сквозным аудитом и возвращает его текст как есть.      А, traced_text(), AuditWriter, MCPServer (+6 more)

### Community 11 - "1C HTTP Client"
Cohesion: 0.32
Nodes (7): format_references(), parse_link(), Поиск ссылок, навигация и права метаданных. Собственная реализация контрактов., Внутренняя ссылка или URL публикации с фрагментом e1cib/data/., register(), validate_kind(), validate_ref()

### Community 12 - "Metadata Tree Tool"
Cohesion: 0.18
Nodes (12): filter_noise(), format_metadata_summary(), format_metadata_tree(), _is_noise(), AuditWriter, MCPServer, Инструмент get_metadata_tree: объекты конфигурации по категориям., Компактная сводка: названия категорий и количество объектов. (+4 more)

### Community 13 - "Form Parser Tests"
Cohesion: 0.23
Nodes (6): parse_fixture(), Тесты разбора Form.xml.  Фикстуры в testdata/ — реальные файлы dump-выгрузки 1С, test_catalog_list_form(), test_common_form_password(), test_empty_form(), test_register_record_form()

### Community 14 - "Object Structure Tool"
Cohesion: 0.32
Nodes (7): _attr_line(), format_object_structure(), Any, AuditWriter, MCPServer, Инструмент get_object_structure: реквизиты и структура объекта метаданных., register()

### Community 15 - "HTTP Audit Tests"
Cohesion: 0.11
Nodes (16): Context, AccessMCP, AuditWriter, MCPServer, Доступность HTTP-инструментов по эффективным правам пользователя сервиса., Скрывает недоступные инструменты и проверяет прямые вызовы., OneCClient, Any (+8 more)

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
Nodes (38): analyze(), _directives(), format_source(), _inspect(), Собственные базовые проверки и консервативный форматер BSL на Python.  Никаких в, Проверяет пары директив, не пытаясь вычислять условия препроцессора., _semantic(), _walk() (+30 more)

### Community 22 - "HelpIndex"
Cohesion: 0.07
Nodes (37): HTMLParser, Справочник встроенных функций 1С (порт bsl/functions.go).  Файл сгенерирован скр, Справочник встроенных функций языка 1С (BSL).  Порт пакета bsl из Go-версии. Дан, Ищет функции по имени (русскому или английскому), без учёта регистра., search(), build_synonym_map(), Двуязычные BSL-синонимы для полнотекстового поиска.  Порт dump/analyzer.go (buil, Двунаправленная карта синонимов BSL (в нижнем регистре). (+29 more)

### Community 23 - "docs/README.md"
Cohesion: 0.07
Nodes (33): Architecture, Commands, Development workflow (owner's hard rules), graphify, New local tools and access control, What this is, HTTP-контракти, Архітектура (+25 more)

### Community 25 - "mcp-baf"
Cohesion: 0.11
Nodes (19): 1. Встановити, 2. Встановити розширення в 1С, 3. Запустити HTTP-сервіс 1С, 4. Налаштувати AI-клієнт, `audit.log` — журнал подій (JSONL), mcp-baf, `server.log` — операційний журнал, Доступні інструменти (+11 more)

### Community 26 - "test_objects.py"
Cohesion: 0.23
Nodes (17): AuditLog, call(), events(), Контракты read-only инструментов: валидация, форматирование, аудит., setup_tools(), test_link_roundtrip_and_escaped_presentation(), test_missing_object_and_service_error(), test_references_body_grouping_and_privacy() (+9 more)

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
Cohesion: 0.11
Nodes (14): MCP-сервер для чтения BAF, поиска справки и анализа BSL., MCPServer, MCP-prompts для типовых задач разработки 1С (порт prompts/prompts.go).  Каждый p, register(), _check_extension_version(), Сборка MCP-сервера: создание MCPServer и регистрация инструментов., Убирает автогенерированные pydantic'ом "title" из JSON-схемы.      Смысла для мо, Сверяет версию расширения 1С с ожидаемой.      Эндпоинт /version может отсутство (+6 more)

### Community 33 - "form.py"
Cohesion: 0.43
Nodes (7): _client(), _events(), Тесты аудита HTTP-вызовов 1С: ровно одно событие one_c.http на запрос., one_c.http наследует trace_id, выставленный traced_text для инструмента., test_one_c_http_inherits_tool_trace_id(), test_one_c_http_logged_on_error(), test_one_c_http_logged_on_success()

### Community 35 - "test_bsl.py"
Cohesion: 0.22
Nodes (4): format_functions(), Тесты справочника встроенных функций BSL и инструмента bsl_syntax_help., test_format_functions(), test_format_multiple_separated()

### Community 37 - "configuration_info.py"
Cohesion: 0.29
Nodes (6): format_configuration_info(), Any, AuditWriter, MCPServer, Инструмент get_configuration_info: общая информация о базе 1С., register()

### Community 38 - "dumpindex/__init__.py"
Cohesion: 0.24
Nodes (8): Match, Одно совпадение поиска в BSL-модуле., Индекс полнотекстового поиска по dump-выгрузке конфигурации 1С., format_search_result(), AuditWriter, MCPServer, Инструмент search_code: полнотекстовый поиск по коду модулей конфигурации., register()

## Knowledge Gaps
- **98 isolated node(s):** `mcp-baf`, `What this is`, `Commands`, `Architecture`, `Development workflow (owner's hard rules)` (+93 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_server()` connect `Server Assembly & Config` to `traced_text`, `MCP Tool Registration Helpers`, `configuration_info.py`, `SQLite FTS5 Index Store`, `CLI Entry Point & Config`, `dumpindex/__init__.py`, `Form Structure Tool`, `1C HTTP Client`, `Metadata Tree Tool`, `Object Structure Tool`, `HTTP Audit Tests`, `Query Validation Tool`, `HelpIndex`, `test_objects.py`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `DumpIndex` connect `SQLite FTS5 Index Store` to `traced_text`, `nfc`, `index.py`, `dumpindex/__init__.py`, `Index Disk Cache`, `Server Assembly & Config`, `SearchParams`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `OneCClient` connect `HTTP Audit Tests` to `MCP Tool Registration Helpers`, `traced_text`, `form.py`, `configuration_info.py`, `Server Assembly & Config`, `Form Structure Tool`, `Metadata Tree Tool`, `Object Structure Tool`, `Query Validation Tool`, `test_objects.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `OneCClient` (e.g. with `AccessMCP` and `Config`) actually correct?**
  _`OneCClient` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DumpIndex` (e.g. with `build()` and `index()`) actually correct?**
  _`DumpIndex` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SearchParams` (e.g. with `test_cache_reused_and_search_works()` and `test_incremental_add_modify_delete()`) actually correct?**
  _`SearchParams` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `mcp-baf`, `What this is`, `Commands` to the rest of the system?**
  _98 weakly-connected nodes found - possible documentation gaps or missing edges._