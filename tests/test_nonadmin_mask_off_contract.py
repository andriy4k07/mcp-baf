"""Issue #163: --mask-pii off must not cause requests to settings/PII-config.

Регресс vladimir-kharin/1c_mcp: чтение НАСТРОЕК маскирования (через список
пользователей ИБ) выполнялось безусловно — и пользователь без права
«Администрирование» терял все вызовы, даже когда маскирование выключено.
Контракт mcp-baf: маскирование ПДн считается полностью локально
(`mcp_baf.pii`), а значит набор HTTP-запросов к 1С НЕ зависит от флага
--mask-pii. Эти тесты закрепляют контракт списком вызовов: при --mask-pii off
к расширению уходят только эндпоинты данных, никаких /settings-подобных
чтений в контексте вызывающего пользователя.
"""

from __future__ import annotations

import asyncio

import pytest
from mcp_baf_audit import AuditLog

from mcp_baf import pii
from mcp_baf.tools import eventlog, form, objects, query

PHONE = "0671234567"

# Ожидаемый список вызовов: только эндпоинты данных инструментов.
EXPECTED_CALLS = [
    ("POST", "/query"),
    ("POST", "/eventlog"),
    ("GET", "/form/Catalog/Tovary"),
    ("POST", "/refs"),
]

# Подстроки пути, появление которых в списке вызовов = «чтение настроек в
# контексте вызывающего» (сценарий kharin: настройки маскирования/пользователей).
FORBIDDEN_SUBSTRINGS = ("setting", "pii", "mask", "policy", "user", "right")


class RecordingClient:
    """Замена OneCClient: пишет последовательность (метод, путь) каждого вызова."""

    def __init__(self, payloads: dict[str, dict]):
        self.payloads = payloads
        self.calls: list[tuple[str, str]] = []

    async def get(self, path, **kwargs):
        self.calls.append(("GET", path))
        return self.payloads[path]

    async def post(self, path, body=None, **kwargs):
        self.calls.append(("POST", path))
        return self.payloads[path]

    async def aclose(self):
        pass


def _payloads() -> dict[str, dict]:
    return {
        "/query": {"columns": ["Телефон"], "rows": [[PHONE]], "total": 1},
        "/eventlog": {
            "events": [{"date": "2026-11-23 10:00:00", "level": "Ошибка",
                        "event": "Тест", "comment": f"тел {PHONE}"}],
            "found": 1,
        },
        "/form/Catalog/Tovary": {"name": "ФормаТовара", "title": f"Товар {PHONE}"},
        "/refs": {"hits": []},
    }


def _invoke_maskable_tools(mask_pii: bool, tmp_path):
    """Регистрирует mask-aware инструменты с RecordingClient и вызывает каждый."""
    # Каждый вызов сбрасывает резолв ключа (это же «рестарт» для тестов).
    pii.configure_pii(cache_dir=str(tmp_path), enabled=mask_pii)
    audit = AuditLog(str(tmp_path))
    client = RecordingClient(_payloads())
    tools: dict = {}

    class FakeMCP:
        def tool(self, **kwargs):
            return lambda f: tools.setdefault(kwargs.get("name", f.__name__), f)

    query.register(FakeMCP(), client, audit, mask_pii)
    eventlog.register(FakeMCP(), client, audit, mask_pii)
    form.register(FakeMCP(), client, audit, "", mask_pii)
    objects.register(FakeMCP(), client, audit, mask_pii)

    async def scenario():
        return {
            "query": await tools["execute_query"](
                query="ВЫБРАТЬ Телефон ИЗ Справочник.Товары"),
            "eventlog": await tools["get_event_log"](limit=10),
            "form": await tools["get_form_structure"](
                object_type="Catalog", object_name="Tovary"),
            "refs": await tools["find_object_references"](
                ref="12345678-1234-4234-8234-123456789abc",
                ref_kind="Справочник.Товары"),
        }

    return client, asyncio.run(scenario())


def test_mask_off_no_settings_or_pii_config_requests(tmp_path):
    """--mask-pii off: список вызовов совпадает с ожидаемым буквально.

    Любая новая строка в списке («почитаю настройки маскирования перед
    вызовом») — это будущий kharin-регресс: нереагистрированное чтение
    настроек в контексте вызывающего ломает неадминистраторов.
    """
    client, outputs = _invoke_maskable_tools(mask_pii=False, tmp_path=tmp_path)
    assert client.calls == EXPECTED_CALLS
    for _, path in client.calls:
        low = path.lower()
        assert not any(f in low for f in FORBIDDEN_SUBSTRINGS), (
            f"запрос к настроечному эндпоинту при --mask-pii off: {path}"
        )
    # Выключенный флаг не создаёт и ключевую подсистему (pii.key не трогаем).
    assert not (tmp_path / pii.PII_KEY_FILENAME).exists()
    # off — данные идут открытым текстом (маскирование действительно выключено).
    assert PHONE in outputs["query"]


@pytest.mark.parametrize("flag", [True, False], ids=["mask-on", "mask-off"])
def test_call_list_independent_of_mask_flag(tmp_path, flag):
    """Набор HTTP-запросов не зависит от --mask-pii: маскирование локальное.

    Флаг меняет только постобработку ответа, не сеть: при включённом
    маскировании запросов «за настройками» быть не больше, чем при
    выключенном, — иначе включение флага стало бы правами-зависимым.
    """
    client_on, outputs_on = _invoke_maskable_tools(mask_pii=True, tmp_path=tmp_path / "on")
    client_off, outputs_off = _invoke_maskable_tools(mask_pii=False, tmp_path=tmp_path / "off")
    assert client_on.calls == client_off.calls == EXPECTED_CALLS
    # Флаг при этом genuinely wired: on — телефон схлопнут в токен PII:xxxx.
    assert PHONE not in outputs_on["query"] and "PII:" in outputs_on["query"]
    assert PHONE not in outputs_on["eventlog"]
    assert PHONE not in outputs_on["form"]
    assert PHONE in outputs_off["query"]
