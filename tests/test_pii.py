"""Тесты маскирования ПДн в execute_query и подсистемы --mask-pii (#53)."""

import asyncio
import hashlib
import hmac
import importlib
import inspect
import json
import os
import pkgutil
import re
from pathlib import Path

import httpx
import pytest

from mcp_baf import pii
from mcp_baf.config import Config, load_config, parse_args
from mcp_baf.tools.query import mask_pii_result


@pytest.fixture(autouse=True)
def _isolate_pii_state(monkeypatch):
    """Глобальное состояние pii (ключ, маркеры) не течёт между тестами."""
    monkeypatch.delenv(pii.PII_KEY_ENV, raising=False)
    yield
    pii.configure_pii(cache_dir="", extra_column_markers=())


def _r(columns, rows):
    return {"columns": columns, "rows": rows, "total": len(rows)}


def test_column_masking_stable_tokens():
    out = mask_pii_result(_r(
        ["Контрагент.ИНН", "Сумма", "Телефон"],
        [["1234567890", 5, ""], ["1234567890", 7, "x"], ["999", 1, None]],
    ))["rows"]
    assert out[0][0].startswith("PII:") and out[0][0] == out[1][0] != out[2][0]
    assert out[0][1] == 5 and out[0][2] == "" and out[2][2] is None
    assert out[1][2].startswith("PII:")


def test_regex_phone_email():
    cell = "тел +380 50 123-45-67, 0671234567, a.b@ex.com; код 12345"
    out = mask_pii_result(_r(["Комментарий"], [[cell]]))["rows"][0][0]
    assert out.count("PII:") == 3 and "12345" in out and "@" not in out and "380" not in out


def test_config_default_env_cli(monkeypatch):
    monkeypatch.delenv("mcp_baf_MASK_PII", raising=False)
    assert load_config(parse_args([])).mask_pii is False
    monkeypatch.setenv("mcp_baf_MASK_PII", "1")
    assert load_config(parse_args([])).mask_pii is True
    monkeypatch.delenv("mcp_baf_MASK_PII")
    assert load_config(parse_args(["--mask-pii"])).mask_pii is True


# --- Маскирование вне execute_query: журнал, формы, код ---

def test_mask_pii_text_replaces_contacts_only():
    from mcp_baf.pii import mask_pii_text

    out = mask_pii_text("тел 0671234567, a.b@ex.com; код 12345")
    assert out.count("PII:") == 2 and "12345" in out
    assert mask_pii_text(None) == ""
    assert mask_pii_text(7) == "7"


# --- Issue #45: телефонний regex не повинен псувати identifier-токени ---

_GUID_LIKE_SAMPLES = [
    # 10-значний цифровий прогін, обмежений hex-літерами/дефісами — раніше
    # з'їдався телефонною альтернативою (клас ROCTUP/1c-mcp-toolkit#44).
    "a1b2c3d4-0123456789-abcdef-000000000000",
    "f1781d67-5012-4361-b3d4-0123456789ab",
    "0e1c2d3f-a0b1-c2d3-0123456789-abcd",
    "e1cib:data/Справочник.Номенклатура?value=f1781d67-5012-4361-b3d4-0123456789ab",
    "WBAKA0123456789AB12",  # VIN-подібний артикул
]


def test_guid_like_tokens_survive_masking():
    from mcp_baf.pii import mask_pii_text, mask_pii_value

    for sample in _GUID_LIKE_SAMPLES:
        assert mask_pii_value(sample) == sample, sample
        assert mask_pii_text(sample) == sample, sample


def test_phones_masked_around_guid_tokens():
    from mcp_baf.pii import mask_pii_text

    out = mask_pii_text(
        "клієнт f1781d67-5012-4361-b3d4-0123456789ab, тел 0671234567, "
        "код a1b2c3d4-0123456789-abcdef"
    )
    assert "f1781d67-5012-4361-b3d4-0123456789ab" in out
    assert "a1b2c3d4-0123456789-abcdef" in out
    assert "0671234567" not in out and out.count("PII:") == 1


