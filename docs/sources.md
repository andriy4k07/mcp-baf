# Джерела і ліцензії

[← Назад до змісту](README.md)

mcp-baf — самостійний проєкт. Ця сторінка фіксує походження успадкованої реалізації, адаптованих компонентів та ідей нових інструментів. Посилання на репозиторій не означає, що його код включено до пакета.

| Репозиторій | Що використано | Revision / спосіб | Ліцензія |
|---|---|---|---|
| [feenlace/mcp-1c](https://github.com/feenlace/mcp-1c) | Основа попередніх версій: інструменти читання, промпти, ідеї пошуку/кешу, початкова статична довідка BSL. Генератор `_functions_data.py` досі читає `bsl/functions.go` | Успадковано з попередніх версій mcp-baf; історичні коментарі збережено | MIT; copyright feenlace залишається в [LICENSE](../LICENSE) |
| [ROCTUP/1c-mcp-toolkit](https://github.com/ROCTUP/1c-mcp-toolkit) | Ідеї пошуку посилань, навігації та перевірки прав | `fe12903`; власна реалізація за поведінковими специфікаціями research, без перенесення коду | GPL джерела; його код не включено |
| [rzateev/onec-help-mcp](https://github.com/rzateev/onec-help-mcp) | Формат і парсер контейнера `.hbk`, читання ZIP `FileStorage`. Адаптація з перевіркою меж/ланцюжків і кодування. HTML-парсер та SQLite-індекс реалізовані в mcp-baf | `f66860b`; адаптовано `src/parsers/hbk_reader.py` | MIT, Copyright (c) 2025–2026 Roman Zateev. [Повний текст у пакеті](../src/mcp_baf/helpindex/LICENSE-onec-help-mcp.txt) |
| [phsin/mcp-bsl-ls](https://github.com/phsin/mcp-bsl-ls) | Приклад форми інструментів аналізу та форматування | `119f82f`; інтерфейс інструментів використано як приклад, аналізатор і форматер написано на Python, код не перенесено | LICENSE у дослідженому checkout відсутній |
| [1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server) | Досліджений приклад діагностик; рушій цього проєкту не використовується | Власний базовий Python-лексер/парсер і форматер; Java-код, граматика та JAR не включені | LGPL-3.0-or-later, див. [ліцензійний заголовок джерела](https://github.com/1c-syntax/bsl-language-server/blob/develop/src/main/java/com/github/_1c_syntax/bsl/languageserver/reporters/JsonReporter.java) |
| [vladimir-kharin/1c_mcp](https://github.com/vladimir-kharin/1c_mcp) | Ідея фільтрації списку інструментів за правами. Реалізовано через права HTTP-методів із перевіркою прямого виклику | `07fd888`; власна реалізація, контейнери обробок не впроваджено | README заявляє MIT; LICENSE у дослідженому checkout відсутній; код не перенесено |
| [skiddgoddamn/1c-mcp](https://github.com/skiddgoddamn/1c-mcp) | Досліджено діагностику заповнення/проведення документів; її відкладено, у цьому релізі нічого не використано | `a031e11` | README заявляє MIT; LICENSE у дослідженому checkout відсутній |
| [andriy4k07/mcp-baf-audit](https://github.com/andriy4k07/mcp-baf-audit) | Спільний контракт аудиту, trace_id та ротація журналів | Зовнішня Python-залежність `mcp-baf-audit>=0.2.1` | Ліцензія й атрибуція постачаються з пакетом залежності |

Початкові специфікації — документи `01`–`07` з локального `mcp-baf-research`, дослідження від 2026-10-01. Сам дослідницький каталог не потрібен для встановлення mcp-baf.

У research ліцензію BSL Language Server помилково позначено Apache-2.0. В документації mcp-baf використано LGPL-3.0-or-later за актуальним заголовком офіційного джерела. У поточній реалізації BSL Language Server не є залежністю: базові перевірки та форматування виконуються власним Python-кодом.

Офіційна довідка платформи не включена до пакета. Користувач надає свої `.hbk`-файли; тестова HBK-фікстура містить лише власні короткі тестові сторінки. Docker/Qdrant і embedding-код onec-help-mcp не використовуються.

## Походження за функціональними областями

Проєкт стартував 2026-06-11 як Python-порт feenlace/mcp-1c (Go), стан апстриму ≈ тег v1.6.13 (2026-06-04). Порт виконано в проміжному приватному репозиторії `mcp-1c-python` («Strict Python port of the Go mcp-1c»); він не опублікований і не є залежністю.

| Область | Файли | Походження | Ліцензія |
|---|---|---|---|
| Розширення 1C / HTTP-сервіс MCPService (`/hs/mcp-baf`), маршрути та інсталятор | `src/mcp_baf/extension_src/`, `installer.py` | Успадковано від розширення feenlace/mcp-1c на момент порту (та сама структура HTTP-сервісу); відтоді розвивається самостійно: власне версіонування (0.5.x проти 0.4.x в апстримі), capabilities, маршрути об'єктів/прав, українська локалізація, патчинг XML під версію платформи | MIT (feenlace, див. [LICENSE](../LICENSE)) |
| `execute_query`, `validate_query`, `get_event_log`, `get_configuration_info`, `get_metadata_tree`, `get_object_structure`, `get_form_structure`, `bsl_syntax_help`, `search_code`, промпти | `tools/*.py`, `prompts.py`, `dumpindex/`, `bsl/` | Портовано з feenlace/mcp-1c 2026-06-11, далі змінювалося самостійно (напр. ліміт журналу реєстрації, парсер форм) | MIT (feenlace) |
| `find_object_references`, `get_object_link`, `get_metadata_rights` | `tools/objects.py` | Власна реалізація з ідей ROCTUP/1c-mcp-toolkit (див. таблицю вище) | Ліцензія проєкту |
| Фільтрація інструментів за capabilities | `access.py` | Власна реалізація, ідея з vladimir-kharin/1c_mcp | Ліцензія проєкту |
| `search_platform_help`, `get_platform_element` | `helpindex/` | Парсер HBK адаптовано з rzateev/onec-help-mcp, решта власна | MIT (Roman Zateev) + ліцензія проєкту |
| `bsl_analyze`, `bsl_format` | `bsl_native/` | Власна реалізація; mcp-bsl-ls / bsl-language-server лише вивчалися | Ліцензія проєкту |
| `--mask-pii` — маскування PII у результатах запитів | `tools/query.py` (`mask_pii_result`) | Власна реалізація, зовнішнього джерела немає | Ліцензія проєкту |
| Транспорт HTTPS/streamable-http, bearer-токен, самопідписаний CA, Docker | `tls.py`, `__main__.py`, `Dockerfile` | Власна реалізація поверх офіційного MCP SDK, зовнішнього джерела немає | Ліцензія проєкту |
| Аудит/логування | залежність `mcp-baf-audit` | Див. таблицю вище | Див. таблицю вище |

«Ліцензія проєкту» — MIT, Copyright (c) 2026 andriy4k07 (у [LICENSE](../LICENSE) також рядок про feenlace).
