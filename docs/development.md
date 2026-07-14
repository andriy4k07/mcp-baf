# Розробка

[← Назад до змісту](README.md)

## Встановлення

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev]"          # Linux / macOS
# .venv\Scripts\pip install -e ".[dev]"    # Windows
```

Python **3.11+**. Залежності мінімальні: `mcp>=1.9`, `httpx>=0.27`,
`mcp-baf-audit>=0.2.1`. З dev-екстри ставиться лише `pytest`.

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
.venv/bin/python -m pytest tests                                        # усі (98)
.venv/bin/python -m pytest tests/test_server.py::test_registered_tools  # один
```

| Файл | Що покриває |
|---|---|
| `test_config.py` | Пріоритет defaults → env → CLI |
| `test_client.py` | `OneCClient`: auth, ліміт розміру, помилки |
| `test_server.py` | Реєстрація тулів (зокрема: без `--dump` немає `search_code`) |
| `test_dumpindex.py` | Побудова індексу, режими пошуку |
| `test_cache.py` | Дисковий кеш, шляхи, інкрементальний diff |
| `test_modulenames.py` | NFC-нормалізація, розбір імен модулів |
| `test_formparser.py` | Розбір `Form.xml` з вивантаження |
| `test_installer.py` | Патчі XML під версії платформи |
| `test_bsl.py` | Довідник BSL |
| `test_traced.py` | `traced_text`, події аудиту, `trace_id` |

> **Лінтера й форматера в проєкті немає** — не додавай їх мимохідь.

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

`scripts/e2e_check.py` — ручна перевірка, потребує mock-сервера 1С з
оригінального Go-репо:

```sh
go run ./cmd/mock-1c
```

## Структура

```
src/mcp_baf/
├── __main__.py        точка входу: --install або сервер на stdio
├── server.py          create_server, порядок реєстрації, EXPECTED_EXTENSION_VERSION
├── config.py          defaults → env → CLI
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
> Зараз обидва — `0.4.2`.

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
- Коментарі часто посилаються на відповідні файли Go-версії (`dump/index.go`,
  `server/server.go`) — це навмисно, порт тримає паритет з оригіналом.
- Порядок реєстрації тулів у `create_server` збігається з Go-версією — не
  переставляй без причини.
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