def test_email_in_code_like_token_still_masked():
    from mcp_baf.pii import mask_pii_text

    out = mask_pii_text("владельця abc-def@mail.example.com не показувати")
    assert "@" not in out and out.count("PII:") == 1


def test_error_detail_scrub_keeps_guids():
    from mcp_baf.client import scrub_error_detail

    detail = "Ошибка обращения к Справочник.Номенклатура {a1b2c3d4-0123456789-abcdef-000000000000}; тел 0671234567"
    out = scrub_error_detail(detail)
    assert "a1b2c3d4-0123456789-abcdef-000000000000" in out
    assert "0671234567" not in out and "***" in out


def test_form_structure_masks_title_and_handlers():
    from mcp_baf.tools.form import format_form_structure

    form = {
        "name": "ФормаЭлемента",
        "title": "Карточка, тел +380 67 123-45-67",
        "elements": [{
            "name": "Телефон", "type": "Поле", "title": "client@example.com",
            "dataPath": "Объект.Телефон", "events": [],
        }],
        "commands": [],
        "handlers": [],
    }
    plain = format_form_structure(form)
    masked = format_form_structure(form, mask_pii=True)
    assert "+380 67 123-45-67" in plain and "client@example.com" in plain
    assert "123-45-67" not in masked and "client@example.com" not in masked
    assert masked.count("PII:") == 2
    assert "Объект.Телефон" in masked


def test_search_code_masks_context():
    from mcp_baf.dumpindex import Match
    from mcp_baf.tools.search_code import format_search_result

    matches = [Match(module="ОбщийМодуль.Почта", line=3,
                     context='Сообщить("client@example.com");', score=1.0)]
    plain = format_search_result(matches, 1, "почта", "smart")
    masked = format_search_result(matches, 1, "почта", "smart", mask_pii=True)
    assert "client@example.com" in plain
    assert "client@example.com" not in masked and "PII:" in masked
    assert "ОбщийМодуль.Почта" in masked


# --- Issue #53, п.1: маркеры секретов/долгов + пользовательские маркеры ---

def test_secret_debt_markers_mask_columns():
    out = mask_pii_result(_r(
        ["Пользователь.Логин", "Контрагент.НомерКарты", "Физлицо.СНИЛС",
         "Паспорт.Серия", "Паспорт.Номер", "Паспорт.КемВыдан",
         "Клиент.ЛицевойСчет", "Сумма"],
        [["ivan", "4444", "110-20-30", "78", "1234", "МВС України", "0001", 5]],
    ))["rows"][0]
    assert all(str(v).startswith("PII:") for v in out[:-1]), out
    assert out[-1] == 5


def test_extra_markers_env_and_cli(monkeypatch):
    assert load_config(parse_args([])).pii_column_markers == ""
    monkeypatch.setenv("mcp_baf_PII_COLUMN_MARKERS", "БонусныйСчет, ШтрихКод")
    cfg = load_config(parse_args([]))
    assert cfg.pii_column_markers == "БонусныйСчет, ШтрихКод"
    pii.configure_pii(extra_column_markers=pii.split_marker_list(cfg.pii_column_markers))
    out = mask_pii_result(_r(
        ["Клиент.БонусныйСчет", "Товар.ШтрихКод", "Ціна"],
        [["900", "4820000000000", 10]],
    ))["rows"][0]
    assert out[0].startswith("PII:") and out[1].startswith("PII:") and out[2] == 10
    monkeypatch.delenv("mcp_baf_PII_COLUMN_MARKERS")
    cli = load_config(parse_args(["--pii-column-markers", "ИмяФайла"]))
    assert cli.pii_column_markers == "ИмяФайла"


# --- Issue #53, п.4 (хвіст): перелік замаскованих колонок у відповіді ---

