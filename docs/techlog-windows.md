# Технологічний журнал і служба Windows

[← Назад до змісту](README.md)

Один екземпляр mcp-baf працює **на сервері 1С** як служба (`--transport https`).
Він читає технологічний журнал (ТЖ) з локального диска, тож SMB не потрібен.
Інші клієнти (hermes, робоче місце з Claude Code) підключаються до нього по HTTPS
з Bearer-токеном.

```
Сервер 1С (Windows)
 ├─ rphost ──────────► пише ТЖ у D:\LOG_1C
 └─ служба mcp-baf ──► читає ТЖ локально, ходить у 1С через http://localhost/...
        ▲ HTTPS + токен
   ┌────┴─────┐
 hermes    робоче місце
```

Усі команди нижче виконуються в **PowerShell від імені адміністратора** на сервері 1С.
Шпаргалка є також наприкінці `mcp-baf --help`.

## 1. Підготовка

1. Клонуйте репозиторій і створіть venv (звідси ставиться служба й беруться оновлення):
   ```powershell
   git clone https://github.com/andriy4k07/mcp-baf C:\src\mcp-baf
   cd C:\src\mcp-baf
   py -m venv .venv
   .\.venv\Scripts\pip install -e .
   ```
2. Секрети покладіть **у файли** (не в командний рядок і не в змінні з самим секретом):
   ```powershell
   New-Item -ItemType Directory -Force C:\mcp-baf | Out-Null
   Set-Content -Path C:\mcp-baf\token.txt    -Value "<довгий випадковий токен>" -NoNewline
   Set-Content -Path C:\mcp-baf\password.txt -Value "<пароль користувача 1С>"   -NoNewline
   Test-Path C:\mcp-baf\token.txt, C:\mcp-baf\password.txt   # обидва True
   ```
   Генерувати токен можна так:
   `-join ((1..48) | % { [char[]]'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789' | Get-Random })`.
   Пароль — той самий, з яким HTTP-сервіс 1С уже працює (перевірте, див. «Помилки»).
3. Змінні середовища в поточній сесії:
   ```powershell
   $env:mcp_baf_USER            = "<користувач 1С>"
   $env:mcp_baf_PASSWORD_FILE   = "C:\mcp-baf\password.txt"
   $env:mcp_baf_HTTP_TOKEN_FILE = "C:\mcp-baf\token.txt"
   ```

## 2. Розширення і `logcfg.xml`

```powershell
.\.venv\Scripts\mcp-baf.exe --install "localhost\<база>" --server --db-user <користувач> --techlog-dir D:\LOG_1C
```

Пароль до бази краще передати через `$env:mcp_baf_DB_PASSWORD_FILE`, а не через `--db-password`.

Після встановлення розширення команда кладе `logcfg.xml` у каталог `conf` платформи.
Каталог визначається так: `ConfLocation` з `bin\conf\conf.cfg`, інакше `bin\conf`.
На BAF 8.3.18 це, наприклад, `C:\Program Files\BAF\conf\logcfg.xml`. Також команда
створює `D:\LOG_1C`.

- Журнал **звужений**: лише `TLOCK`, `TTIMEOUT`, `TDEADLOCK`, `EXCP`, історія 72 години.
  Повний журнал (`<ne property="name" value=""/>`, тобто всі події) на робочій базі
  займає гігабайти за годину й гальмує сервер, тож лишати його ввімкненим не варто.
- `<property name="all"/>` для `EXCP` пише в `Descr`/`Context` бізнес-дані,
  тому служба запускається з `--mask-pii`.
- Наявний `logcfg.xml` **не перезаписується**. Якщо він збігається з шаблоном
  (пробіли й відступи не враховуються), команда виводить `already installed`.
  Якщо ні, друкує diff, і тоді секцію `<log>` треба об'єднати вручну.
- Без прав адміністратора файл не пишеться. Команда друкує шлях і вміст для
  ручного встановлення, і це не помилка.
- Платформа перечитує `logcfg.xml` приблизно раз на хвилину, перезапуск не потрібен.

## 3. Встановлення служби

```powershell
.\.venv\Scripts\mcp-baf.exe --install-service `
  --base http://localhost/<база>/uk_UA/hs/mcp-baf `
  --transport https --http-host 0.0.0.0 --http-port 8001 `
  --http-allowed-hosts "<IP або ім'я сервера>:*" `
  --techlog-dir D:\LOG_1C --mask-pii
