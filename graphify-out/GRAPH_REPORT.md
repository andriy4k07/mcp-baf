# Graph Report - mcp-baf  (2026-11-18)

## Corpus Check
- 108 files · ~109,506 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1810 nodes · 3741 edges · 90 communities (83 shown, 7 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 205 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `21317697`
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
- ._do
- test_bsl.py
- .__init__
- configuration_info.py
- dumpindex/__init__.py
- pii.py
- test_metadata_reads_bsl_guard.py
- tls.py
- _SyntheticBuild
- ensure_self_signed
- access.py
- test_dependency_bounds.py
- mask_pii_text
- test_bsl_capabilities_guard.py
- test_tls_concurrency.py
- _scripted_install
- LockTimeout
- scrub_error_detail
- test_https_transport.py
- CLAUDE.md
- Сумісність
- Архітектура
- ._search_smart
- register
- Документація mcp-baf
- file_lock
- _recorder
- Перелік інструментів
- _copy_extension_sources
- Локальна довідка та BSL
- Джерела і ліцензії
- test_docker_entrypoint.py
- _fake_run_with_log
- _timeout_run
- docker-entrypoint.sh
- bsl/__init__.py
- scrub_error_detail
- prompts.py
- register
- _isolate_pii_state
- test_leftover_pid_temp_file_does_not_block_startup
- ConfigError
- _env_float
- _DripStream
- test_preexisting_weak_key_file_perms_are_tightened
- test_masking_note_qualified_for_columnless_tools
- parse_platform_version
- newest_platform
- classify_designer_error
- _run_http
- OneCError
- test_query_hints.py
- test_traced.py
- prompts.py
- .__init__
- _DripStream

## God Nodes (most connected - your core abstractions)
1. `OneCClient` - 72 edges
2. `Config` - 60 edges
3. `DumpIndex` - 60 edges
4. `load_config()` - 46 edges
5. `SearchParams` - 46 edges
6. `parse_args()` - 39 edges
7. `traced_text()` - 34 edges
8. `discover_extension_roots()` - 31 edges
9. `create_server()` - 29 edges
10. `ensure_self_signed()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `test_dcs_text_searchable_by_smart()` --calls--> `SearchParams`  [INFERRED]
  tests/test_dumpindex_usages.py → src/mcp_baf/dumpindex/index.py
- `test_email_in_code_like_token_still_masked()` --calls--> `mask_pii_text()`  [INFERRED]
  tests/test_pii.py → src/mcp_baf/pii.py
- `test_mask_pii_text_replaces_contacts_only()` --calls--> `mask_pii_text()`  [INFERRED]
  tests/test_pii.py → src/mcp_baf/pii.py
- `test_split_host_port_rejects_malformed()` --calls--> `split_host_port()`  [INFERRED]
  tests/test_main.py → src/mcp_baf/tls.py
- `test_form_structure_masks_title_and_handlers()` --calls--> `format_form_structure()`  [INFERRED]
  tests/test_pii.py → src/mcp_baf/tools/form.py

## Import Cycles
- None detected.

## Communities (90 total, 7 thin omitted)

### Community 0 - "MCP Tool Registration Helpers"
Cohesion: 0.29
Nodes (9): format_event_log(), Any, Форматирует журнал; при mask_pii телефон/email в полях скрываются.      Журнал р, Тесты маскирования ПДн в журнале регистрации (get_event_log)., test_event_log_masking_empty_result(), test_event_log_masks_phone_and_email(), test_event_log_truncated_gives_cursor_for_next_page(), test_event_log_truncated_without_cursor_advises_narrowing() (+1 more)

### Community 1 - "1C Extension Installer"
Cohesion: 0.05
Nodes (65): Имя каталога не может принадлежать расширению (каталог «вида»,     стандартный к, _rejected_dir_name(), _build_designer_args(), build_logcfg(), classify_designer_error(), _designer_log_is_fatal(), designer_timeout(), dump() (+57 more)

### Community 2 - "nfc"
Cohesion: 0.07
Nodes (61): discover_extension_roots(), Находит вложенные корни расширений: rel_dir -> имя из манифеста.      Ключи — от, _base_config_module_name(), bsl_path_to_module_name(), ModuleNameParts, nfc(), parse_module_name(), NamedTuple (+53 more)

### Community 3 - "index.py"
Cohesion: 0.16
Nodes (10): Ссылки на объект в одном модуле/СКД: номера строк (для СКД — в тексте запросов)., Usage, Индекс полнотекстового поиска по dump-выгрузке конфигурации 1С., format_usages(), Сгруппированный список модулей/СКД со строками и числом ссылок., idx(), _mk(), Тесты обратных зависимостей (mode=usages) и индексации СКД. (+2 more)

### Community 5 - "1C Form XML Parser"
Cohesion: 0.09
Nodes (54): _edt_manifest(), _edt_project(), _list_dirs(), _local(), _manifest_name(), Поиск вложенных кореньев расширений в dump-выгрузке.  Порт поведения feenlace/mc, Читает Configuration.mdo EDT-проекта: (это расширение?, имя).      shortcut: фор, Читает имя расширения из Configuration.xml (или '' при отказе). (+46 more)

### Community 6 - "SQLite FTS5 Index Store"
Cohesion: 0.12
Nodes (10): DumpIndex, Connection, Exception, Индекс поиска по коду модулей из dump-выгрузки конфигурации.      Строится асинх, Векторный индекс строится после готовности FTS: читает модули пачками., Собирает состояние всех .bsl файлов: rel_path -> (путь, mtime, size)., Создаёт схему и наполняет базу пачками по BUILD_BATCH модулей.          Содержим, Атомарно подменяет index.db собранным временным файлом.          На POSIX os.rep (+2 more)

### Community 7 - "CLI Entry Point & Config"
Cohesion: 0.12
Nodes (40): Namespace, load_config(), parse_args(), Собирает конфигурацию: defaults -> env -> CLI-флаги., clean_env(), Тесты конфигурации: приоритет defaults -> env -> CLI., Изолирует тест от mcp_baf_* переменных окружения хоста., test_allowed_hosts_malformed_env_rejected_at_load() (+32 more)

### Community 8 - "Index Disk Cache"
Cohesion: 0.14
Nodes (30): cache_path(), index_db_path(), Расположение дискового кэша индекса (порт dump/cache.go).  Кэш каждой dump-выгру, Платформенный каталог кэша пользователя (аналог os.UserCacheDir в Go)., Каталог кэша индекса для данной dump-выгрузки., user_cache_dir(), vectors_db_path(), _assert_db_intact() (+22 more)

### Community 9 - "Server Assembly & Config"
Cohesion: 0.24
Nodes (7): _join_background_threads(), Контракты SDK 2: схемы, все prompts, ошибки и реальный stdio-процесс., Не пропускаем фоновые daemon-потоки за границу теста (issue #56).      create_se, _server(), test_discover_cache_hint_and_no_logging_capability(), test_discover_over_streamable_http(), test_tool_schemas_prompts_and_expected_errors()

### Community 10 - "Form Structure Tool"
Cohesion: 0.24
Nodes (11): find_form_files(), _forms_in(), Формы объекта в одном корне выгрузки: Designer, EDT, EDT с src/ внутри base., Находит все формы объекта (Form.xml / Form.form) в dump-выгрузке.      Возвращае, parse_link(), Внутренняя ссылка или URL публикации с фрагментом e1cib/data/., Обязательное строковое поле ответа 1С: иначе явная ошибка контракта., _required_str() (+3 more)

### Community 11 - "1C HTTP Client"
Cohesion: 0.16
Nodes (17): format_cell(), Any, Преобразует значение ячейки JSON-ответа в строку для markdown-таблицы., test_null_is_rendered_as_empty_cell_not_blank_string(), call(), execute_query: пагинация, проверка «только SELECT» и маскирование ПДн., setup(), test_comment_prefixed_select_reaches_extension() (+9 more)

### Community 12 - "Metadata Tree Tool"
Cohesion: 0.09
Nodes (31): CanCall, load_tree(), Any, Дерево метаданных: одна коллекция при filter, иначе кэшированный полный обход., format_query_result(), access_checker(), advise_query(), _args_count() (+23 more)

### Community 13 - "Form Parser Tests"
Cohesion: 0.13
Nodes (6): parse_fixture(), Тесты разбора Form.xml.  Фикстуры в testdata/ — реальные файлы dump-выгрузки 1С, test_catalog_list_form(), test_common_form_password(), test_empty_form(), test_register_record_form()

### Community 14 - "Object Structure Tool"
Cohesion: 0.11
Nodes (27): Асинхронный HTTP-клиент для общения с 1С:Предприятие., MCP-сервер для чтения BAF, поиска справки и анализа BSL., mask_pii_text(), Маскирует свободный текст (None -> пустая строка) по regex ПДн.      Используетс, Сборка MCP-сервера: создание MCPServer и регистрация инструментов., Анализ и форматирование переданного текста без изменения исходников., register(), clamp_limit() (+19 more)

### Community 15 - "HTTP Audit Tests"
Cohesion: 0.15
Nodes (23): AuditLog, Config, one_c.http наследует trace_id, выставленный traced_text для инструмента., test_error_code_hint_survives_mask_pii(), test_one_c_http_inherits_tool_trace_id(), test_event_log_400_from_extension_becomes_tool_error(), test_event_log_tool_output_is_limited(), get_form_structure: отказ dump-обогащения виден в ответе, а не только в логе. (+15 more)

### Community 16 - "Query Validation Tool"
Cohesion: 0.10
Nodes (24): audit_text(), Свободный текст (запрос) для args аудита: при --mask-pii маскируется,     всегда, create_server(), MCPServer, AuditWriter, MCPServer, Инструмент bsl_syntax_help: справочник встроенных функций языка 1С.  Работает ло, register() (+16 more)

### Community 17 - "Manual E2E Check Script"
Cohesion: 0.47
Nodes (5): main(), make_dump(), Path, Ручная e2e-проверка: запускает сервер по stdio и вызывает все инструменты.  Испо, Создаёт миниатюрную dump-выгрузку для проверки search_code и форм.

### Community 18 - "BSL Data Generator Script"
Cohesion: 0.67
Nodes (3): main(), Генерирует mcp_baf/bsl/_functions_data.py из bsl/functions.go (Go-версия).  Извл, unquote_go()

### Community 19 - "SearchParams"
Cohesion: 0.11
Nodes (35): SearchParams, index(), mk_bsl(), mk_manifest(), Тесты индекса поиска по dump-выгрузке (SQLite FTS5)., #61: `(\\w\\w|\\w)+!` не ловится эвристикой вложенных кванторов, но     должен п, Режимы regex/exact не тянут весь код модулей через fetchall()., Найденное до исчерпания бюджета не выбрасывается, а помечается усечённым. (+27 more)

### Community 20 - "Async Transport Stub"
Cohesion: 0.08
Nodes (51): analyze(), format_source(), codes(), Синтаксис, безопасное форматирование и приватность Python-анализатора., test_alternative_header_keeps_reserved_name_suppression_and_parameter_check(), test_analyzer_accepts_own_extension(), test_audit_has_char_count_not_code_and_stays_small(), test_bare_raise_before_block_terminators() (+43 more)

### Community 22 - "HelpIndex"
Cohesion: 0.21
Nodes (14): create_index(), make_hbk(), HBK-контейнер, двуязычный поиск, кеш и ошибки построения., test_ambiguous_cards_source_disambiguates(), test_bom_title_and_type_names(), test_broken_file_does_not_disable_help_and_partial_names_match(), test_build_errors_are_explicit(), test_disk_cache_invalidation_corruption_and_reindex() (+6 more)

### Community 24 - "traced_text"
Cohesion: 0.08
Nodes (39): _is_loopback_bind(), True для loopback-bind: уся петля 127.0.0.0/8, ::1 і `localhost`.      Рядкового, Режим установки и справка CLI не должны импортировать MCP-сервер., Функциональная проверка тем же middleware, что использует SDK., `--http-allowed-hosts mcp-baf` не должен превращать сервис в 421., Для 80/443 браузер шлёт Origin без порту — додаємо й такий варіант., Порожній список — поведінка #27: типові хости з портом і `:*`., 127.0.0.2 — теж loopback (127.0.0.0/8), захист має бути увімкнений. (+31 more)

### Community 25 - "mcp-baf"
Cohesion: 0.10
Nodes (20): 1. Встановити, 2. Встановити розширення в 1С, 3. Запустити HTTP-сервіс 1С, 4. Налаштувати AI-клієнт, `audit.log` — журнал подій (JSONL), mcp-baf, `server.log` — операційний журнал, Безпека й аудит (+12 more)

### Community 26 - "test_objects.py"
Cohesion: 0.21
Nodes (18): call(), events(), Контракты read-only инструментов: валидация, форматирование, аудит., setup_tools(), test_link_roundtrip_and_escaped_presentation(), test_mask_pii_in_references_and_link(), test_missing_object_and_service_error(), test_object_link_tolerates_null_link() (+10 more)

### Community 27 - "Швидкий старт"
Cohesion: 0.11
Nodes (18): EDT-проєкти, Вимоги, Встановлення, Далі, Крок 1. Встановити пакет, Крок 2. Встановити розширення в базу 1С, Крок 3. Опублікувати HTTP-сервіс, Крок 4. Налаштувати AI-клієнт (+10 more)

### Community 28 - "Пошук по коду та індекс"
Cohesion: 0.10
Nodes (20): `exact` — точний підрядок, `regex` — регулярний вираз, `smart` — BM25 + синоніми, `usages` — зворотні залежності (issue #129, ч. 1), Версія схеми, Гібридний пошук (BM25 + вектори, issue #159 ч. 2), Дивіться також, Дисковий кеш (+12 more)

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
Cohesion: 0.05
Nodes (42): Маскирует ПДн и обрезает тело ошибки 1С до безопасной длины., scrub_error_detail(), _is_pii_name(), mask_pii_result(), _pii_aliases(), Алиасы `КАК X`, чьё выражение содержит чувствительное поле (в нижнем регистре)., Маскирует ПДн в строках результата: по имени колонки, алиасу из query и по regex, test_scrub_error_detail_masks_and_truncates() (+34 more)

### Community 33 - "form.py"
Cohesion: 0.06
Nodes (53): Cols, _Bail, column_sources(), _Parser, Exception, Происхождение колонок текста запроса 1С для маскирования ПДн (issue #127).  Конс, Источники ИЗ: подзапросы и временные таблицы получают колонки., Разбор невозможен — вызывающий откатывается на прежнее поведение. (+45 more)

### Community 34 - "._do"
Cohesion: 0.11
Nodes (16): AuditWriter, OneCClient, Any, Безопасный фрагмент ошибки 1С для текста исключения (и для агента).          Без, GET-запрос к эндпоинту 1С с разбором JSON-ответа., POST-запрос к эндпоинту 1С с JSON-телом и разбором JSON-ответа.          HTTP-се, Одна попытка запроса; обновляет state для аудита.          Транспортные ошибки и, Пишет ровно одно событие one_c.http. Тело запроса/ответа не логируется. (+8 more)

### Community 35 - "test_bsl.py"
Cohesion: 0.05
Nodes (78): (cert, key) для https: явные файлы или самоподписанный CA в <cache_dir>/tls/., _resolve_tls(), _build_ca(), _build_leaf(), _bundle_valid(), _check_port(), ensure_self_signed(), _expires_within() (+70 more)

### Community 36 - ".__init__"
Cohesion: 0.14
Nodes (26): _attr_line(), format_object_structure(), Any, call(), Контракты инструментов: валидация URL-сегментов, filter, лимит вывода, экраниров, setup(), test_configuration_info_cells_are_escaped(), test_constant_type_is_rendered() (+18 more)

### Community 37 - "configuration_info.py"
Cohesion: 0.18
Nodes (12): filter_noise(), format_metadata_summary(), format_metadata_tree(), _is_noise(), AuditWriter, MCPServer, Инструмент get_metadata_tree: объекты конфигурации по категориям., Убирает автогенерируемые объекты из дерева метаданных. (+4 more)

### Community 38 - "dumpindex/__init__.py"
Cohesion: 0.14
Nodes (19): body_of(), function_body(), Статические гарды изменений Module.bsl (без запуска 1С)., Тело функции по точной сигнатуре (для хелперов без параметра Запрос)., test_constant_object_returns_its_type(), test_constant_type_is_mapped_in_metadata_lookup(), test_event_log_total_is_returned_count_and_found_is_separate(), test_eventlog_empty_body_means_empty_params_and_bad_limit_is_400() (+11 more)

### Community 39 - "pii.py"
Cohesion: 0.10
Nodes (36): CompletedProcess, main(), app_dir(), build_service_cmd(), _cmd_quote(), _current_pip_spec(), default_service_data_dir(), find_cache_dir() (+28 more)

### Community 40 - "test_metadata_reads_bsl_guard.py"
Cohesion: 0.22
Nodes (22): body_of(), call_args(), func_of(), Статичні гарди контрактних фіксів B12 (дати, пагінація, статуси, навігація).  BS, Позиційні аргументи виклику, що починається з позиції start (після дужки)., source(), test_configuration_mode_is_unknown_not_empty(), test_error_code_never_sits_in_reason_slot() (+14 more)

### Community 41 - "tls.py"
Cohesion: 0.11
Nodes (20): Chunk, chunk_module(), _embed(), embed_texts(), _embed_truncating(), endpoint(), _np(), _post() (+12 more)

### Community 42 - "_SyntheticBuild"
Cohesion: 0.16
Nodes (12): Event, Гонка close() проти потока-строителя DumpIndex (issue #56).  CI флат: сегфолт (e, Циклы «создать индекс → сразу закрыть» — как 4×create_server в protocol-тестах., close() не висит на _db_lock дольше таймаута и не теряет соединение.      Поток-, Индекс без реального dump: файлы и содержимое — синтетика в памяти.      `gate`, close() посреди долгой сборки ждёт поток, а не рвёт соединение под ним., Воспроизведение краша в CI (issue #56): close() во время count(*) в _finish_buil, _SyntheticBuild (+4 more)

### Community 43 - "ensure_self_signed"
Cohesion: 0.33
Nodes (3): HelpIndex, normalize(), Имена типов контекста (ru и en, casefold); пусто, пока индекс не готов.

### Community 44 - "access.py"
Cohesion: 0.15
Nodes (11): BaseException, Context, capabilities_failure_cause(), capabilities_failure_reason(), Шлёт tools/list_changed, если права разошлись с отданным списком.          Клиен, Есть ли у пользователя HTTP-метод (кэш /capabilities); для необязательных подска, 1С недоступна (не явный отказ), а техжурнал настроен., Код причины отказа `/capabilities` (`reason` из тела 1С), если он есть.      Без (+3 more)

### Community 45 - "test_dependency_bounds.py"
Cohesion: 0.22
Nodes (11): _dependency_specs(), Гарды на контракт зависимостей (issue #37, #49).  `mcp-baf-audit` пишет `audit.l, Имя пакета (нормализованное) -> список объявленных spec-строк., Все прямые импорты объявлены явно и с ожидаемыми границами., httpx/cryptography не должны «уехать» на мажор без ревью., certifi ниже 2026.10.23 несёт скомпрометированные промежуточные CA., _spec(), test_audit_dependency_has_upper_bound() (+3 more)

### Community 46 - "mask_pii_text"
Cohesion: 0.12
Nodes (11): _fake_install(), PID-файл, --stop, фон и установка службы (без реального Windows)., Окружение установки: ProgramFiles/ProgramData в tmp, subprocess и schtasks — заг, test_install_service_pip_failure_aborts(), test_install_service_refuses_raw_secrets(), test_install_service_requires_admin(), test_install_service_reuses_venv(), test_install_service_schtasks() (+3 more)

### Community 47 - "test_bsl_capabilities_guard.py"
Cohesion: 0.30
Nodes (10): body(), module_text(), Статичний гард Module.bsl і карт доступів.  BSL у pytest не виконується, тому ко, Тіло функції <name>(Запрос) без КонецФункции., test_eventlog_requires_admin_right_explicitly(), test_extensions_route_is_gone_and_capabilities_match_tools(), test_metadata_rights_accepts_english_and_russian_type_names(), test_method_available_keeps_out_param_and_reason_order() (+2 more)

### Community 48 - "test_tls_concurrency.py"
Cohesion: 0.27
Nodes (11): _body(), decode_html(), _number(), Path, Чтение HBK: адаптация контейнерного парсера rzateev/onec-help-mcp @ f66860b.  SP, Цепочка блоков контейнера; защита от циклов и неверных размеров., Выдаёт HTML-страницы FileStorage без извлечения файлов на диск., read_pages() (+3 more)

### Community 49 - "_scripted_install"
Cohesion: 0.18
Nodes (11): Гоняет _install_from; ответы _run_designer берутся по очереди из responses., _scripted_install(), test_install_compat_mode_chain_keeps_first_error(), test_install_default_run_mode_retry(), test_install_delete_and_retry_success(), test_install_delete_failure_raises(), test_install_reload_failure_after_delete_warns_loudly(), test_install_strip_not_applied_on_new_platform() (+3 more)

### Community 50 - "LockTimeout"
Cohesion: 0.18
Nodes (16): evaluate(), GoldItem, is_hit(), load_gold(), main(), method_ranges(), metrics(), open_index() (+8 more)

### Community 51 - "scrub_error_detail"
Cohesion: 0.21
Nodes (16): _account(), _candidate_files(), format_techlog(), _iter_events(), parse_props(), parse_window(), Any, datetime (+8 more)

### Community 52 - "test_https_transport.py"
Cohesion: 0.20
Nodes (5): HTMLParser, PageParser, parse_page(), test_html_sections_and_script_hidden(), test_table_cells_stay_separate_and_bad_bytes_do_not_fail()

### Community 53 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Architecture, Commands, Development workflow (owner's hard rules), graphify, New local tools and access control, What this is

### Community 54 - "Сумісність"
Cohesion: 0.25
Nodes (8): AI-клієнти, Origin за TLS-термінуючим проксі, Python, Версії платформи 1С, Далі, Додаткові локальні компоненти, Операційні системи, Сумісність

### Community 55 - "Архітектура"
Cohesion: 0.29
Nodes (7): HTTP-контракти, Архітектура, Аудит і HTTP-клієнт, Локальні компоненти, Модель прав: транспортна роль і права на дані, Реєстрація та доступ, Розширення та оновлення

### Community 56 - "._search_smart"
Cohesion: 0.14
Nodes (16): list, _extract_context(), _first_line_with_any(), Match, Matches, Список совпадений; `truncated` — скан прерван по бюджету времени., Одно совпадение поиска в BSL-модуле., Ищет совпадения в проиндексированных модулях. Диспетчер по mode. (+8 more)

### Community 57 - "register"
Cohesion: 0.11
Nodes (27): _check_env_key(), configure_pii(), mask_pii_value(), _parse_key_hex(), pii_token(), Any, Маскирование ПДн в ответах MCP-инструментов.  `--mask-pii` должен закрывать все, Маркер короче 3 символов («а») подстрокой маскирует почти все колонки. (+19 more)

### Community 58 - "Документація mcp-baf"
Cohesion: 0.33
Nodes (6): Версія, Довідники, Документація mcp-baf, Зміст, Початок роботи, Що варто знати одразу

### Community 59 - "file_lock"
Cohesion: 0.09
Nodes (27): extract_dcs_text(), is_dcs_candidate(), Pattern, Схемы компоновки данных (СКД) как псевдо-модули индекса и поиск использований., Текст запросов СКД или None, если файл — не схема / не разбирается., Все написания типа метаданных (ru/en, ед./мн.ч.), если token — одно из них., Regex ссылки `Тип.Имя` по всем написаниям типа и имя объекта для FTS-префильтра., type_aliases() (+19 more)

### Community 60 - "_recorder"
Cohesion: 0.33
Nodes (6): _recorder(), test_dump_base_only_single_call(), test_dump_dedupes_extension_names_case_insensitive(), test_dump_named_extension_dir_cleaned(), test_dump_rejects_path_in_extension_name(), test_dump_specific_extensions_into_subdirs()

### Community 61 - "Перелік інструментів"
Cohesion: 0.40
Nodes (5): Контракт помилок HTTP-сервісу 1С, Маскування ПДн (`--mask-pii`) — семантика токенів, Перелік інструментів, Промпти (11), Інструменти

### Community 62 - "_copy_extension_sources"
Cohesion: 0.50
Nodes (4): _copy_extension_sources(), test_localize_extension_keeps_bom(), test_localize_extension_ru_is_noop(), test_localize_extension_ua()

### Community 63 - "Локальна довідка та BSL"
Cohesion: 0.67
Nodes (3): Аналіз та форматування BSL, Довідка платформи, Локальна довідка та BSL

### Community 64 - "Джерела і ліцензії"
Cohesion: 0.67
Nodes (3): Джерела і ліцензії, Кандидати діагностик `bsl_analyze`, Походження за функціональними областями

### Community 66 - "_fake_run_with_log"
Cohesion: 0.67
Nodes (3): _fake_run_with_log(), test_run_designer_decodes_cp1251_log(), test_run_designer_strips_utf8_bom()

### Community 67 - "_timeout_run"
Cohesion: 0.67
Nodes (3): test_run_designer_timeout_env_override(), test_run_designer_timeout_reports_clear_error(), _timeout_run()

### Community 69 - "bsl/__init__.py"
Cohesion: 0.13
Nodes (11): Справочник встроенных функций 1С (порт bsl/functions.go).  Файл сгенерирован скр, Справочник встроенных функций языка 1С (BSL).  Порт пакета bsl из Go-версии. Дан, Ищет функции по имени (русскому или английскому), без учёта регистра., search(), Имена глобального контекста платформы для проверки UnknownGlobalCall.  Основа —, Удаляет временные файлы `<prefix>*` старше `max_age` секунд (сироты после SIGKIL, remove_stale(), build_synonym_map() (+3 more)

### Community 70 - "scrub_error_detail"
Cohesion: 0.16
Nodes (10): lex(), Собственный лексер BSL: двуязычные ключевые слова, строки и комментарии., Token, Базовый рекурсивный парсер BSL: конструкции управления и выражения.  Это собстве, #65: `#`/`&` не в начале строки не должны давать квадратичный разбор., test_lexer_hash_not_at_line_start_is_linear(), Узгодженість XML-джерел, прав, маршрутів і серверних обробників., test_access_right_calls_have_required_platform_arguments() (+2 more)

### Community 71 - "prompts.py"
Cohesion: 0.33
Nodes (4): Node, ParseFailure, Parser, Exception

### Community 72 - "register"
Cohesion: 0.20
Nodes (15): _branch_state(), _directives(), _inspect(), _is_mixed_script(), _preprocessor_dead_lines(), Собственные базовые проверки и консервативный форматер BSL на Python.  Никаких в, Рядки, які компілятор не компілює достовірно або ймовірно (dead/unknown)., Порт 1c-syntax/bsl-language-server#4905 (поведение, не код — LGPL).      Вызов И (+7 more)

### Community 73 - "_isolate_pii_state"
Cohesion: 0.12
Nodes (23): _default_host_names(), _http_security(), _origins(), _parse_dump_extensions(), Точка входа: mcp-baf --base <url> --user <user> --pass <password>., Режим --install: не зависит от серверной конфигурации и PII., Настраивает логирование.      MCP-клиенты показывают каждую строку stderr как [e, Хости, які сервер приймає за замовчуванням.      localhost/loopback + bind-хост (+15 more)

### Community 74 - "test_leftover_pid_temp_file_does_not_block_startup"
Cohesion: 0.22
Nodes (13): make_log(), Тесты разбора технологического журнала и source=techlog в get_event_log., test_budgets(), test_event_filter(), test_excp_grouped_without_guids(), test_mask_applied_to_context(), test_scan_aggregates_all_events(), test_scan_hour_file_events_and_multiline() (+5 more)

### Community 75 - "ConfigError"
Cohesion: 0.11
Nodes (20): _check_allowed_hosts(), _check_transport(), ConfigError, _env_bool(), _env_float(), _env_int(), _env_int_nonneg(), _env_secret() (+12 more)

### Community 76 - "_env_float"
Cohesion: 0.21
Nodes (8): fake_embed(), make_index(), Тесты гибридного поиска: чанкер, кэш векторов, RRF, реранкер (без сети)., Детерминированный «эмбеддинг»: слова про себестоимость -> ось 0, остальное -> ос, test_hybrid_fuses_and_reranker_fallback(), test_hybrid_while_vectors_building(), test_incremental_cache_embeds_only_new_chunks(), test_wait_vectors_returns_early_on_build_error()

### Community 77 - "_DripStream"
Cohesion: 0.22
Nodes (9): 1. Підготовка, 2. Розширення і `logcfg.xml`, 3. Встановлення служби, 4. Керування, 5. Підключення клієнтів, 6. Використання ТЖ, 7. Помилки й що з ними робити, Запуск у консолі й фон (+1 more)

### Community 78 - "test_preexisting_weak_key_file_perms_are_tightened"
Cohesion: 0.14
Nodes (10): MCP-инструменты сервера mcp-baf., call(), _client_for_status(), Контрактні фікси B12: дати/пагінація /query, підказки статусів, режим ІБ, форма., setup(), test_iso_dates_from_extension_pass_through_unchanged(), test_offset_above_cap_is_rejected_by_schema(), test_parameters_are_sent_as_is() (+2 more)

### Community 79 - "test_masking_note_qualified_for_columnless_tools"
Cohesion: 0.43
Nodes (7): _as_admin(), _logcfg_platform(), test_install_logcfg_as_admin_writes_and_creates_dir(), test_install_logcfg_existing_differs_is_not_overwritten(), test_install_logcfg_manual_when_not_admin_or_not_windows(), test_install_logcfg_same_ignoring_whitespace(), test_logcfg_conf_dir_default_and_conf_location()

### Community 80 - "parse_platform_version"
Cohesion: 0.18
Nodes (17): AccessMCP, MCPServer, Доступность HTTP-инструментов по эффективным правам пользователя сервиса., Скрывает недоступные инструменты и проверяет прямые вызовы., _denial(), Проверка list и прямых calls, обновление прав, отказ при недоступности сервиса., test_denial_contains_status_hint_not_body(), test_denial_contains_transport_cause_without_secrets() (+9 more)

### Community 81 - "newest_platform"
Cohesion: 0.17
Nodes (8): format_functions(), _Audit, _call_help(), Тесты справочника встроенных функций BSL и инструмента bsl_syntax_help., test_format_functions(), test_format_multiple_separated(), test_syntax_help_caps_results(), test_syntax_help_rejects_short_query()

### Community 82 - "classify_designer_error"
Cohesion: 0.18
Nodes (13): Collection, object_path_segments(), Валидирует тип и имя объекта и возвращает percent-encoded URL-сегменты., Проверяет имя объекта метаданных перед подстановкой в URL/путь., Проверяет тип объекта по белому списку поддерживаемых типов., validate_metadata_name(), validate_metadata_type(), AuditWriter (+5 more)

### Community 83 - "_run_http"
Cohesion: 0.15
Nodes (11): Popen, _BearerAuthASGI, ASGI-слой перед streamable-http: статический bearer-токен на каждый запрос., streamable-http (uvicorn) за bearer-слоем; TLS, если передан tls., _run_http(), Поток опроса консоли Windows; no-op вне интерактивной консоли., Запускает отсоединённую копию сервера с теми же аргументами., Атомарно пишет PID текущего процесса. (+3 more)

### Community 84 - "OneCError"
Cohesion: 0.18
Nodes (12): OneCError, Exception, Ошибка взаимодействия с 1С с понятным пользователю текстом., Транзиентная ошибка: идемпотентный запрос имеет смысл повторить., _RetryableOneCError, convert_dump_form(), form_from_dump(), merge_dump_into_form() (+4 more)

### Community 85 - "test_query_hints.py"
Cohesion: 0.36
Nodes (10): call(), Подсказки «возможно, вы имели в виду» и советник по тексту запроса., setup(), test_advisor_no_false_positives(), test_advisor_union_and_leading_percent(), test_execute_query_generic_error_points_to_validate(), test_hint_skipped_without_access(), test_validate_query_field_hint_resolves_alias() (+2 more)

### Community 86 - "test_traced.py"
Cohesion: 0.36
Nodes (8): last_event(), Тесты сквозного аудита вызовов инструментов (tools.common.traced_text).  В отлич, #78: текст запроса в audit.log обрезается всегда, при --mask-pii     литералы-ПД, test_query_text_in_audit_truncated_and_masked(), test_traced_text_keeps_index_state_text_for_client(), test_traced_text_logs_tool_error_on_exception(), test_traced_text_redacts_secret_args(), test_traced_text_returns_markdown_unchanged()

### Community 87 - "prompts.py"
Cohesion: 0.50
Nodes (3): MCPServer, MCP-prompts для типовых задач разработки 1С (порт prompts/prompts.go).  Каждый p, register()

## Knowledge Gaps
- **116 isolated node(s):** `docker-entrypoint.sh script`, `mcp-baf`, `What this is`, `Commands`, `Architecture` (+111 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `HTTP Audit Tests` to `CLI Entry Point & Config`, `Server Assembly & Config`, `1C HTTP Client`, `Object Structure Tool`, `Query Validation Tool`, `traced_text`, `test_objects.py`, `form.py`, `._do`, `test_bsl.py`, `.__init__`, `_isolate_pii_state`, `test_leftover_pid_temp_file_does_not_block_startup`, `ConfigError`, `test_preexisting_weak_key_file_perms_are_tightened`, `parse_platform_version`, `_run_http`, `OneCError`, `test_query_hints.py`, `.__init__`, `_DripStream`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `DumpIndex` connect `SQLite FTS5 Index Store` to `nfc`, `index.py`, `Index Disk Cache`, `tls.py`, `_SyntheticBuild`, `_env_float`, `Object Structure Tool`, `Query Validation Tool`, `LockTimeout`, `SearchParams`, `._search_smart`, `file_lock`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `OneCClient` connect `._do` to `form.py`, `.__init__`, `configuration_info.py`, `Server Assembly & Config`, `test_leftover_pid_temp_file_does_not_block_startup`, `1C HTTP Client`, `Metadata Tree Tool`, `Object Structure Tool`, `HTTP Audit Tests`, `parse_platform_version`, `Query Validation Tool`, `classify_designer_error`, `test_preexisting_weak_key_file_perms_are_tightened`, `test_query_hints.py`, `.__init__`, `_DripStream`, `test_objects.py`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `OneCClient` (e.g. with `AccessMCP` and `Config`) actually correct?**
  _`OneCClient` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `Config` (e.g. with `OneCClient` and `OneCError`) actually correct?**
  _`Config` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `DumpIndex` (e.g. with `VectorIndex` and `LockTimeout`) actually correct?**
  _`DumpIndex` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `SearchParams` (e.g. with `GoldItem` and `VectorIndex`) actually correct?**
  _`SearchParams` has 37 INFERRED edges - model-reasoned connections that need verification._