def test_masked_columns_reported_in_result_and_output():
    from mcp_baf.tools.query import format_query_result

    masked = mask_pii_result(_r(["Телефон", "Сумма"], [["0671234567", 5]]))
    assert masked["masked_columns"] == ["Телефон"]
    text = format_query_result(masked)
    assert "0671234567" not in text and "PII" in text
    assert "столбцы: Телефон" in text
    # Замаскованих за іменем колонок немає — зайвого ключа в ответі нема.
    assert "masked_columns" not in mask_pii_result(_r(["Сумма"], [[5]]))


# --- Issue #53, п.2: стабільний ключ токенов --------------------------------

def test_key_stable_across_restarts(tmp_path):
    pii.configure_pii(cache_dir=str(tmp_path))
    t1 = pii.pii_token("Іваненко Іван")
    key_file = tmp_path / pii.PII_KEY_FILENAME
    assert key_file.exists()
    assert key_file.stat().st_mode & 0o777 == 0o600
    assert len(bytes.fromhex(key_file.read_text("ascii"))) == pii.PII_KEY_BYTES
    pii.configure_pii(cache_dir=str(tmp_path))  # «рестарт»: ключ перечитується
    assert pii.pii_token("Іваненко Іван") == t1
    # Рівні значення — рівні токени, різні — різні.
    assert pii.pii_token("0671234567") == pii.pii_token("0671234567")
    assert pii.pii_token("0671234567") != pii.pii_token("0671234568")


def test_env_key_precedence_and_invalid(monkeypatch):
    key = "ab" * pii.PII_KEY_BYTES
    monkeypatch.setenv(pii.PII_KEY_ENV, key)
    pii.configure_pii(cache_dir="")
    expected = "PII:" + hmac.new(
        bytes.fromhex(key), b"x", hashlib.sha256
    ).hexdigest()[:8]
    assert pii.pii_token("x") == expected

    monkeypatch.setenv(pii.PII_KEY_ENV, "deadbeef")  # завороткий / не hex
    # Ревю #53 (MINOR): некоректний env-ключ — помилка запуску (configure_pii),
    # а не перший токен; в тексті лише очікувана довжина, не значення.
    with pytest.raises(ValueError) as ei:
        pii.configure_pii(cache_dir="")
    msg = str(ei.value)
    assert pii.PII_KEY_ENV in msg and str(pii.PII_KEY_HEX_CHARS) in msg
    assert "deadbeef" not in msg
    monkeypatch.delenv(pii.PII_KEY_ENV)


def test_invalid_env_key_fails_fast_without_leaking_value(monkeypatch):
    """MINOR реві #53: валідація mcp_baf_PII_KEY на старті, значення не витекає."""
    bad = "deadbeef" * 8 + "ab"  # валідний hex, хибна довжина (66)
    monkeypatch.setenv(pii.PII_KEY_ENV, bad)
    try:
        with pytest.raises(ValueError) as ei:
            pii.configure_pii(cache_dir="", rotate=True)  # і до ротації дійти не повинен
        msg = str(ei.value)
        assert pii.PII_KEY_ENV in msg and str(pii.PII_KEY_HEX_CHARS) in msg
        assert "deadbeef" not in msg
        # Бібліотечний шлях без configure_pii — той самий fail-closed на токені.
        with pytest.raises(ValueError):
            pii.pii_token("x")
    finally:
        monkeypatch.delenv(pii.PII_KEY_ENV)