```

Що робить команда:

1. Відмовляє, якщо секрет заданий відкрито: `mcp_baf_PASSWORD`, `mcp_baf_HTTP_TOKEN`,
   `mcp_baf_PII_KEY`, `mcp_baf_DB_PASSWORD`, `--pass`, `--http-token`. Служба працює
   від імені SYSTEM і не бачить змінних вашої сесії, а писати секрети у файл завдання
   відкритим текстом не можна.
2. Перевіряє конфігурацію (як звичайний старт), тож з помилкою служба не реєструється.
3. Зупиняє стару службу, якщо вона є.
4. Створює `%ProgramFiles%\mcp-baf\venv` і ставить туди пакет із того самого
   джерела, звідки запущено команду. Для локального клону це звичайна установка,
   не editable. Це займає хвилину-дві: pip качає залежності, потрібна мережа.
5. Створює `%ProgramData%\mcp-baf` для даних і журналів (або бере `--cache-dir`)
   і через `icacls` залишає доступ лише SYSTEM і Administrators.
6. Пише `run-mcp-baf.cmd` у каталог даних: `chcp 65001`, усі `mcp_baf_*` змінні
   сесії (лише шляхи до файлів і ім'я користувача) і команду запуску. Реєструє
   завдання Планувальника `mcp-baf` (SYSTEM, запуск при старті ОС) і запускає його.

| Що | Де |
|---|---|
| Програма | `C:\Program Files\mcp-baf\venv` |
| Дані, журнали, TLS, `pii.key` | `C:\ProgramData\mcp-baf` |
| Секрети | ваші файли, наприклад `C:\mcp-baf\*.txt` (SYSTEM має мати доступ на читання) |

**Оновлення:** `git pull` у клоні, а потім та сама команда `--install-service`.
Стару службу вона зупиняє сама.

**Видалення:** `mcp-baf --uninstall-service` прибирає завдання й програму.
Дані (журнали, CA, `pii.key`) лишаються.

## 4. Керування

| Команда | Що робить |
|---|---|
| `mcp-baf --status` | стан служби, PID сервера, каталог і журнали |
| `mcp-baf --logs` | вивід служби (`server-console.log`): останні 50 рядків і стеження, Ctrl+C — вихід |
| `mcp-baf --logs server` | помилки сервера (`server.log`) |
| `mcp-baf --logs audit` | виклики інструментів і відмови 1С (`audit.log`) |
| `mcp-baf --stop` | зупинити сервер за PID-файлом |
| `schtasks /run /tn mcp-baf` | запустити службу знову |
| `mcp-baf --uninstall-service` | видалити службу |

Після `--install-service` команди `--status`, `--logs` і `--stop` самі знаходять
каталог служби через Планувальник, `--cache-dir` не потрібен. Запускати їх можна
будь-яким `mcp-baf.exe`, наприклад `& "C:\Program Files\mcp-baf\venv\Scripts\mcp-baf.exe" --status`.

### Запуск у консолі й фон

Для тестів сервер можна запустити просто у вікні (тими самими прапорами, без
`--install-service`). Підказка у вікні:

- **d** (або **в** в українській розкладці): сервер звільняє порт і запускає свою
  копію у фоні, без вікна, з тими самими аргументами й змінними. Друкує її PID,
  журнал і команду зупинки. Копія переживає закриття вікна.
- **Ctrl+C**: зупинка без traceback.

Фонова копія без `--cache-dir` працює з каталогом за замовчуванням
(`%LOCALAPPDATA%\mcp-baf`). Тому зупиняйте її **командою з підказки**, тобто з
`--cache-dir`. Голий `mcp-baf --stop` знайде каталог служби й зупинить службу.
Порт для тестової копії (наприклад 8002) з мережі доступний лише після
окремого правила брандмауера.

## 5. Підключення клієнтів

Адреса: `https://<IP або ім'я сервера>:8001/mcp`, заголовок `Authorization: Bearer <токен>`.

1. Відкрийте порт (за можливості лише для потрібних адрес):
   ```powershell
   New-NetFirewallRule -DisplayName "mcp-baf" -Direction Inbound -Protocol TCP -LocalPort 8001 -Action Allow
   ```
2. Довірте локальний CA. Без `--tls-cert/--tls-key` служба створює його в
   `C:\ProgramData\mcp-baf\tls\ca.crt`. Скопіюйте цей файл на клієнт:
   - Claude Code (Node): `NODE_EXTRA_CA_CERTS=/шлях/ca.crt`;
   - Python (httpx/requests): `SSL_CERT_FILE` або `verify="/шлях/ca.crt"`.

   Новий каталог даних означає новий CA, і довіру треба налаштувати заново.
   Для довгострокового спільного використання краще вказати свій сертифікат
   через `--tls-cert/--tls-key`.
3. Claude Code:
   ```sh
   claude mcp add --transport http mcp-baf-srv https://<сервер>:8001/mcp \
     --header "Authorization: Bearer $(cat ~/.mcp-baf-srv.token)"
   ```

