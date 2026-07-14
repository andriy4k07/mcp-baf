# Архітектура

[← Назад до змісту](README.md)

mcp-baf — це **read-only** сторона екосистеми BAF: MCP-сервер, який дає AI-асистенту
доступ до метаданих і даних бази 1С:Підприємство через HTTP-сервіс, але нічого
в базу не пише. Python-порт [feenlace/mcp-1c](https://github.com/feenlace/mcp-1c)
(Go) — коментарі в коді часто посилаються на відповідні файли Go-версії, а
порядок реєстрації інструментів навмисно збігається з нею.

```
AI-клієнт (MCP, stdio)  <-- stdio -->  mcp-baf (Python)  --HTTP GET/POST-->  HTTP-сервіс 1С
                                            |                                 (розширення MCPService,
                                            +-- SQLite FTS5                   RootURL /hs/mcp-baf)
                                                (search_code, опційно, --dump)
```

Парний проєкт до write-стороны — [baf-write-mcp](https://github.com/andriy4k07/baf-write-mcp),
яка форсує потік `propose → validate → create → verify` і пише в базу. mcp-baf
такого потоку не має взагалі: усі інструменти лише читають.

## Точка входу і два режими

`__main__.py:main` спочатку парсить аргументи (`config.parse_args` →
`config.load_config`) і піднімає логування (`_setup_logging`), а далі
розходиться в один з двох режимів:

- **`--install <DB_PATH>`** — викликає `installer.install(...)`: завантажує
  розширення 1С в цільову базу через DESIGNER і завершується (сервер не
  запускається). Деталі нижче, у розділі [Розширення 1С](#розширення-1с).
- **звичайний запуск** — `server.create_server(config)` збирає `FastMCP` і
  `server.run(transport="stdio")` запускає його на stdio. Це основний режим:
  так сервер підключається до AI-клієнта (Claude Desktop, Claude Code,
  Cursor тощо).

## Реєстрація інструментів

Кожен модуль у `src/mcp_baf/tools/` (`metadata`, `object_structure`, `query`,
`search_code`, `form`, `validate_query`, `eventlog`, `configuration_info`,
`bsl_help`) виставляє функцію `register(mcp, client, audit)`, яка реєструє
один MCP-інструмент через `@mcp.tool(...)`. `server.create_server` викликає
ці функції в **фіксованому порядку**, що навмисно повторює порядок
`server/server.go` в Go-оригіналі:

```python
metadata.register(mcp, client, audit)
object_structure.register(mcp, client, audit)
query.register(mcp, client, audit)
if index is not None:
    search_code.register(mcp, index, audit)
form.register(mcp, client, audit, config.dump_dir)
validate_query.register(mcp, client, audit)
eventlog.register(mcp, client, audit)
configuration_info.register(mcp, client, audit)
bsl_help.register(mcp, audit)
prompts.register(mcp)
```

`search_code` — виняток із загального патерну: реєструється, тільки якщо
задано `--dump` (є `DumpIndex`), і отримує сам індекс замість `client`.
Без `--dump` цього інструмента в списку MCP-тулів немає взагалі (на цьому
побудований `tests/test_server.py::test_registered_tools`).

Усі інструменти повертають **готовий markdown-текст**, а не JSON — MCP-клієнт
рендерить його як є. Це відрізняє mcp-baf від типового MCP-сервера, що
повертає структуровані дані.

## `traced_text`: наскрізний аудит виклику інструмента

Тіло кожного інструмента обгортається в `tools/common.py:traced_text(audit,
tool, call, args=...)`. Вона:

1. Бере `trace_id` з contextvar (`get_trace_id()`) або генерує новий
   (`new_trace_id()`) — ніколи не залишає його порожнім — і фіксує його назад
   у contextvar (`set_trace_id`).
2. Виконує `call()` і повертає його результат (markdown) без змін.
3. Пише подію аудиту `tool_call` (канонічно `tool.call`) з `tool`, `args`,
   `ok=True`, `duration_ms` — або, якщо `call()` кинув виняток, `tool_error`
   (`tool.error`) з текстом помилки, і прокидає виняток далі.

Оскільки `trace_id` живе в contextvar, усі вкладені події того самого async-
контексту (найпомітніше — `one_c.http` з `client.py`) успадковують той самий
`trace_id` без явної передачі. Деталі схеми та зв'язку подій — у
[Логуванні та аудиті](logging-and-audit.md).

## HTTP-клієнт до 1С

`client.py:OneCClient` — асинхронний клієнт на httpx:

- **Basic auth**, якщо задано `--user`/`--pass`.
- **`Connection: close`** на кожному запиті — щоб не вичерпувати ліміт
  сеансів 1С (тривалий keep-alive з боку HTTP-сервісу 1С — проблема, а не
  оптимізація).
- **Стрімінг з лімітом.** Відповідь читається чанками через
  `resp.aiter_bytes()`; якщо накопичений розмір перевищує
  `--max-response-size` (MiB), запит переривається з понятною `OneCError`
  замість того, щоб зжерти всю пам'ять на гігантській відповіді.
- **Рівно одна подія аудиту на виклик.** `_audit_http` пишеться в `finally`
  незалежно від результату (успіх, HTTP-помилка, помилка декодування JSON,
  переповнення ліміту) — метод, ендпоінт, статус, тривалість, розмір
  відповіді. **Тіло запиту й відповіді в аудит не потрапляє ніколи.**

## Розширення 1С

`extension_src/` — вихідники розширення `MCP_HTTPService` (HTTP-сервіс
`MCPService`, `RootURL = mcp-baf`) у форматі XML-вивантаження конфігурації
(`DumpConfigToFiles`), що постачаються прямо всередині Python-пакета —
скомпільований `.cfe`-файл не потрібен.

`installer.py` (викликається з `--install`):

1. Копіює `extension_src/` у тимчасовий каталог і локалізує синоніми
   (`--lang ua|ru`; за замовчуванням українська — мова цільової бази BAF).
2. Патчить XML під версію цільової платформи: версію формату вивантаження
   (`version="2.X"`), режим сумісності розширення, вирізає елементи, які не
   розуміють старі платформи (`KeepMappingToExtendedConfigurationObjectsByIDs`,
   `InternalInfo`, `ContainedObject` ролі — усе це з'явилось у 8.3.15).
3. Вантажить розширення командою DESIGNER `/LoadConfigFromFiles`, з
   ланцюжком повторних спроб під конкретні відомі помилки старих платформ
   (немає режиму сумісності, конфлікт заимствованих властивостей, розширення
   вже існує тощо), і застосовує `/UpdateDBCfg`.

Мінімальна підтримувана платформа — 8.3.10.

**Версія розширення й сервера мусять збігатися.** `server.py` тримає
константу `EXPECTED_EXTENSION_VERSION` (наразі `"0.4.2"`), яка звіряється з
версією, зашитою в `HTTPServices/MCPService/Ext/Module.bsl` (ендпоінт
`GET /version`). На старті сервера фонова задача `_check_extension_version`
запитує `/version`; розбіжність не блокує роботу сервера, а лише логується
(`logger.error`) і пишеться в аудит подією `extension_version_mismatch`
(`server.version_mismatch`). Якщо ендпоінт `/version` відсутній (стара
версія розширення), перевірка мовчки пропускається. При будь-якій зміні
`extension_src/` обидва місця — версія в `Module.bsl` і
`EXPECTED_EXTENSION_VERSION` — мусять бути піднятими разом.

## Чому read-only

Read-only — не просто угода на боці клієнта, а властивість, витримана на
обох рівнях:

- **1С-сторона.** Ендпоінт `Запрос`/`Query` розширення сам перевіряє текст
  запиту: `Module.bsl` відхиляє все, що не починається з `ВЫБРАТЬ`/`SELECT`,
  кодом 400 (`"Only SELECT queries allowed"`). Навіть якщо клієнт спробує
  протягнути `УДАЛИТЬ`/`DELETE` чи виклик процедури — 1С відмовить ще до
  виконання.
- **MCP-сторона.** Кожен з 9 інструментів реєструється з
  `ToolAnnotations(readOnlyHint=True)` — це чесна декларація для MCP-клієнта,
  а не косметика: жоден інструмент дійсно не змінює стан бази.
- **Немає жодного `execute_bsl`, `create_object` чи подібного.** Набір
  інструментів закритий і повністю описовий: метадані, структура об'єктів,
  запити (тільки читання), пошук по коду, довідка BSL, журнал реєстрації.

Запис у базу — окрема відповідальність сусіднього
[baf-write-mcp](https://github.com/andriy4k07/baf-write-mcp): інше
розширення (`BAF_WriteAPI`), інша роль 1С з мінімальними правами, форсований
потік `propose → validate → create → verify`. Розділення за рівнем довіри
навмисне: читаючий сервер безпечно давати будь-якій моделі й будь-якому
MCP-клієнту без додаткових гарантій; пишучий вимагає окремого контуру
довіри. Обидва сервери діляться спільним контрактом аудиту
(`mcp-baf-audit`) і живлять `baf-ops-dashboard` та віддаленого
`hermes-agent`.

## Пошуковий індекс (коротко)

`search_code` (реєструється, лише якщо задано `--dump`) працює поверх
SQLite FTS5-індексу над `.bsl`-файлами локальної вивантаження конфігурації;
індекс будується у фоновому потоці, тож старт сервера не блокується.
Деталі побудови, кешування й режимів (`smart`/`regex`/`exact`) — у
[Пошук і індексація](search-and-index.md).