def test_preexisting_weak_key_file_perms_are_tightened(tmp_path):
    """MINOR реві #53: 0600 у README — інваріант, а не лише режим створення.

    Файл, створений поза інструментом із 0644 (umask, cp), мусить бути
    піджатий і при читанні ключа, і при ротації (режим O_CREAT для
    наявного файлу ігнорується)."""
    kf = tmp_path / pii.PII_KEY_FILENAME
    kf.write_text("aa" * pii.PII_KEY_BYTES, "ascii")
    os.chmod(kf, 0o644)
    pii.configure_pii(cache_dir=str(tmp_path))
    assert pii.pii_token("x").startswith("PII:")  # читання існуючого файлу
    assert kf.stat().st_mode & 0o777 == 0o600
    # Ротація перезаписує наявний файл: O_CREAT-режим не діє — рятує fchmod.
    os.chmod(kf, 0o644)
    pii.rotate_pii_key()
    assert kf.stat().st_mode & 0o777 == 0o600
    # І шлях «бітий файл -> перевипуск» не залишає слабкий режим.
    kf.write_text("not-hex", "ascii")
    os.chmod(kf, 0o640)
    pii.configure_pii(cache_dir=str(tmp_path))
    assert pii.pii_token("x").startswith("PII:")
    assert kf.stat().st_mode & 0o777 == 0o600


def test_rotate_pii_key_breaks_and_freezes_tokens(tmp_path):
    pii.configure_pii(cache_dir=str(tmp_path))
    t1 = pii.pii_token("тел 067")
    pii.rotate_pii_key()
    t2 = pii.pii_token("тел 067")
    assert t2 != t1
    pii.configure_pii(cache_dir=str(tmp_path))  # рестарт читає новий ключ
    assert pii.pii_token("тел 067") == t2
    # Конфігуровація з rotate=True — теж ротація (шлях --rotate-pii-key).
    pii.configure_pii(cache_dir=str(tmp_path), rotate=True)
    assert pii.pii_token("тел 067") != t2


def test_rotate_cli_flag_and_ephemeral_without_cache_dir():
    assert load_config(parse_args([])).rotate_pii_key is False
    assert load_config(parse_args(["--rotate-pii-key"])).rotate_pii_key is True
    # Без каталогу (бібліотечне використання) — ефемерний ключ, файл не створюється.
    pii.configure_pii(cache_dir="")
    assert pii.pii_token("x") == pii.pii_token("x")


# --- Issue #53, п.3: фіксована фраза + подія pii.error_text в аудиті --------

def _pii_client(tmp_path, handler, mask_pii_flag):
    from mcp_baf.client import OneCClient
    from mcp_baf_audit import AuditLog

    cfg = Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path),
                 mask_pii=mask_pii_flag)
    return OneCClient(cfg, transport=httpx.MockTransport(handler),
                      audit=AuditLog(str(tmp_path)))


def _audit_events(tmp_path):
    return [json.loads(line)
            for line in (tmp_path / "audit.log").read_text("utf-8").splitlines()]


@pytest.mark.parametrize("mask_pii_flag", [True, False])
def test_error_body_masked_phrase_and_audit_event(tmp_path, mask_pii_flag):
    from mcp_baf.client import OneCError

    body = ("Ошибка обращения: Петренко Петро Петрович, вул. Хрещатик 1, "
            "тел 0671234567, ref f1781d67-5012-4361-b3d4-0123456789ab")

    def handler(request):
        return httpx.Response(500, text=body)

    client = _pii_client(tmp_path, handler, mask_pii_flag)
    try:
        with pytest.raises(OneCError) as ei:
            asyncio.run(client.get("/query"))
    finally:
        asyncio.run(client.aclose())
    msg = str(ei.value)
    events = _audit_events(tmp_path)
    pii_events = [e for e in events if e["event"] == "pii.error_text"]
    if mask_pii_flag:
        # Агенту — константа: ні ПІБ, ні адреси, ні телефону.
        assert "Петренко" not in msg and "0671234567" not in msg
        assert "Хрещатик" not in msg
        assert "pii.error_text" in msg  # підказка, де шукати повний текст
        assert len(pii_events) == 1
        # Повний текст — саме в аудит: і ПІБ, і телефон, і адреса.
        assert "Петренко" in pii_events[0]["error_text"]
        assert "0671234567" in pii_events[0]["error_text"]
        assert "Хрещатик" in pii_events[0]["error_text"]
    else:
        # Стара поведінка: скрубований фрагмент, події pii.error_text нема.
        assert "Петренко" in msg and "0671234567" not in msg
        assert not pii_events


