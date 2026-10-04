# Розробка

[← Назад до змісту](README.md)

## Встановлення

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev]"          # Linux / macOS
# .venv\Scripts\pip install -e ".[dev]"    # Windows
```

Python **3.11+**. Прямі залежності: `mcp>=2.3,<3`, `httpx>=0.27`,
`mcp-baf-audit>=0.2.1`. З dev-екстри ставиться лише `pytest`.

Використовується офіційний MCP SDK **2.x**: `MCPServer` і `Context` з
`mcp.server.mcpserver`, клієнт `mcp.Client`. Python-поля мають snake_case:
`ToolAnnotations(read_only_hint=True)`, `CallToolResult.is_error`,
`Tool.input_schema`. У JSON протоколу зберігаються `readOnlyHint`, `isError`,
`inputSchema`; для серіалізації моделей потрібен `model_dump(by_alias=True)`.
`AccessMCP.call_tool` передає контекст запиту до базового класу, а очікувані
помилки BAF і параметрів перетворюються на `ToolError` з поясненням для клієнта.

### Сусідній репозиторій mcp-baf-audit

`mcp-baf-audit` — спільна бібліотека аудиту (JSONL, schema v2), окремий репозиторій
і пакет на PyPI. У локальній розробці ставиться з сусіднього каталогу:

```sh
.venv/bin/pip install -e ../mcp-baf-audit
```

Релізи пінить git-тегом:

```sh
pip install "git+<repo>/mcp-baf-audit.git@v0.2.1"
```

> Залежність **односпрямована**: mcp-baf залежить від mcp-baf-audit, ніколи навпаки.

## Тести

```sh
.venv/bin/python -m pytest tests                                        # усі
.venv/bin/python -m pytest tests/test_server.py::test_registered_tools  # один
```

| Файл | Що покриває |
|---|---|
| `test_config.py` | Пріоритет defaults → env → CLI |
| `test_client.py` | `OneCClient`: auth, ліміт розміру, помилки |
| `test_server.py` | Реєстрація тулів (зокрема: без `--dump` немає `search_code`) |
| `test_protocol.py` | SDK 2: JSON-схеми, 11 промптів, помилки, stdio у сучасному та legacy режимах |
| `test_access.py` | Фільтрація list/call, зміна прав, контекст запиту, аудит відмов |
| `test_dumpindex.py` | Побудова індексу, режими пошуку |
| `test_cache.py` | Дисковий кеш, шляхи, інкрементальний diff |
| `test_modulenames.py` | NFC-нормалізація, розбір імен модулів |
| `test_formparser.py` | Розбір `Form.xml` з вивантаження |
| `test_installer.py` | Патчі XML під версії платформи |
| `test_bsl.py` | Довідник BSL |
| `test_traced.py` | `traced_text`, події аудиту, `trace_id` |

> Автоформатера Python у проєкті немає. MCP-інструменти `bsl_analyze`/`bsl_format` використовують власний Python-аналізатор і не переписують код репозиторію.

### Тести й змінні оточення

`load_config` читає env, тому тести на дефолти чутливі до оточення розробника.
Новий тест на дефолтне значення має явно чистити свою змінну:

```python
def test_dump_dir_default_empty(monkeypatch):
    monkeypatch.delenv("mcp_baf_DUMP_DIR", raising=False)
    ...
```

Інакше виставлений у shell `mcp_baf_*` протече в асерт і тест впаде тільки в
когось одного. `test_server.py` цієї проблеми не має — він конструює `Config()`
напряму, повз `load_config`.

### E2E

`scripts/e2e_check.py --base http://host/base/hs/mcp-baf` — ручна перевірка MCP через stdio з розширенням 0.5.6. Облікові дані читаються зі звичайних `mcp_baf_USER`/`mcp_baf_PASSWORD`. Скрипт пропускає недоступні інструменти і показує це явно. Для локальної контрактної перевірки запускайте pytest: нові HTTP-маршрути покриті MockTransport, довідка — власною HBK-фікстурою, BSL — власними двомовними прикладами, помилковими фрагментами, перевірками збереження токенів і приватності. Python-аналітика не замінює live-компіляцію BSL на платформі.

## Структура

```
src/mcp_baf/
├── __main__.py        точка входу: --install або сервер на stdio
├── server.py          create_server, порядок реєстрації, EXPECTED_EXTENSION_VERSION
├── config.py          defaults → env → CLI
├── access.py          перевірка capabilities, фільтрація list/call
├── bsl_native/        Python-лексер, парсер, базові перевірки та відступи
├── helpindex/         HBK → кешований SQLite FTS5
├── client.py          OneCClient (httpx)
├── installer.py       завантаження розширення через DESIGNER
├── prompts.py         11 MCP-промптів
├── tools/             по модулю на тул + common.py (traced_text)
├── dumpindex/         SQLite FTS5-індекс, кеш, синоніми, NFC
├── bsl/               довідник BSL (_functions_data.py — генерований)
└── extension_src/     XML-вивантаження розширення 1С
```

