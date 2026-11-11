"""Маскирование ПДн в ответах MCP-инструментов.

`--mask-pii` должен закрывать все каналы, через которые ПДн попадают к
агенту: строки execute_query, журнал регистрации, структуру форм и
найденный код. Раньше маскирование жило только в execute_query, поэтому
телефон или email из журнала/кода уходили наружу в открытом виде.

Два механизма:
  * по имени колонки (`PII_COLUMN_MARKERS`) — для табличных результатов,
    где значения не отличить от обычных данных;
  * по значению (`PII_VALUE_RE`) — телефоны и email в свободном тексте.

Токен — усечённый HMAC-SHA256 от значения на стабильном ключе (issue #53):
ключ хранится в файле `pii.key` в кэш-каталоге (или приходит из
`mcp_baf_PII_KEY`), создаётся при первом использовании. Поэтому токены
равны между рестартами и сессиями (можно сравнивать обезличенные выборки),
но остаются неподбираемыми по словарю и не обратимы без ключа.
`--rotate-pii-key` выпускает новый ключ: старые и новые токены не связаны.

Концепции (не код) — рецензия vladimir-kharin/1c_mcp v1.10.0 в #44.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from collections.abc import Callable, Iterable
from typing import Any

# Подстроки имён колонок с персональными данными (сравнение без регистра).
# shortcut: ПІБ у полі Наименование (фізособи-контрагенти) не маскується —
# лише за назвою колонки; розширити, якщо агент виводить Наименование фізосіб
PII_COLUMN_MARKERS = tuple(m.lower() for m in (
    "ФИО", "ПІБ", "ИНН", "ІПН", "РНОКПП", "КодПоДРФО", "ДатаРождения",
    "ДатаНародження", "Телефон", "Email", "ЭлектроннаяПочта", "Паспорт",
    "ДокументУдостоверяющий", "Адрес",
    # Issue #53: признаки секретов и долговых идентификаторов
    # (концепция vladimir-kharin/1c_mcp v1.10.0). «Серия»/«Номер» —
    # сознательное перемаскивание (НомерДок, НомерГТД): промах в сторону
    # маскирования безопаснее утечки паспорта/карты.
    "Пароль", "Логин", "Токен", "ИмяПользователя",
    "Логін", "ІмяКористувача", "Ім'яКористувача", "Серія",
    "Password", "Login", "Token",
    "СНИЛС", "НомерКарты", "ЛицевойСчет", "Серия", "Номер", "КемВыдан",
))
# Украинские телефоны (+380XXXXXXXXX, 0XXXXXXXXX с пробелами/дефисами/
# скобками) и email.
_EMAIL_RE = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
_PHONE_RE = r"(?<!\d)(?:\+?38[\s-]*)?\(?0[\s-]*\d[\s-]*\d\)?(?:[\s-]*\d){7}(?!\d)"
PII_VALUE_RE = re.compile(_PHONE_RE + "|" + _EMAIL_RE)

# Идентификатороподобный токен: цифры/латиница/дефис, внутри есть хотя бы
# одна латинская буква — GUID, артикул, VIN, e1cib-ссылка, BSL-идентификатор.
# 10-значний цифровой прогон внутри такого токена — часть кода, а не телефон:
# ROCTUP/1c-mcp-toolkit#44 (анонимайзер съедал навигационный ref как IBAN).
# Email идёт ПЕРВЫМ в альтернативе: "abc-def@x.com" остаётся почтой.
# Сознательный компромисс: "tel-0671234567" не маскируется — в 1С-контексте
# телефоны живут в кириллическом/пунктуационном обрамлении, латиница в
# токене означает идентификатор.
# Сознательное перемаскивание (issue #53, п.5): голый 10-значный прогон с
# ведущим нулём ("0123456789") маскируется как телефон. Требовать
# разделители/префикс нельзя — голые "0671234567" в комментариях 1С
# реальный канал утечки (тест #46); ложное маскирование безобиднее.
_IDENT_RE = r"(?<![0-9a-zA-Z-])[0-9a-zA-Z-]*[a-zA-Z][0-9a-zA-Z-]*(?![0-9a-zA-Z-])"
PII_TEXT_RE = re.compile(
    r"(?P<email>" + _EMAIL_RE + r")|(?P<ident>" + _IDENT_RE + r")|(?P<phone>" + _PHONE_RE + r")"
)

# --- Ключ токенов (issue #53, п.2) ---------------------------------------

PII_KEY_FILENAME = "pii.key"
PII_KEY_BYTES = 32  # 256-битный ключ HMAC-SHA256
PII_KEY_HEX_CHARS = PII_KEY_BYTES * 2
PII_KEY_ENV = "mcp_baf_PII_KEY"
PII_COLUMN_MARKERS_ENV = "mcp_baf_PII_COLUMN_MARKERS"

# Фраза вместо текста ошибки 1С при --mask-pii (issue #53, п.3): regex-скруб
# оставляет ПІБ/адреса, которые не ловит телефонно-почтовый паттерн, поэтому
# агенту уходит константа, а полный текст — только в audit.log.
MASKED_ERROR_PHRASE = (
    "текст помилки 1С приховано (--mask-pii); повний текст — у audit.log, "
    "подія pii.error_text"
)

# Семантика токенов для описаний инструментов (issue #53, п.4).
# Список замаскированных колонок обещаем ТОЛЬКО для табличных ответов
# (execute_query): у журнала/формы/кода колонок нет, `masked_columns`
# там не появляется — безусловная обещанка вводила агента в заблуждение.
MASKING_NOTE = (
    "При --mask-pii ПДн замещены токенами PII:xxxxxxxx: токен стабилен в "
    "пределах ключа (файл pii.key в кэш-каталоге или mcp_baf_PII_KEY), "
    "равные значения дают равные токены, --rotate-pii-key меняет все "
    "токены; необратимость сохраняется (HMAC). ПІБ в поле Наименование не "
    "маскируется; в табличных ответах дополнительно приводится список "
    "замаскированных колонок."
)

# Состояние процесса: ключ и пользовательские маркеры. Нижа 32 байт ключ не
# принимаем, ниже порога криптостойкости усечённый HMAC подбирается быстрее.
_key: bytes | None = None
_key_file: str = ""
_extra_markers: tuple[str, ...] = ()


MIN_MARKER_LEN = 3


def _validate_markers(markers: Iterable[str]) -> tuple[str, ...]:
    """Маркер короче 3 символов («а») подстрокой маскирует почти все колонки."""
    out = tuple(m.strip().lower() for m in markers if m and m.strip())
    for m in out:
        if len(m) < MIN_MARKER_LEN:
            raise ValueError(
                f"маркер колонки ПДн «{m}» закороткий: потрібно щонайменше "
                f"{MIN_MARKER_LEN} символи (інакше маскуються майже всі колонки)"
            )
    return out


def split_marker_list(raw: str) -> tuple[str, ...]:
    """Разбирает CSV-строку маркеров (env/CLI) в кортеж нижнего регистра."""
    return _validate_markers(raw.split(","))


def configure_pii(
    cache_dir: str = "",
    extra_column_markers: Iterable[str] = (),
    *,
    rotate: bool = False,
    enabled: bool = True,
) -> None:
    """Инициализирует подсистему при старте сервера (см. `__main__.main`).

    Каждый вызов сбрасывает резолв ключа — это же «рестарт» для тестов:
    ключ лениво перечитывается из файла/окружения при первом токене.
    `rotate=True` выпускает новый ключ и перезаписывает файл немедленно.

    Некорректный `mcp_baf_PII_KEY` — ошибка сразу здесь (fail-fast при
    запуске), а не при первом токене: сервер с «плавающими» токенами
    выглядит рабочим, пока кто-то не сравнит выборки. Сообщение называет
    только ожидаемую длину, не значение ключа.

    При `enabled` (включён --mask-pii) каталог создаётся и ключ резолвится
    сразу: ошибки доступа/формата всплывают на старте (ValueError/OSError),
    а не посреди вызова инструмента.
    """
    global _key, _key_file, _extra_markers
    _extra_markers = _validate_markers(extra_column_markers)
    _key_file = os.path.join(cache_dir, PII_KEY_FILENAME) if cache_dir else ""
    _key = None
    _check_env_key()
    if rotate and os.environ.get(PII_KEY_ENV, "").strip():
        # Ротация молча перебила бы env-ключ (он старше файла) — отказываем.
        raise ValueError(
            f"--rotate-pii-key несумісний з {PII_KEY_ENV}: ключ із середовища "
            "не можна ротувати; приберіть змінну або прапорець"
        )
    if not (enabled or rotate):
        return
    if _key_file:
        os.makedirs(os.path.dirname(_key_file), exist_ok=True)
    if rotate:
        rotate_pii_key()
    else:
        _resolve_key()


def _check_env_key() -> None:
    """Проверяет формат env-ключа; молчит, когда ключ не задан."""
    env_raw = os.environ.get(PII_KEY_ENV, "").strip()
    if env_raw and _parse_key_hex(env_raw) is None:
        raise ValueError(
            f"{PII_KEY_ENV} повинен містити {PII_KEY_HEX_CHARS} "
            "шістнадцяткових символів (32 байти)"
        )


def _parse_key_hex(raw: str) -> bytes | None:
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        return None
    return key if len(key) == PII_KEY_BYTES else None


def _write_key_file(key: bytes, *, replace: bool = False) -> bool:
    """Атомарно кладёт ключ в файл; False, если файл уже есть (replace=False).

    Пишем во временный файл 0600 рядом и публикуем `os.link` (падает, если
    цель существует) либо `os.replace` (ротация — намеренная перезапись):
    читатель не увидит пустой/недописанный файл, а два процесса, стартующие
    одновременно, не выпустят разные ключи. 0600 — ключ позволяет заново
    вычислять токены по audit.log.
    """
    tmp = f"{_key_file}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            os.write(fd, key.hex().encode("ascii"))
        finally:
            os.close(fd)
        if replace:
            os.replace(tmp, _key_file)
        else:
            try:
                os.link(tmp, _key_file)
            except FileExistsError:
                return False
        return True
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _read_key_file() -> bytes:
    """Читает ключ; FileNotFoundError — файла нет, ValueError — он битый."""
    with open(_key_file, encoding="ascii", errors="replace") as fh:
        key = _parse_key_hex(fh.read().strip())
    if key is None:
        # Не перезаписываем молча: смена ключа тихо ломает связность токенов.
        raise ValueError(
            f"файл ключа PII {_key_file} порожній або має хибний формат "
            f"(очікується {PII_KEY_HEX_CHARS} шістнадцяткових символів); "
            "виправте його або запустіть з --rotate-pii-key"
        )
    return key


def _resolve_key() -> bytes:
    """Ключ: env `mcp_baf_PII_KEY` > файл `<cache_dir>/pii.key` > эфемерный.

    Файл создаётся при первом использовании (0600). Некорректный env-ключ
    — ошибка конфигурации, а не тихий фолбэк: молча «плавающие» токены
    выглядят как работающий маскировщик. Проверка дублирует
    `configure_pii` — библиотечное использование без него тоже fail-closed.
    """
    global _key
    if _key is not None:
        return _key
    env_raw = os.environ.get(PII_KEY_ENV, "").strip()
    if env_raw:
        _check_env_key()
        _key = bytes.fromhex(env_raw)
        return _key
    if _key_file:
        try:
            key = _read_key_file()
        except FileNotFoundError:  # только отсутствие файла создаёт ключ
            key = secrets.token_bytes(PII_KEY_BYTES)
            if not _write_key_file(key):
                key = _read_key_file()  # соседний процесс успел раньше
        # Файл мог быть создан вне инструмента (umask, cp, git checkout)
        # с 0644: поднимаем режим к задокументированному 0600. Не смогли —
        # падение, а не работа с миром-читаемым ключом.
        os.chmod(_key_file, 0o600)
        _key = key
        return _key
    # Библиотечное использование без кэш-каталога: соль на процесс,
    # как до issue #53 (токены стабильны в сессии, но не между рестартами).
    _key = secrets.token_bytes(PII_KEY_BYTES)
    return _key


def rotate_pii_key() -> bytes:
    """Выпускает новый ключ (и перезаписывает файл, если он настроен)."""
    global _key
    _key = secrets.token_bytes(PII_KEY_BYTES)
    if _key_file:
        _write_key_file(_key, replace=True)
    return _key


def pii_token(value: Any) -> str:
    """Стабильный в пределах ключа токен вместо значения (HMAC-SHA256)."""
    digest = hmac.new(_resolve_key(), str(value).encode("utf-8"),
                      hashlib.sha256).hexdigest()
    return f"PII:{digest[:8]}"


def scrub_pii_text(text: str, repl: Callable[[str], str]) -> str:
    """Заменяет телефон/email на repl(match), идентификатороподобные токены
    (GUID, артикулы, e1cib-ссылки) оставляет нетронутыми."""
    return PII_TEXT_RE.sub(
        lambda m: m.group() if m.group("ident") else repl(m.group()),
        text,
    )


def mask_pii_value(value: Any) -> Any:
    """Маскирует значение: непустые строки — по regex, остальное как есть."""
    if isinstance(value, str) and value:
        return scrub_pii_text(value, pii_token)
    return value


def mask_pii_text(value: Any) -> str:
    """Маскирует свободный текст (None -> пустая строка) по regex ПДн.

    Используется каналами без табличной структуры: журнал регистрации,
    структура формы, найденный код.
    """
    if value is None:
        return ""
    return scrub_pii_text(str(value), pii_token)


def mask_pii_result(r: dict[str, Any]) -> dict[str, Any]:
    """Маскирует ПДн в строках результата: по имени колонки и по regex.

    Базовые маркеры `PII_COLUMN_MARKERS` дополняются пользовательскими из
    `mcp_baf_PII_COLUMN_MARKERS` / `--pii-column-markers` (issue #53, п.1).
    Если хотя бы одна колонка замаскирована по имени, в ответ добавляется
    `masked_columns` — агенту видно, каким столбцам не доверять (п.4).
    """
    columns = r.get("columns") or []
    markers = PII_COLUMN_MARKERS + _extra_markers
    sensitive = [
        any(m in str(c).rsplit(".", 1)[-1].lower() for m in markers)
        for c in columns
    ]

    def mask(i: int, v: Any) -> Any:
        if v is None or v == "":
            return v
        if i < len(sensitive) and sensitive[i]:
            return pii_token(v)
        return mask_pii_value(v)

    rows = r.get("rows")
    if rows is None:
        rows = []
    # Молчаливый пропуск маскирования — утечка ПДн: контракт должен падать явно.
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise ValueError(
            "execute_query: ответ 1С содержит rows не в виде списка списков — "
            "маскирование ПДн невозможно. Отключите --mask-pii или проверьте "
            "контракт расширения (/query)."
        )
    masked = [[mask(i, v) for i, v in enumerate(row)] for row in rows]
    out = {**r, "rows": masked}
    masked_columns = [c for c, s in zip(columns, sensitive) if s]
    if masked_columns:
        out["masked_columns"] = masked_columns
    return out