`--http-allowed-hosts` — це ім'я або IP, які клієнти пишуть в адресі, плюс `:*`
(будь-який порт). Кілька значень перелічуються через кому. Вони ж потрапляють у
сертифікат. Запит з іншим `Host` сервер відхиляє, це захист від DNS-rebinding.

## 6. Використання ТЖ

`get_event_log(source="techlog")` повертає зведення за вікно (типово остання
година, час сервера):
- області блокувань за сумарним очікуванням;
- дедлоки й таймаути;
- групи помилок `EXCP`. GUID при групуванні замінюються на `…`, тож однакові помилки рахуються разом.

`event="TLOCK"|"TTIMEOUT"|"TDEADLOCK"|"EXCP"` залишає лише один розділ.
`start_date`/`end_date` задають вікно у форматі ISO, без часового поясу.
Тривалості в 8.3.x — мікросекунди.

**Коли 1С недоступна** (впала, не відповідає `/capabilities`), видно лише
`get_event_log` і локальні BSL-інструменти, і `get_event_log` працює тільки з
`source="techlog"`, щоб знайти причину. Журнал реєстрації та інші HTTP-інструменти
при цьому відмовляють. Явна відмова 1С у правах закриває й ТЖ.

Перевірено на BAF 8.3.18: файли `<процес>_<pid>\yyMMddHH.log`, час місцевий,
`Regions`/`WaitConnections`/`Usr`/`Context`/`Descr` розбираються.

## 7. Помилки й що з ними робити

| Симптом | Причина | Що робити |
|---|---|---|
| `Configuration error: --transport https requires a bearer token` | токен не задано | `$env:mcp_baf_HTTP_TOKEN_FILE = "C:\mcp-baf\token.txt"` |
| `mcp_baf_PASSWORD_FILE: не вдалося прочитати файл ... (FileNotFoundError)` | файла немає: `Set-Content` іноді нічого не створює без явних параметрів | `Set-Content -Path ... -Value ... -NoNewline`, потім `Test-Path` має дати `True` |
| `Секрети не можна записати у службу відкритим текстом` | задано `mcp_baf_PASSWORD`/`--pass` тощо | `Remove-Item Env:mcp_baf_PASSWORD`, використовуйте `*_FILE` |
| `Configuration error: --http-allowed-hosts: ...` | кривий запис (`[::1`, порт 99999) | формат `хост:порт` або `хост:*`, через кому |
| Видно лише `get_event_log` і `bsl_*` | служба не авторизується в 1С | `mcp-baf --logs audit`, подія `access.capabilities_unavailable`. `401` — пароль у файлі не той, `ConnectError` — неправильний `--base` або 1С/вебсервер лежить, `403` з `reason` — немає прав |
| `401` при правильному, здавалося б, паролі | пароль у файлі відрізняється від пароля в 1С (регістр, зайвий символ) | порівняйте з робочим клієнтом; файл без переводу рядка (`-NoNewline`) |
| Сервер не бачить 1С | у `--base` бракує `/` після хоста або `/uk_UA` | `http://localhost/<база>/uk_UA/hs/mcp-baf`, як у браузері |
| Клієнт: таймаут з'єднання | порт закритий брандмауером | `New-NetFirewallRule ... -LocalPort 8001` |
| Клієнт: помилка сертифіката | CA не довірений або змінився каталог даних | довірте `C:\ProgramData\mcp-baf\tls\ca.crt` (розділ 5) |
| Клієнт: 421/403 за `Host` | адреса клієнта не в `--http-allowed-hosts` | додайте IP/ім'я з `:*` і перевстановіть службу |
| `logcfg.xml exists and differs, NOT overwritten` | файл відрізняється по суті | об'єднайте секцію `<log>` вручну |
| `get_event_log(source="techlog")`: `Файлов: 0` | порожнє вікно, ТЖ ще не пише або інший каталог | перевірте `location` у `logcfg.xml` = `--techlog-dir`, зачекайте хвилину після зміни, розширте `start_date` |
| `mcp-baf --stop` зупинив службу замість тестової копії | без `--cache-dir` `--stop` бере каталог служби | зупиняйте тестову копію командою з підказки (з `--cache-dir`) |
| `--status`: `стан: ?` | локалізована Windows (рядок не `Status:`) | дивіться `schtasks /query /tn mcp-baf` |
| pip при оновленні: файл зайнятий | процес ще не відпустив файли venv | повторіть `--install-service` |
| Служба перестала стартувати після оновлення Python | venv прив'язаний до базового Python | повторіть `--install-service` новим Python |
| Після переїзду каталогу даних змінилися токени `PII:…` | новий `pii.key` | очікувано. Щоб зберегти, скопіюйте `pii.key` і `tls\` зі старого каталогу до першого старту |

Безпека: не вставляйте паролі й токени в чати, тікети чи скриншоти. Якщо таке
сталося, змініть пароль користувача 1С і запишіть новий у `password.txt`.