# --- Issue #53, п.4: описи інструментів документують семантику токенів ------

def _captured_tool_kwargs():
    from mcp_baf.tools import eventlog, form, query, search_code

    tools = {}

    class FakeMCP:
        def tool(self, **kw):
            return lambda f: tools.setdefault(kw["name"], kw)

    query.register(FakeMCP(), None, None, mask_pii=True)
    eventlog.register(FakeMCP(), None, None, mask_pii=True)
    form.register(FakeMCP(), None, None, mask_pii=True)
    search_code.register(FakeMCP(), None, None, mask_pii=True)
    return tools


@pytest.mark.parametrize("tool_name", [
    "execute_query", "get_event_log", "get_form_structure", "search_code",
])
def test_tool_descriptions_document_token_semantics(tool_name):
    description = _captured_tool_kwargs()[tool_name]["description"]
    for needle in ("PII:", "pii.key", "mcp_baf_PII_KEY", "Наименование",
                   "замаскирован"):
        assert needle in description, (tool_name, needle)


def test_masking_note_qualified_for_columnless_tools():
    """MINOR реві #53: «список замаскированных колонок» — лише для табличних
    відповідей. У журналу реєстрації/структури форми/знайденого коду колонок
    немає, тож безумовна обіцянка переконує агента шукати те, чого там не буває."""
    assert "список замаскированных колонок" in pii.MASKING_NOTE
    before = pii.MASKING_NOTE.split("список замаскированных колонок")[0]
    assert "таблич" in before[-60:], (
        "обіцянка списку колонок має бути кваліфікована табличними ответами"
    )


# --- Issue #53, п.5: інваріант реєстру + перемаскування голых 10-значних ----

def test_registry_invariant_all_maskable_tools_pass_mask_pii():
    """Кожен інструмент із mask-aware formatter зобов'язаний отримувати
    config.mask_pii з server.py (адаптація fail-closed прапорця kharin)."""
    from mcp_baf import server as server_module

    source = Path(inspect.getsourcefile(server_module)).read_text()
    register_calls = dict(re.findall(r"(\w+)\.register\(([^)\n]*)\)", source))

    import mcp_baf.tools as tools_pkg

    maskable = set()
    for module_info in pkgutil.iter_modules(tools_pkg.__path__):
        module = importlib.import_module(f"mcp_baf.tools.{module_info.name}")
        mask_aware_formatter = any(
            "mask_pii" in inspect.signature(obj).parameters
            for name, obj in vars(module).items()
            if name.startswith("format_") and callable(obj)
        ) or any(
            # execute_query маскується не formatter'ом, а mask_pii_result.
            getattr(obj, "__module__", "") == "mcp_baf.pii"
            for name, obj in vars(module).items()
        )
        if not mask_aware_formatter:
            continue
        maskable.add(module_info.name)
        assert module_info.name in register_calls, (
            f"{module_info.name} має mask-aware formatter, але не реєструється"
        )
        assert "mask_pii" in register_calls[module_info.name], (
            f"{module_info.name}.register викликається без config.mask_pii — "
            "канал ПДн без маскирування (fail-closed інваріант #53)"
        )
        register = getattr(module, "register", None)
        assert register is not None and "mask_pii" in inspect.signature(
            register
        ).parameters
    # Очікуваний набір фіксований: новий канал із mask-aware formatter
    # зобов'язаний з'явитися тут свідомо, а не «випасти» з інваріанта.
    assert maskable == {"eventlog", "form", "query", "search_code"}


def test_bare_ten_digit_zero_prefix_is_accepted_overmasking():
    """Рішення #53 п.5: голий 10-значний прогін із провідним нулем маскується як
    телефон — прийнятне перемаскування. Вимагати роздільники не можна:
    голі «0671234567» у вільному тексті — реальний канал витоку (#46)."""
    out = pii.mask_pii_text("код 0123456789 у коментарі")
    assert out.count("PII:") == 1 and "0123456789" not in out
