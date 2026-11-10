"""Тесты маскирования ПДн в execute_query."""

from mcp_baf.config import load_config, parse_args
from mcp_baf.tools.query import mask_pii_result


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
