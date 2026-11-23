"""Issue #163: --mask-pii не должен порождать запросы к настройкам/ПДн-конфигу.

Регресс vladimir-kharin/1c_mcp #35: чтение настроек маскирования (через список
пользователей ИБ) выполнялось безусловно — и пользователь без права
«Администрирование» терял все вызовы, даже когда маскирование выключено.
Контракт mcp-baf: маскирование ПДн считается полностью локально
(`mcp_baf.pii`), набор HTTP-запросов к 1С не зависит от флага --mask-pii,
а каждый инструмент ходит только в свой эндпоинт (плюс /version и
/capabilities сервера). Риск kharin живёт на стороне BSL — его закрепляет
отдельный текстовый контракт Module.bsl ниже.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx
import pytest
from mcp.client import Client

from mcp_baf import pii
from mcp_baf.access import TOOL_METHODS
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.server import EXPECTED_EXTENSION_VERSION, create_server

PHONE = "0671234567"
REF = "12345678-1234-4234-8234-123456789abc"
MODULE = Path(__file__).parents[1]/"src/mcp_baf/extension_src/HTTPServices/MCPService/Ext/Module.bsl"
SERVER_PATHS = {"/version", "/capabilities"}

# Минимальные валидные аргументы: каждый инструмент обязан дойти до 1С.
TOOL_ARGS = {
    "get_metadata_tree": {},
    "get_object_structure": {"object_type": "Catalog", "object_name": "Tovary"},
    "get_form_structure": {"object_type": "Catalog", "object_name": "Tovary"},
    "get_configuration_info": {},
    "execute_query": {"query": "ВЫБРАТЬ Телефон ИЗ Справочник.Товары"},
    "validate_query": {"query": "ВЫБРАТЬ 1"},
    "get_event_log": {"limit": 10},
    "find_object_references": {"ref": REF, "ref_kind": "Справочник.Товары"},
    "get_object_link": {"mode": "make", "ref": REF, "kind": "Справочник.Товары"},
    "get_metadata_rights": {"metadata_object": "Catalog.Tovary"},
}


def test_tool_args_cover_every_http_tool():
    assert TOOL_ARGS.keys() == TOOL_METHODS.keys()


def _run_all_tools(tmp_path, mask_pii: bool) -> tuple[list[str], dict[str, list[str]], str]:
    """Полный сервер (lifespan, AccessMCP, OneCClient) поверх MockTransport.

    Возвращает запросы старта, запросы каждого инструмента и вывод execute_query.
    """
    pii.configure_pii(cache_dir=str(tmp_path), enabled=mask_pii)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/hs/mcp-baf")
        requests.append(path)
        if path == "/capabilities":
            return httpx.Response(200, json={"methods": list(TOOL_METHODS.values())})
        if path == "/version":
            return httpx.Response(200, json={"version": EXPECTED_EXTENSION_VERSION})
        if path == "/query":
            return httpx.Response(200, json={"columns": ["Телефон"], "rows": [[PHONE]]})
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    mp = pytest.MonkeyPatch()
    mp.setattr("mcp_baf.server.OneCClient", lambda config, **kw: OneCClient(config, transport, **kw))
    try:
        server = create_server(Config(base_url="http://test/hs/mcp-baf",
                                      cache_dir=str(tmp_path), mask_pii=mask_pii))
    finally:
        mp.undo()

    async def scenario():
        per_tool: dict[str, list[str]] = {}
        query_out = ""
        async with Client(server) as client:
            for _ in range(100):  # проверка версии — фоновая задача lifespan
                if "/version" in requests:
                    break
                await asyncio.sleep(0.01)
            await client.list_tools()
            startup = list(requests)
            for name, args in TOOL_ARGS.items():
                before = len(requests)
                result = await client.call_tool(name, args)
                per_tool[name] = requests[before:]
                if name == "execute_query":
                    query_out = "".join(getattr(c, "text", "") for c in result.content)
        return startup, per_tool, query_out

    try:
        return asyncio.run(scenario())
    finally:
        pii.configure_pii(cache_dir="", enabled=False)


@pytest.mark.parametrize("mask_pii", [False, True], ids=["mask-off", "mask-on"])
def test_each_tool_hits_only_its_own_endpoint(tmp_path, mask_pii):
    startup, per_tool, _ = _run_all_tools(tmp_path, mask_pii)
    assert set(startup) == SERVER_PATHS
    for name, paths in per_tool.items():
        endpoint = "/" + TOOL_METHODS[name].rsplit(".", 1)[0]
        own = [p for p in paths if p.split("/")[:2] == endpoint.split("/")]
        assert own, f"{name}: не дошёл до {endpoint}"
        extra = [p for p in paths if p not in own and p not in SERVER_PATHS]
        assert not extra, f"{name}: лишние запросы {extra}"


def test_request_set_independent_of_mask_flag(tmp_path):
    startup_off, off, out_off = _run_all_tools(tmp_path/"off", mask_pii=False)
    startup_on, on, out_on = _run_all_tools(tmp_path/"on", mask_pii=True)
    assert set(startup_off) == set(startup_on)
    # кэш /capabilities может дать разное число повторов — сравниваем эндпоинты
    assert {k: set(v) - SERVER_PATHS for k, v in off.items()} == \
           {k: set(v) - SERVER_PATHS for k, v in on.items()}
    # флаг реально подключён: off — открытый текст, on — токен PII:
    assert PHONE in out_off
    assert PHONE not in out_on and "PII:" in out_on
    # выключенный флаг не создаёт ключ
    assert not (tmp_path/"off"/pii.PII_KEY_FILENAME).exists()


def _bsl_code() -> str:
    text = MODULE.read_text(encoding="utf-8-sig")
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def test_extension_reads_no_settings_storage():
    # kharin #35: чтение хранилищ настроек требует прав, которых нет у неадмина
    code = _bsl_code()
    for api in ("ХранилищеОбщихНастроек", "ХранилищеСистемныхНастроек",
                "ХранилищеНастроекДанныхФорм", "ХранилищеПользовательскихНастроекОтчетов"):
        assert api not in code, api


def test_infobase_users_read_only_after_admin_check():
    # ПользователиИнформационнойБазы доступен только администратору: каждое
    # обращение должно стоять после явной проверки «Администрирование» в той же
    # процедуре, иначе неадмин получит ошибку вместо 403.
    code = _bsl_code()
    hits = [m.start() for m in re.finditer(r"ПользователиИнформационнойБазы\.", code)]
    assert hits
    for pos in hits:
        starts = [m.start() for m in re.finditer(r"^\s*(?:Процедура|Функция)\s", code[:pos], re.M)]
        body = code[starts[-1] if starts else 0:pos]
        assert 'ПравоДоступа("Администрирование"' in body, code[:pos].count("\n") + 1
