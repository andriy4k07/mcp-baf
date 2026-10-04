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
