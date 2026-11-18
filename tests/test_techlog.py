"""Тесты разбора технологического журнала и source=techlog в get_event_log."""

import asyncio
from datetime import datetime

import httpx
import pytest

from mcp_baf import techlog
from mcp_baf_audit import AuditLog
from mcp_baf.client import OneCClient
from mcp_baf.config import Config
from mcp_baf.tools import eventlog

LOG = (
    "﻿"
    "05:10.000001-2500000,TLOCK,5,process=rphost,connectID=11,Usr=Иванов,"
    "Regions=InfoRg1.DIMS,Locks='InfoRg1.DIMS Exclusive',WaitConnections=12\n"
    "05:11.000001-500000,TLOCK,5,connectID=12,Usr=Петров,Regions=InfoRg1.DIMS\n"
    "06:00.000002-0,TTIMEOUT,2,connectID=11,Usr=Иванов,WaitConnections=12,"
    "Regions=InfoRg1.DIMS,Context='Документ.Продажа.МодульОбъекта : 10\n"
    "    Запись(); ''тел +380501234567'''\n"
    "07:00.000003-0,TDEADLOCK,2,connectID=11,DeadlockConnectionIntersections='11 12 InfoRg1',"
    "Context=ctx\n"
    "08:00.000004-0,EXCP,2,Descr='Ошибка, с запятой',Context=x\n"
    "08:01.000004-0,EXCP,2,Descr='Ошибка, с запятой'\n"
    "09:00.000005-1,CALL,2,Usr=skip\n"
)


def make_log(tmp_path, name="rphost_100", file="26111805.log", text=LOG):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / file).write_bytes(text.encode("utf-8"))
    return tmp_path


def test_parse_props_quotes_and_multiline():
    p = techlog.parse_props("a=1,b='x, ''y''\nz',c=\"q\",d=end")
    assert p == {"a": "1", "b": "x, 'y'\nz", "c": "q", "d": "end"}


def test_scan_aggregates_all_events(tmp_path):
    make_log(tmp_path)
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5, 0), datetime(2026, 11, 18, 5, 59, 59))
    assert res.tlock == 2
    assert res.regions["InfoRg1.DIMS"] == [2, 3_000_000, 2_500_000]
    assert len(res.timeouts) == 1 and len(res.deadlocks) == 1


def test_scan_hour_file_events_and_multiline(tmp_path):
    # файл часа 05: минуты 00..59, поэтому 06:00 — это уже минута 6 того же файла
    make_log(tmp_path)
    out = techlog.format_techlog(
        techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5, 0), datetime(2026, 11, 18, 5, 59)), 50
    )
    assert "TLOCK): 2" in out and "InfoRg1.DIMS: 2 шт., ожидание 3.000 с" in out
    assert "Дедлоки (TDEADLOCK): 1" in out and "11 12 InfoRg1" in out
    assert "Таймауты блокировок (TTIMEOUT): 1" in out and "Запись(); 'тел" in out
    assert "EXCP): 2" in out and "2 x Ошибка, с запятой" in out
    assert "CALL" not in out and "﻿" not in out


def test_window_filters_by_name_and_time(tmp_path):
    make_log(tmp_path)
    # другой час — файл вообще не открывается
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 7), datetime(2026, 11, 18, 8))
    assert res.files == 0 and res.events_parsed == 0
    # окно внутри часа отсекает события по времени
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5, 5, 0), datetime(2026, 11, 18, 5, 5, 10, 500000))
    assert res.tlock == 1 and not res.deadlocks and res.excp_total == 0


def test_event_filter(tmp_path):
    make_log(tmp_path)
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5), datetime(2026, 11, 18, 5, 59), "EXCP")
    assert res.excp_total == 2 and res.tlock == 0
    out = techlog.format_techlog(res, 50)
    assert "EXCP): 2" in out and "TLOCK" not in out and "TDEADLOCK" not in out


