# mcp-baf

MCP-сервер для 1С:Предприятие на официальном SDK
([mcp](https://pypi.org/project/mcp/)) и [httpx](https://www.python-httpx.org/).
Python-порт [feenlace/mcp-1c](https://github.com/feenlace/mcp-1c) (Go, MIT):
те же инструменты, prompts, поиск по коду с дисковым кэшем и режим установки
расширения.

## Установка

```sh
python -m venv .venv
.venv\Scripts\pip install -e .          # Windows
# .venv/bin/pip install -e .            # Linux/macOS
```

## Запуск

```sh
mcp-baf --base http://localhost:8080/hs/mcp-1c --user admin --pass secret
```

Флаги и переменные окружения (флаг имеет приоритет; имена переменных
сохранены от Go-версии для совместимости конфигов):

| Флаг | Переменная окружения | По умолчанию |
|------|----------------------|--------------|
| `--base` | `MCP_1C_BASE_URL` | `http://localhost:8080/hs/mcp-1c` |
| `--user` | `MCP_1C_USER` | — |
| `--pass` / `--password` | `MCP_1C_PASSWORD` | — |
| `--dump` (включает search_code) | — | — |
| `--cache-dir` | `MCP_1C_CACHE_DIR` | платформенный кэш |
| `--reindex` (пересборка кэша индекса) | — | — |
| `--max-response-size` (MiB) | `MCP_1C_MAX_RESPONSE_SIZE` | 128 |
| `--request-timeout` (сек) | `MCP_1C_REQUEST_TIMEOUT` | 300 |
| `--debug` (INFO-лог в server.log) | — | — |
| `--quiet` / `--verbose` (прогресс на stderr) | `MCP_1C_NO_TTY=1` | автоопределение TTY |

## Подключение к Claude Code

```sh
claude mcp add baf-1c \
  --env MCP_1C_USER='Администратор' \
  --env MCP_1C_PASSWORD='пароль' \
  -- /путь/к/.venv/bin/mcp-baf \
  --base http://сервер/база/hs/mcp-1c \
  --dump /путь/к/выгрузке
```

## Установка расширения в базу 1С

```sh
mcp-baf --install "C:\путь\к\базе"                 # файловая база
mcp-baf --install "server\database" --server       # клиент-серверная
```

Дополнительно: `--platform` (путь к 1cv8.exe, иначе автопоиск),
`--platform-version` (например 8.3.13, если не определяется из пути),
`--db-user` / `--db-password` (пользователь базы для DESIGNER).
XML-исходники расширения встроены в пакет; перед загрузкой они патчатся
под версию целевой платформы (формат выгрузки, режим совместимости,
неподдерживаемые элементы) с цепочкой повторов под ошибки старых платформ.

## Структура

```
src/mcp_baf/
  __main__.py     — точка входа (CLI, stdio-транспорт, режим --install)
  config.py       — флаги и переменные окружения
  client.py       — асинхронный HTTP-клиент к 1С (httpx)
  server.py       — сборка FastMCP, регистрация инструментов, проверка
                    версии расширения при старте
  prompts.py      — 11 MCP-prompts для типовых задач разработки 1С
  installer.py    — установка расширения через DESIGNER
  extension_src/  — XML-исходники расширения 1С
  tools/          — MCP-инструменты (по одному модулю на инструмент)
  dumpindex/      — поиск по dump-выгрузке: индекс SQLite FTS5 с дисковым
                    кэшем и инкрементальным обновлением, разбор Form.xml
  bsl/            — справочник встроенных функций 1С
scripts/
  e2e_check.py    — ручная e2e-проверка (нужен mock-1c из Go-версии)
  gen_bsl_data.py — регенерация справочника функций из bsl/functions.go
                    Go-версии: python scripts/gen_bsl_data.py <путь>
tests/            — pytest-тесты (python -m pytest tests)
```

## Инструменты

- `get_metadata_tree` — объекты конфигурации по категориям (GET `/metadata`).
- `get_object_structure` — реквизиты и структура объекта (GET `/object/{type}/{name}`).
- `execute_query` — выполнение запроса ВЫБРАТЬ/SELECT (POST `/query`).
- `get_form_structure` — структура формы (GET `/form/{type}/{name}`; с `--dump`
  состав элементов, команды и обработчики обогащаются из Form.xml выгрузки).
- `validate_query` — проверка синтаксиса запроса (POST `/validate-query`).
- `get_event_log` — журнал регистрации (POST `/eventlog`).
- `get_configuration_info` — общая информация о базе 1С (GET `/configuration`).
- `search_code` — полнотекстовый поиск по коду модулей (только с `--dump`).
- `bsl_syntax_help` — справочник 180 встроенных функций языка 1С (локальный,
  без HTTP-запросов).

Плюс 11 prompts: review_module, write_posting, optimize_query, explain_config,
analyze_error, find_duplicates, write_report, explain_object, 1c_query_syntax,
1c_metadata_navigation, 1c_development_workflow.

### search_code

Поиск работает по локальной выгрузке конфигурации (`DumpConfigToFiles`).
Индекс — SQLite FTS5: при первом старте сервер в фоновом потоке рекурсивно
обходит директорию `--dump`, параллельно читает `.bsl` файлы
(ThreadPoolExecutor) и строит индекс; до готовности поиск возвращает
«search index is building, please retry». База сохраняется в кэш-каталоге
(имя — sha256 от пути выгрузки) и на следующих стартах открывается мгновенно:
изменённые/новые/удалённые файлы определяются по mtime+size и применяются
инкрементально. `--reindex` принудительно пересобирает кэш; битый кэш
пересобирается автоматически.

Режимы: `smart` (BM25 с двуязычными BSL-синонимами — StrFind находит
СтрНайти), `regex` (Python `re`), `exact` (подстрока). Отличие от Go-версии:
синтаксис regex — Python, а не Go.

## Лицензия

MIT, см. [LICENSE](LICENSE). Порт Go-проекта
[feenlace/mcp-1c](https://github.com/feenlace/mcp-1c) (MIT).
