# Graph Report - mcp-baf  (2026-11-14)

## Corpus Check
- 90 files · ~86,516 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1434 nodes · 2932 edges · 69 communities (65 shown, 4 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 155 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `58e428ba`
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

## God Nodes (most connected - your core abstractions)
1. `OneCClient` - 62 edges
2. `Config` - 51 edges
3. `DumpIndex` - 48 edges
4. `load_config()` - 39 edges
5. `SearchParams` - 36 edges
6. `traced_text()` - 34 edges
7. `parse_args()` - 33 edges
8. `create_server()` - 28 edges
9. `discover_extension_roots()` - 27 edges
10. `ensure_self_signed()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `test_failed_extension_exits_1()` --calls--> `_run_dump()`  [INFERRED]
  tests/test_main.py → src/mcp_baf/__main__.py
- `test_is_loopback_bind_covers_ipv4_loopback_and_falls_back()` --calls--> `_is_loopback_bind()`  [INFERRED]
  tests/test_main.py → src/mcp_baf/__main__.py
- `_settings()` --calls--> `_http_security()`  [INFERRED]
  tests/test_main.py → src/mcp_baf/__main__.py
- `_DripStream` --uses--> `OneCClient`  [INFERRED]
  tests/test_client.py → src/mcp_baf/client.py
- `_DripStream` --uses--> `Config`  [INFERRED]
  tests/test_client.py → src/mcp_baf/config.py

## Import Cycles
- None detected.

## Communities (69 total, 4 thin omitted)

### Community 0 - "MCP Tool Registration Helpers"
Cohesion: 0.15
Nodes (13): Асинхронный HTTP-клиент для общения с 1С:Предприятие., _check_transport(), Конфигурация MCP-сервера.  Приоритет источников (от низшего к высшему): значения, Сетевой транспорт: только с токеном, plain http — только с явным opt-in., _version(), format_event_log(), Any, Инструмент get_event_log: чтение журнала регистрации 1С. (+5 more)

### Community 1 - "1C Extension Installer"
Cohesion: 0.05
Nodes (63): Имя каталога не может принадлежать расширению (каталог «вида»,     стандартный к, _rejected_dir_name(), _build_designer_args(), classify_designer_error(), _designer_log_is_fatal(), designer_timeout(), dump(), _error_contains() (+55 more)

### Community 2 - "nfc"
Cohesion: 0.07
Nodes (62): NamedTuple, Расположение дискового кэша индекса (порт dump/cache.go).  Кэш каждой dump-выгру, Удаляет временные файлы `<prefix>*` старше `max_age` секунд (сироты после SIGKIL, remove_stale(), discover_extension_roots(), _list_dirs(), _manifest_name(), Поиск вложенных кореньев расширений в dump-выгрузке.  Порт поведения feenlace/mc (+54 more)

### Community 3 - "index.py"
Cohesion: 0.16
Nodes (14): Match, Одно совпадение поиска в BSL-модуле., Индекс полнотекстового поиска по dump-выгрузке конфигурации 1С., clamp_limit(), Нормализует пользовательский limit к диапазону [default, maximum]., format_search_result(), AuditWriter, MCPServer (+6 more)

### Community 5 - "1C Form XML Parser"
Cohesion: 0.09
Nodes (45): _descend_into_child_items(), display_type(), find_form_files(), FormCommandInfo, FormElementInfo, FormHandlerInfo, FormInfo, _local() (+37 more)

### Community 6 - "SQLite FTS5 Index Store"
Cohesion: 0.14
Nodes (8): Connection, DumpIndex, Exception, Индекс поиска по коду модулей из dump-выгрузки конфигурации.      Строится асинх, Создаёт схему и наполняет базу пачками по BUILD_BATCH модулей.          Содержим, Атомарно подменяет index.db собранным временным файлом.          На POSIX os.rep, Открывает кэш и инкрементально применяет изменения файлов., Удаляет документ из FTS5 с внешним содержимым.          Команде 'delete' нужно с

### Community 7 - "CLI Entry Point & Config"
Cohesion: 0.05
Nodes (70): Namespace, ConfigError, _env_bool(), _env_float(), _env_int(), _env_int_nonneg(), _env_secret(), load_config() (+62 more)

### Community 8 - "Index Disk Cache"
Cohesion: 0.17
Nodes (26): cache_path(), index_db_path(), Каталог кэша индекса для данной dump-выгрузки., _assert_db_intact(), build(), mk_bsl(), _mk_dump(), Тесты дискового кэша индекса и инкрементального обновления. (+18 more)

### Community 9 - "Server Assembly & Config"
Cohesion: 0.09
Nodes (22): MCP-сервер для чтения BAF, поиска справки и анализа BSL., MCPServer, MCP-prompts для типовых задач разработки 1С (порт prompts/prompts.go).  Каждый p, register(), _check_extension_version(), create_server(), MCPServer, Сборка MCP-сервера: создание MCPServer и регистрация инструментов. (+14 more)

### Community 10 - "Form Structure Tool"
Cohesion: 0.13
Nodes (18): escape_pipe(), Экранирует вертикальную черту, чтобы не ломать markdown-таблицы., format_configuration_info(), Any, format_form_structure(), Форматирует структуру формы; при mask_pii свободный текст маскируется.      Заго, format_references(), parse_link() (+10 more)

### Community 11 - "1C HTTP Client"
Cohesion: 0.08
Nodes (25): format_cell(), Any, Преобразует значение ячейки JSON-ответа в строку для markdown-таблицы., call(), _client_for_status(), Контрактні фікси B12: дати/пагінація /query, підказки статусів, режим ІБ, форма., setup(), test_iso_dates_from_extension_pass_through_unchanged() (+17 more)

### Community 12 - "Metadata Tree Tool"
Cohesion: 0.14
Nodes (15): filter_noise(), format_metadata_summary(), format_metadata_tree(), _is_noise(), load_tree(), Any, AuditWriter, MCPServer (+7 more)

### Community 13 - "Form Parser Tests"
Cohesion: 0.13
Nodes (6): parse_fixture(), Тесты разбора Form.xml.  Фикстуры в testdata/ — реальные файлы dump-выгрузки 1С, test_catalog_list_form(), test_common_form_password(), test_empty_form(), test_register_record_form()

### Community 14 - "Object Structure Tool"
Cohesion: 0.09
Nodes (28): Collection, Анализ и форматирование переданного текста без изменения исходников., register(), object_path_segments(), Общие помощники для MCP-инструментов., Валидирует тип и имя объекта и возвращает percent-encoded URL-сегменты., Обрезает вывод по лимиту, сохраняя целые строки и явную пометку., Проверяет имя объекта метаданных перед подстановкой в URL/путь. (+20 more)

### Community 15 - "HTTP Audit Tests"
Cohesion: 0.13
Nodes (33): AsyncBaseTransport, AuditLog, AccessMCP, AuditWriter, MCPServer, Скрывает недоступные инструменты и проверяет прямые вызовы., OneCClient, AuditWriter (+25 more)

### Community 16 - "Query Validation Tool"
Cohesion: 0.15
Nodes (13): audit_text(), Свободный текст (запрос) для args аудита: при --mask-pii маскируется,     всегда, Поиск справки в локальном индексе HBK., register(), query_keyword(), Инструмент execute_query: выполнение запроса 1С (только чтение)., Первое ключевое слово запроса — без комментариев и ведущих пробелов.      Провер, format_validate_result() (+5 more)

### Community 17 - "Manual E2E Check Script"
Cohesion: 0.47
Nodes (5): main(), make_dump(), Path, Ручная e2e-проверка: запускает сервер по stdio и вызывает все инструменты.  Испо, Создаёт миниатюрную dump-выгрузку для проверки search_code и форм.

### Community 18 - "BSL Data Generator Script"
Cohesion: 0.67
Nodes (3): main(), Генерирует mcp_baf/bsl/_functions_data.py из bsl/functions.go (Go-версия).  Извл, unquote_go()

### Community 19 - "SearchParams"
Cohesion: 0.12
Nodes (32): SearchParams, index(), mk_bsl(), mk_manifest(), Тесты индекса поиска по dump-выгрузке (SQLite FTS5)., #61: `(\\w\\w|\\w)+!` не ловится эвристикой вложенных кванторов, но     должен п, Режимы regex/exact не тянут весь код модулей через fetchall()., Во время скана замок свободен: другой поиск и close() не блокируются. (+24 more)

### Community 20 - "Async Transport Stub"
Cohesion: 0.05
Nodes (66): analyze(), _branch_state(), _directives(), format_source(), _inspect(), _is_mixed_script(), _preprocessor_dead_lines(), Собственные базовые проверки и консервативный форматер BSL на Python.  Никаких в (+58 more)

### Community 22 - "HelpIndex"
Cohesion: 0.06
Nodes (47): HTMLParser, Pattern, Справочник встроенных функций 1С (порт bsl/functions.go).  Файл сгенерирован скр, Справочник встроенных функций языка 1С (BSL).  Порт пакета bsl из Go-версии. Дан, Ищет функции по имени (русскому или английскому), без учёта регистра., search(), Платформенный каталог кэша пользователя (аналог os.UserCacheDir в Go)., user_cache_dir() (+39 more)

### Community 24 - "traced_text"
Cohesion: 0.09
Nodes (34): _is_loopback_bind(), True для loopback-bind: уся петля 127.0.0.0/8, ::1 і `localhost`.      Рядкового, Режим установки и справка CLI не должны импортировать MCP-сервер., Функциональная проверка тем же middleware, что использует SDK., `--http-allowed-hosts mcp-baf` не должен превращать сервис в 421., Для 80/443 браузер шлёт Origin без порту — додаємо й такий варіант., Порожній список — поведінка #27: типові хости з портом і `:*`., 127.0.0.2 — теж loopback (127.0.0.0/8), захист має бути увімкнений. (+26 more)

### Community 25 - "mcp-baf"
Cohesion: 0.11
Nodes (19): 1. Встановити, 2. Встановити розширення в 1С, 3. Запустити HTTP-сервіс 1С, 4. Налаштувати AI-клієнт, `audit.log` — журнал подій (JSONL), mcp-baf, `server.log` — операційний журнал, Доступні інструменти (+11 more)

### Community 26 - "test_objects.py"
Cohesion: 0.10
Nodes (23): format_functions(), MCP-инструменты сервера mcp-baf., _Audit, _call_help(), Тесты справочника встроенных функций BSL и инструмента bsl_syntax_help., test_format_functions(), test_format_multiple_separated(), test_syntax_help_caps_results() (+15 more)

### Community 27 - "Швидкий старт"
Cohesion: 0.12
Nodes (17): Вимоги, Встановлення, Далі, Крок 1. Встановити пакет, Крок 2. Встановити розширення в базу 1С, Крок 3. Опублікувати HTTP-сервіс, Крок 4. Налаштувати AI-клієнт, Крок 5. Перевірити (+9 more)

### Community 28 - "Пошук по коду та індекс"
Cohesion: 0.11
Nodes (18): `exact` — точний підрядок, `regex` — регулярний вираз, `smart` — BM25 + синоніми, Версія схеми, Дивіться також, Дисковий кеш, Завершення роботи (issue #56), Неблокуючий старт (+10 more)

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
Cohesion: 0.09
Nodes (22): mask_pii_result(), Маскирует ПДн в строках результата: по имени колонки, алиасу из query и по regex, _audit_events(), _isolate_pii_state(), _r(), Тесты маскирования ПДн в execute_query и подсистемы --mask-pii (#53)., Глобальное состояние pii (ключ, маркеры) не течёт между тестами., MINOR реві #53: валідація mcp_baf_PII_KEY на старті, значення не витекає. (+14 more)

### Community 33 - "form.py"
Cohesion: 0.11
Nodes (39): _client(), _events(), _flaky_handler(), Тесты аудита HTTP-вызовов 1С: ровно одно событие one_c.http на запрос, разделённ, Отдаёт responses по порядку; исключения из списка поднимает как есть., #79: тіло не-200 читається лише до 4 КиБ, а не повністю., #78: при --mask-pii фраза-заглушка лише для тіла відповіді 1С;     причину мереж, WriteTimeout — той самий клас, що й ReadTimeout: ярлик timeout, без повтора. (+31 more)

### Community 34 - "._do"
Cohesion: 0.12
Nodes (13): OneCError, Any, Exception, Безопасный фрагмент ошибки 1С для текста исключения (и для агента).          Без, GET-запрос к эндпоинту 1С с разбором JSON-ответа., POST-запрос к эндпоинту 1С с JSON-телом и разбором JSON-ответа.          HTTP-се, Одна попытка запроса; обновляет state для аудита.          Транспортные ошибки и, Пишет ровно одно событие one_c.http. Тело запроса/ответа не логируется. (+5 more)

### Community 35 - "test_bsl.py"
Cohesion: 0.18
Nodes (27): _assert_bundle_consistent(), _digest(), _fresh_enough(), _load_ca_key(), _load_cert(), _make_ca(), Перевыпуск серверного листа по notAfter (issue #37).  Лист живёт 825 дней, но `e, Комплект от версии без ca.key: лист перевыпустить нечем → новый CA. (+19 more)

### Community 36 - ".__init__"
Cohesion: 0.19
Nodes (21): call(), Контракты инструментов: валидация URL-сегментов, filter, лимит вывода, экраниров, setup(), test_configuration_info_cells_are_escaped(), test_constant_type_is_sent_to_object_endpoint(), test_form_name_is_sent_as_query_param(), test_form_rejects_bad_url_segments(), test_form_without_form_name_has_no_form_query() (+13 more)

### Community 37 - "configuration_info.py"
Cohesion: 0.18
Nodes (15): AuditWriter, Выполняет инструмент со сквозным аудитом и возвращает его текст как есть.      А, traced_text(), AuditWriter, MCPServer, Инструмент get_configuration_info: общая информация о базе 1С., register(), last_event() (+7 more)

### Community 38 - "dumpindex/__init__.py"
Cohesion: 0.15
Nodes (19): body_of(), function_body(), Статические гарды изменений Module.bsl (без запуска 1С)., Тело функции по точной сигнатуре (для хелперов без параметра Запрос)., test_constant_object_returns_its_type(), test_constant_type_is_mapped_in_metadata_lookup(), test_event_log_total_is_returned_count_and_found_is_separate(), test_eventlog_empty_body_means_empty_params_and_bad_limit_is_400() (+11 more)

### Community 39 - "pii.py"
Cohesion: 0.14
Nodes (21): _check_env_key(), configure_pii(), _is_pii_name(), _parse_key_hex(), _pii_aliases(), Маскирование ПДн в ответах MCP-инструментов.  `--mask-pii` должен закрывать все, Маркер короче 3 символов («а») подстрокой маскирует почти все колонки., Разбирает CSV-строку маркеров (env/CLI) в кортеж нижнего регистра. (+13 more)

### Community 40 - "test_metadata_reads_bsl_guard.py"
Cohesion: 0.25
Nodes (18): body_of(), call_args(), func_of(), Статичні гарди контрактних фіксів B12 (дати, пагінація, статуси, навігація).  BS, Позиційні аргументи виклику, що починається з позиції start (після дужки)., source(), test_configuration_mode_is_unknown_not_empty(), test_error_code_never_sits_in_reason_slot() (+10 more)

### Community 41 - "tls.py"
Cohesion: 0.18
Nodes (16): datetime, _build_ca(), _build_leaf(), _expires_within(), _generate(), _leaf_san(), TLS для https-транспорту: свої cert/key або самопідписаний CA у каталозі.  Без я, Имена из SAN листа (DNS и IP); None — нет SAN или битый файл. (+8 more)

### Community 42 - "_SyntheticBuild"
Cohesion: 0.16
Nodes (12): Event, Гонка close() проти потока-строителя DumpIndex (issue #56).  CI флат: сегфолт (e, Циклы «создать индекс → сразу закрыть» — как 4×create_server в protocol-тестах., close() не висит на _db_lock дольше таймаута и не теряет соединение.      Поток-, Индекс без реального dump: файлы и содержимое — синтетика в памяти.      `gate`, close() посреди долгой сборки ждёт поток, а не рвёт соединение под ним., Воспроизведение краша в CI (issue #56): close() во время count(*) в _finish_buil, _SyntheticBuild (+4 more)

### Community 43 - "ensure_self_signed"
Cohesion: 0.16
Nodes (16): (cert, key) для https: явные файлы или самоподписанный CA в <cache_dir>/tls/., _resolve_tls(), _bundle_valid(), ensure_self_signed(), True, если SAN листа покрывает все текущие `hosts`.      Комплект может быть свя, (ca.crt, server.crt, server.key) у directory; генерує або перевипускає лист., Ім'я для SAN: `[::1]:8001` -> `::1` (дужки й порт у SAN не потрапляють)., SAN за замовчуванням: localhost, loopback і hostname контейнера/хоста. (+8 more)

### Community 44 - "access.py"
Cohesion: 0.20
Nodes (8): BaseException, Context, capabilities_failure_reason(), Доступность HTTP-инструментов по эффективным правам пользователя сервиса., Код причины отказа `/capabilities` (`reason` из тела 1С), если он есть.      Без, Убирает автогенерированные pydantic'ом "title" из JSON-схемы.      Смысла для мо, Шлёт tools/list_changed, если права разошлись с отданным списком.          Клиен, strip_schema_titles()

### Community 45 - "test_dependency_bounds.py"
Cohesion: 0.22
Nodes (11): _dependency_specs(), Гарды на контракт зависимостей (issue #37, #49).  `mcp-baf-audit` пишет `audit.l, Имя пакета (нормализованное) -> список объявленных spec-строк., Все прямые импорты объявлены явно и с ожидаемыми границами., httpx/cryptography не должны «уехать» на мажор без ревью., certifi ниже 2026.10.23 несёт скомпрометированные промежуточные CA., _spec(), test_audit_dependency_has_upper_bound() (+3 more)

### Community 46 - "mask_pii_text"
Cohesion: 0.23
Nodes (12): mask_pii_text(), mask_pii_value(), pii_token(), Any, Стабильный в пределах ключа токен вместо значения (HMAC-SHA256)., Заменяет телефон/email на repl(match), идентификатороподобные токены     (GUID,, Маскирует значение: непустые строки — по regex, остальное как есть., Маскирует свободный текст (None -> пустая строка) по regex ПДн.      Используетс (+4 more)

### Community 47 - "test_bsl_capabilities_guard.py"
Cohesion: 0.30
Nodes (10): body(), module_text(), Статичний гард Module.bsl і карт доступів.  BSL у pytest не виконується, тому ко, Тіло функції <name>(Запрос) без КонецФункции., test_eventlog_requires_admin_right_explicitly(), test_extensions_route_is_gone_and_capabilities_match_tools(), test_metadata_rights_accepts_english_and_russian_type_names(), test_method_available_keeps_out_param_and_reason_order() (+2 more)

### Community 48 - "test_tls_concurrency.py"
Cohesion: 0.30
Nodes (11): _assert_bundle_consistent(), _child_env(), _digest(), Гонка генерации самоподписанного TLS-комплекта (issue #26).  Два процесса/потока, ca.crt от чужого процесса (не подписывает server.crt) — перегенерация., ca.crt подписывает server.crt, а server.key — пара к server.crt., test_concurrent_processes_share_one_bundle(), test_concurrent_threads_share_one_bundle() (+3 more)

### Community 49 - "_scripted_install"
Cohesion: 0.18
Nodes (11): Гоняет _install_from; ответы _run_designer берутся по очереди из responses., _scripted_install(), test_install_compat_mode_chain_keeps_first_error(), test_install_default_run_mode_retry(), test_install_delete_and_retry_success(), test_install_delete_failure_raises(), test_install_reload_failure_after_delete_warns_loudly(), test_install_strip_not_applied_on_new_platform() (+3 more)

### Community 50 - "LockTimeout"
Cohesion: 0.20
Nodes (9): list, _FileState, Matches, Список совпадений; `truncated` — скан прерван по бюджету времени., Состояние одного .bsl файла на диске (для diff манифеста)., Собирает состояние всех .bsl файлов: rel_path -> (путь, mtime, size)., LockTimeout, Лок не удалось взять за отведённое время. (+1 more)

### Community 51 - "scrub_error_detail"
Cohesion: 0.22
Nodes (9): Маскирует ПДн и обрезает тело ошибки 1С до безопасной длины., scrub_error_detail(), test_scrub_error_detail_masks_and_truncates(), Прибрати токени PII:<8 hex>, щоб перевіряти «сирі» ПДн поза токенами.      Хеш-т, Рішення #53 п.5: голий 10-значний прогін із провідним нулем маскується як     те, _strip_tokens(), test_bare_ten_digit_zero_prefix_is_accepted_overmasking(), test_error_detail_scrub_keeps_guids() (+1 more)

### Community 52 - "test_https_transport.py"
Cohesion: 0.31
Nodes (7): _load(), https-транспорт: токен обязателен, plain http — двойной opt-in, TLS c генерируем, SAN для `[::1]:8001` — IP `::1`, а не DNS `[`; порт в SAN не потрапляє., test_network_transport_guards(), test_self_signed_hosts_strips_ipv6_brackets_and_port(), test_stdio_is_default_and_needs_no_token(), test_transport_options_from_env()

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
Cohesion: 0.33
Nodes (4): _extract_context(), Ищет совпадения в проиндексированных модулях. Диспетчер по mode., Полнотекстовый поиск с BM25-ранжированием через FTS5., Построчный поиск (режимы regex и exact).          Содержимое берётся пачками, ве

### Community 57 - "register"
Cohesion: 0.29
Nodes (7): AuditWriter, MCPServer, register(), _captured_tool_kwargs(), Кожен інструмент із mask-aware formatter зобов'язаний отримувати     config.mask, test_registry_invariant_all_maskable_tools_pass_mask_pii(), test_tool_descriptions_document_token_semantics()

### Community 58 - "Документація mcp-baf"
Cohesion: 0.33
Nodes (6): Версія, Довідники, Документація mcp-baf, Зміст, Початок роботи, Що варто знати одразу

### Community 59 - "file_lock"
Cohesion: 0.47
Nodes (5): file_lock(), Межпроцессная файловая блокировка для общих файлов кэша.  Нужна там, где два про, Эксклюзивный лок на файле `path` (файл создаётся при необходимости).      `timeo, _try_lock(), _unlock()

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

## Knowledge Gaps
- **104 isolated node(s):** `docker-entrypoint.sh script`, `mcp-baf`, `What this is`, `Commands`, `Architecture` (+99 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `HTTP Audit Tests` to `MCP Tool Registration Helpers`, `form.py`, `._do`, `.__init__`, `CLI Entry Point & Config`, `Server Assembly & Config`, `ensure_self_signed`, `1C HTTP Client`, `traced_text`, `test_objects.py`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `create_server()` connect `Server Assembly & Config` to `index.py`, `configuration_info.py`, `SQLite FTS5 Index Store`, `CLI Entry Point & Config`, `Form Structure Tool`, `Metadata Tree Tool`, `Object Structure Tool`, `HTTP Audit Tests`, `Query Validation Tool`, `HelpIndex`, `register`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `DumpIndex` connect `SQLite FTS5 Index Store` to `nfc`, `index.py`, `Index Disk Cache`, `Server Assembly & Config`, `_SyntheticBuild`, `LockTimeout`, `SearchParams`, `._search_smart`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `OneCClient` (e.g. with `AccessMCP` and `Config`) actually correct?**
  _`OneCClient` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `Config` (e.g. with `OneCClient` and `OneCError`) actually correct?**
  _`Config` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `DumpIndex` (e.g. with `LockTimeout` and `build()`) actually correct?**
  _`DumpIndex` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `SearchParams` (e.g. with `LockTimeout` and `test_cache_reused_and_search_works()`) actually correct?**
  _`SearchParams` has 29 INFERRED edges - model-reasoned connections that need verification._