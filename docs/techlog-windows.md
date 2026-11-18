# Технологічний журнал і запуск службою Windows

Один екземпляр mcp-baf запускається **на сервері 1С** (`--transport https`) і
читає технологічний журнал (ТЖ) з локального диска, тому SMB не потрібен.
Решта клієнтів (hermes, робоче місце) підключаються до нього по HTTPS із
Bearer-токеном.

## 1. Налаштування ТЖ (`logcfg.xml`)

Від імені **адміністратора** на сервері 1С:

```bat
mcp-baf --install "сервер\база" --server --techlog-dir D:\techlog --db-user Адміністратор
```

Пароль бази — через `mcp_baf_DB_PASSWORD_FILE` (див. [configuration.md](configuration.md)).
Після встановлення розширення команда ставить `logcfg.xml` у каталог `conf`
платформи (`bin\conf`, або каталог із ключа `ConfLocation` у `bin\conf\conf.cfg`)
і створює `D:\techlog`.

- Журнал **звужено**: лише `TLOCK`, `TTIMEOUT`, `TDEADLOCK`, `EXCP`, історія 72 години.
- Для цих подій увімкнено `<property name="all"/>`. Для `EXCP` це означає, що
  `Descr`/`Context` можуть містити бізнес-дані (телефони, email, фрагменти
  запитів), тому запускайте сервер з `--mask-pii`.
- Наявний `logcfg.xml` **не перезаписується**: якщо він відрізняється, команда
  друкує diff і підказку, як замінити вручну.
- Не Windows або немає прав адміністратора — файл не пишеться; шлях і повний
  вміст друкуються для ручного встановлення (це не помилка).
- Платформа перечитує `logcfg.xml` приблизно раз на хвилину, перезапуск не потрібен.

## 2. Запуск службою (Планувальник завдань)

Токен — у файлі (його прочитає `mcp_baf_HTTP_TOKEN_FILE`; прапора `--http-token-file` немає):

```bat
setx /M mcp_baf_HTTP_TOKEN_FILE C:\mcp-baf\token.txt
setx /M mcp_baf_USER MCP
setx /M mcp_baf_PASSWORD_FILE C:\mcp-baf\pass.txt
schtasks /create /tn "mcp-baf" /sc onstart /ru SYSTEM /rl HIGHEST ^
  /tr "C:\mcp-baf\.venv\Scripts\mcp-baf.exe --base http://localhost/baf/hs/mcp-baf --transport https --http-host 0.0.0.0 --http-port 8001 --http-allowed-hosts srv1c.example.com --techlog-dir D:\techlog --mask-pii --cache-dir C:\mcp-baf\cache"
schtasks /run /tn "mcp-baf"
```

Замість `SYSTEM` можна задати окремого користувача (`/ru DOMAIN\mcpsvc /rp *`),
який має читати `D:\techlog` і `C:\mcp-baf`. Обмежте доступ до файлів токена й
пароля. Змінні `setx /M` потрапляють у нові процеси: після їх зміни перезапустіть
завдання. Без `--tls-cert/--tls-key` створюється локальний CA в `<cache-dir>\tls\`
(його сертифікат потрібно довірити клієнтам); для спільного використання
краще вказати свій сертифікат.

## 3. Підключення клієнтів

Клієнт (hermes, Claude Code тощо) підключається за адресою
`https://srv1c.example.com:8001/mcp` із заголовком `Authorization: Bearer <токен>`.
Вимога `--http-allowed-hosts` — ім'я, за яким клієнти звертаються до сервера.
Відкрийте порт 8001 у брандмауері лише для потрібних адрес.

Читання ТЖ — `get_event_log` з `source=techlog` (потребує адмін-прав на
доступ до цього інструмента, як і журнал реєстрації).
Якщо 1С недоступна (впала, не відповідає `/capabilities`), `get_event_log`
лишається доступним лише з `source=techlog` — щоб знайти причину падіння.
Явна відмова 1С у правах закриває інструмент повністю.

## Що варто підтвердити на живому сервері

- Каталог `conf`: `bin\conf` (версійний) чи спільний `<каталог установки>\conf`.
- Одиниця тривалості в ТЖ (8.3.x — мікросекунди, у 8.2 — 1e-4 с).
- Формат файлів: `<techlog-dir>\<процес>_<pid>\yyMMddHH.log`, час — місцевий.