def test_excp_grouped_without_guids(tmp_path):
    text = "".join(
        f"08:0{i}.000001-0,EXCP,2,Descr='Сеанс відсутній ID={g}'\n"
        for i, g in enumerate(["c27c64aa-946d-49de-ae45-f4d036262b3c",
                               "49453879-2bb3-45cb-9cc1-56447d41bd06"]))
    make_log(tmp_path, text=text)
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5), datetime(2026, 11, 18, 5, 59))
    assert res.excp == {"Сеанс відсутній ID=…": 2}


def test_mask_applied_to_context(tmp_path):
    from mcp_baf.pii import mask_pii_text

    make_log(tmp_path)
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5, 0), datetime(2026, 11, 18, 5, 59))
    assert "501234567" in techlog.format_techlog(res, 50)
    assert "501234567" not in techlog.format_techlog(res, 50, mask_pii_text)


def test_symlinks_and_broken_files_skipped(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    make_log(outside, "rphost_1")
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "rphost_link").symlink_to(outside / "rphost_1", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    res = techlog.scan(str(root), datetime(2026, 11, 18, 5), datetime(2026, 11, 18, 5, 59))
    assert res.files == 0
    d = root / "rphost_2"
    d.mkdir()
    (d / "26111805.log").mkdir()  # «файл», который нельзя прочитать
    (d / "garbage.log").write_text("x")
    res = techlog.scan(str(root), datetime(2026, 11, 18, 5), datetime(2026, 11, 18, 5, 59))
    assert res.events_parsed == 0  # не упало


def test_budgets(tmp_path, monkeypatch):
    monkeypatch.setattr(techlog, "MAX_EVENTS", 1)
    make_log(tmp_path)
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5), datetime(2026, 11, 18, 5, 59))
    assert res.events_parsed == 1
    monkeypatch.setattr(techlog, "MAX_EVENTS", 1000)
    monkeypatch.setattr(techlog, "MAX_BYTES", 10)
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5), datetime(2026, 11, 18, 5, 59))
    assert res.bytes_read <= techlog.MAX_BYTES + 400
    monkeypatch.setattr(techlog, "MAX_BYTES", 128 << 20)
    monkeypatch.setattr(techlog, "MAX_FILES", 1)
    make_log(tmp_path, "rphost_2")
    res = techlog.scan(str(tmp_path), datetime(2026, 11, 18, 5), datetime(2026, 11, 18, 5, 59))
    assert res.files == 1 and res.truncated


def test_parse_window_defaults_and_errors():
    now = datetime(2026, 11, 18, 12, 0)
    s, e = techlog.parse_window("", "", now)
    assert (e - s).total_seconds() == 3600
    with pytest.raises(ValueError):
        techlog.parse_window("bad", "")
    with pytest.raises(ValueError):
        techlog.parse_window("2026-11-18T10:00:00", "2026-11-18T09:00:00")


def _tool(tmp_path, **kw):
    tools = {}

    class FakeMCP:
        def tool(self, **_):
            return lambda f: tools.setdefault(f.__name__, f)

    client = OneCClient(Config(base_url="http://test"),
                        httpx.MockTransport(lambda r: httpx.Response(500)))
    eventlog.register(FakeMCP(), client, AuditLog(str(tmp_path / "audit")), **kw)
    return tools["get_event_log"]


def test_tool_techlog_source(tmp_path):
    logs = tmp_path / "tj"
    make_log(logs)
    tool = _tool(tmp_path, techlog_dir=str(logs))
    out = asyncio.run(tool(source="techlog", start_date="2026-11-18T05:00:00",
                           end_date="2026-11-18T05:59:00"))
    assert "Технологический журнал" in out and "InfoRg1.DIMS" in out


def test_tool_techlog_not_configured(tmp_path):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="techlog-dir"):
        asyncio.run(_tool(tmp_path)(source="techlog"))
