# Graph Report - .  (2026-07-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 393 nodes · 731 edges · 22 communities (20 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 24 edges (avg confidence: 0.78)
- Token cost: 22,629 input · 307 output

## Graph Freshness
- Built from commit: `8014363f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MCP Tool Registration Helpers
- 1C Extension Installer
- BSL Code Search Engine
- BSL Reference & Dump Indexing
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
- 1C Development Prompts
- Async Transport Stub
- MCP Server Root

## God Nodes (most connected - your core abstractions)
1. `DumpIndex` - 31 edges
2. `OneCClient` - 29 edges
3. `traced_text()` - 25 edges
4. `create_server()` - 21 edges
5. `SearchParams` - 20 edges
6. `_install_from()` - 15 edges
7. `load_config()` - 14 edges
8. `Config` - 12 edges
9. `parse_args()` - 12 edges
10. `_parse_form_root()` - 11 edges

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

## Communities (22 total, 2 thin omitted)

### Community 0 - "MCP Tool Registration Helpers"
Cohesion: 0.07
Nodes (40): AuditLog, AuditWriter, FastMCP, Инструмент bsl_syntax_help: справочник встроенных функций языка 1С.  Работает ло, register(), clamp_limit(), escape_pipe(), format_cell() (+32 more)

### Community 1 - "1C Extension Installer"
Cohesion: 0.09
Nodes (38): _build_designer_args(), classify_designer_error(), _error_contains(), extract_platform_minor(), find_platform(), format_version_for_platform(), install(), _install_from() (+30 more)

### Community 2 - "BSL Code Search Engine"
Cohesion: 0.09
Nodes (30): _best_line(), _extract_context(), _first_line_with_any(), Match, Ищет совпадения в проиндексированных модулях. Диспетчер по mode., Полнотекстовый поиск с BM25-ранжированием через FTS5., Построчный поиск (режимы regex и exact)., Строка с наибольшим числом различных токенов запроса (0 — нет совпадений). (+22 more)

### Community 3 - "BSL Reference & Dump Indexing"
Cohesion: 0.08
Nodes (29): NamedTuple, Справочник встроенных функций 1С (порт bsl/functions.go).  Файл сгенерирован скр, Справочник встроенных функций языка 1С (BSL).  Порт пакета bsl из Go-версии. Дан, Ищет функции по имени (русскому или английскому), без учёта регистра., search(), find_form_files(), Находит все Form.xml объекта в dump-выгрузке.      Возвращает словарь имя формы, _FileState (+21 more)

### Community 4 - "Package Init & BSL Tests"
Cohesion: 0.07
Nodes (10): MCP-сервер для 1С:Предприятие (Python-версия)., format_functions(), Тесты справочника встроенных функций BSL и инструмента bsl_syntax_help., test_format_functions(), test_format_multiple_separated(), _copy_extension_sources(), Тесты вспомогательной логики installer (без запуска DESIGNER)., test_localize_extension_keeps_bom() (+2 more)

### Community 5 - "1C Form XML Parser"
Cohesion: 0.19
Nodes (24): Element, _descend_into_child_items(), display_type(), FormCommandInfo, FormElementInfo, FormHandlerInfo, FormInfo, _local() (+16 more)

### Community 6 - "SQLite FTS5 Index Store"
Cohesion: 0.14
Nodes (7): Connection, DumpIndex, Exception, Собирает состояние всех .bsl файлов: rel_path -> (путь, mtime, size)., Открывает кэш и инкрементально применяет изменения файлов., Удаляет документ из FTS5 с внешним содержимым.          Команде 'delete' нужно с, Индекс поиска по коду модулей из dump-выгрузки конфигурации.      Строится асинх

### Community 7 - "CLI Entry Point & Config"
Cohesion: 0.18
Nodes (19): Namespace, _env_int(), load_config(), parse_args(), Собирает конфигурацию: defaults -> env -> CLI-флаги., Читает целое из переменной окружения.      Некорректные или неположительные знач, _version(), main() (+11 more)

### Community 8 - "Index Disk Cache"
Cohesion: 0.22
Nodes (17): cache_path(), index_db_path(), Расположение дискового кэша индекса (порт dump/cache.go).  Кэш каждой dump-выгру, Платформенный каталог кэша пользователя (аналог os.UserCacheDir в Go)., Каталог кэша индекса для данной dump-выгрузки., user_cache_dir(), build(), mk_bsl() (+9 more)

### Community 9 - "Server Assembly & Config"
Cohesion: 0.19
Nodes (12): Асинхронный HTTP-клиент для общения с 1С:Предприятие., Config, Конфигурация MCP-сервера.  Приоритет источников (от низшего к высшему): значения, create_server(), FastMCP, Сборка MCP-сервера: создание FastMCP и регистрация инструментов., Убирает автогенерированные pydantic'ом "title" из JSON-схемы.      Смысла для мо, _strip_schema_titles() (+4 more)

### Community 10 - "Form Structure Tool"
Cohesion: 0.17
Nodes (15): OneCError, Exception, Ошибка взаимодействия с 1С с понятным пользователю текстом., convert_dump_form(), form_from_dump(), format_form_structure(), merge_dump_into_form(), Any (+7 more)

### Community 11 - "1C HTTP Client"
Cohesion: 0.21
Nodes (8): OneCClient, Any, Пишет ровно одно событие one_c.http. Тело запроса/ответа не логируется., HTTP-клиент к HTTP-сервису 1С.      Если задан пользователь, ко всем запросам до, GET-запрос к эндпоинту 1С с разбором JSON-ответа., POST-запрос к эндпоинту 1С с JSON-телом и разбором JSON-ответа., _check_extension_version(), Сверяет версию расширения 1С с ожидаемой.      Эндпоинт /version может отсутство

### Community 12 - "Metadata Tree Tool"
Cohesion: 0.18
Nodes (12): filter_noise(), format_metadata_summary(), format_metadata_tree(), _is_noise(), AuditWriter, FastMCP, Инструмент get_metadata_tree: объекты конфигурации по категориям., Компактная сводка: названия категорий и количество объектов. (+4 more)

### Community 13 - "Form Parser Tests"
Cohesion: 0.23
Nodes (6): parse_fixture(), Тесты разбора Form.xml.  Фикстуры в testdata/ — реальные файлы dump-выгрузки 1С, test_catalog_list_form(), test_common_form_password(), test_empty_form(), test_register_record_form()

### Community 14 - "Object Structure Tool"
Cohesion: 0.32
Nodes (7): _attr_line(), format_object_structure(), Any, AuditWriter, FastMCP, Инструмент get_object_structure: реквизиты и структура объекта метаданных., register()

### Community 15 - "HTTP Audit Tests"
Cohesion: 0.43
Nodes (7): _client(), _events(), Тесты аудита HTTP-вызовов 1С: ровно одно событие one_c.http на запрос., one_c.http наследует trace_id, выставленный traced_text для инструмента., test_one_c_http_inherits_tool_trace_id(), test_one_c_http_logged_on_error(), test_one_c_http_logged_on_success()

### Community 16 - "Query Validation Tool"
Cohesion: 0.29
Nodes (6): format_validate_result(), Any, AuditWriter, FastMCP, Инструмент validate_query: проверка синтаксиса запроса без выполнения., register()

### Community 17 - "Manual E2E Check Script"
Cohesion: 0.47
Nodes (5): Path, main(), make_dump(), Ручная e2e-проверка: запускает сервер по stdio и вызывает все инструменты.  Испо, Создаёт миниатюрную dump-выгрузку для проверки search_code и форм.

### Community 18 - "BSL Data Generator Script"
Cohesion: 0.67
Nodes (3): main(), Генерирует mcp_baf/bsl/_functions_data.py из bsl/functions.go (Go-версия).  Извл, unquote_go()

### Community 19 - "1C Development Prompts"
Cohesion: 0.50
Nodes (3): FastMCP, MCP-prompts для типовых задач разработки 1С (порт prompts/prompts.go).  Каждый p, register()

## Knowledge Gaps
- **1 isolated node(s):** `mcp-baf`
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DumpIndex` connect `SQLite FTS5 Index Store` to `Index Disk Cache`, `Server Assembly & Config`, `BSL Code Search Engine`, `BSL Reference & Dump Indexing`?**
  _High betweenness centrality (0.191) - this node is a cross-community bridge._
- **Why does `create_server()` connect `Server Assembly & Config` to `MCP Tool Registration Helpers`, `BSL Code Search Engine`, `SQLite FTS5 Index Store`, `CLI Entry Point & Config`, `Form Structure Tool`, `1C HTTP Client`, `Metadata Tree Tool`, `Object Structure Tool`, `Query Validation Tool`, `1C Development Prompts`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Why does `OneCClient` connect `1C HTTP Client` to `MCP Tool Registration Helpers`, `Server Assembly & Config`, `Form Structure Tool`, `Metadata Tree Tool`, `Object Structure Tool`, `HTTP Audit Tests`, `Query Validation Tool`, `Async Transport Stub`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `DumpIndex` (e.g. with `build()` and `index()`) actually correct?**
  _`DumpIndex` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SearchParams` (e.g. with `test_cache_reused_and_search_works()` and `test_incremental_add_modify_delete()`) actually correct?**
  _`SearchParams` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `mcp-baf` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MCP Tool Registration Helpers` be split into smaller, more focused modules?**
  _Cohesion score 0.06859903381642513 - nodes in this community are weakly interconnected._