## Згенерований код

`src/mcp_baf/bsl/_functions_data.py` — довідник BSL для `bsl_syntax_help`.
**Руками не правити.** Генерується з Go-репо:

```sh
python scripts/gen_bsl_data.py <шлях/до/functions.go>
```

## Розширення 1С

Джерела розширення — `src/mcp_baf/extension_src/` (XML config-dump, шиплються
всередині пакета). `installer.py` копіює їх у тимчасовий каталог, патчить XML під
цільову версію платформи й вантажить через DESIGNER `/LoadConfigFromFiles`.

> ### Правило синхронізації версій
>
> При **будь-якій** зміні `extension_src/` піднімай **обидва** значення:
>
> | Що | Де |
> |---|---|
> | Версія розширення | `extension_src/HTTPServices/MCPService/Ext/Module.bsl` — коментар у шапці **і** рядок `Результат.Вставить("version", ...)` |
> | Очікувана версія | `server.py:EXPECTED_EXTENSION_VERSION` |
>
> Зараз обидва — `0.5.6`.

Сервер звіряє їх на старті через `GET /version`. Розбіжність **не блокує роботу**:
пишеться ERROR у лог і подія аудиту `extension_version_mismatch`. Будь-яка помилка
запиту (таймаут 3 с) просто пропускає перевірку.

Шлях `/hs/mcp-baf` захардкоджений у `RootURL` розширення і мусить збігатися з
`--base`. Деталі — [architecture.md](architecture.md).

## Робочий процес

Жорсткі правила власника репозиторію:

1. **Ніколи не відкривати PR, поки власник не перевірив зміну на живій базі 1С.**
   Цикл: реалізація → він перевстановлює розширення/пакет на живій базі → каже
   «перевіряй» → перевірка через MCP-інструменти → лише тоді гілка/коміт/PR.
2. **Гілка на задачу**, названа за фактичною роботою (`fix/<що>`,
   `feature/<N>-<назва>`) — не заглушки.
3. **Коміти логічними блоками** (кілька згрупованих), ніколи один величезний.
4. Повідомлення комітів **англійською**; заголовок PR англійською, тіло можна
   українською.
5. **Тільки власник ставить розширення на живу базу** (`--install`). Claude цього
   зробити не може.

## Конвенції коду

- Коментарі й докстрінги — **російською**; README і `docs/` — **українською**.
- Історичні коментарі до джерел зберігаємо для атрибуції, але паритету з іншим репозиторієм немає. Додавати нові джерела в [sources.md](sources.md).
- GPL-код toolkit і код без підтвердженої ліцензії не переносити; використовувати власну реалізацію описаних контрактів.
- Порядок реєстрації стабільний; локальні інструменти додаються лише з відповідною опцією.
- Тули повертають готовий **markdown**, не JSON.

## Екосистема

Це **читаюча** сторона. Поруч:

| Проєкт | Роль |
|---|---|
| `baf-write-mcp` | Пишуча сторона (`propose → validate → create → verify`) |
| `mcp-baf-audit` | Спільна бібліотека аудиту (PyPI) |
| `baf-ops-dashboard` | Control plane (FastAPI + HTMX) |
| `hermes-agent` | Автономний агент на віддаленому сервері |

> Усе брендоване як «baf» — не повертай «1c» в URL, назви й документацію.

## Нові контрактні перевірки

`test_access.py` перевіряє приховані виклики, кеш списку й зміну прав. `test_objects.py` — параметри, помилки, Markdown і аудит. `test_helpindex.py` — HBK, кодування, пошук, кеш і пошкодження. `test_bsl_analysis.py` — синтаксис, діагностики, форматування, ліміти та незмінність вихідників. `test_extension_contract.py` перевіряє узгодженість XML-маршрутів, UUID, прав, обробників та версій. `test_protocol.py` перевіряє через SDK 2 повний каталог із 16 інструментів, 11 промптів і запуск stdio в обох режимах протоколу.

Синтетична `tests/testdata/platform.hbk` містить шість власних тестових сторінок, не матеріали офіційної довідки. Зміни розширення потребують перевірки на базі власника: GUID/посилання туди й назад, реквізити й табличні частини, незалежні й підпорядковані регістри, два користувачі з різними правами, відмова адміністративної перевірки. Успіх Python-тестів не замінює цієї перевірки.
