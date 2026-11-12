"""Тесты аудита HTTP-вызовов 1С: ровно одно событие one_c.http на запрос,
разделённые таймауты и политика повторов."""

import asyncio
import json

import httpx
import pytest

from mcp_baf_audit import AuditLog, set_trace_id
from mcp_baf.client import OneCClient, OneCError, scrub_error_detail
from mcp_baf.config import Config


def _events(tmp_path):
    lines = (tmp_path / "audit.log").read_text("utf-8").splitlines()
    return [json.loads(line) for line in lines]


def _client(tmp_path, handler, **config_kwargs):
    audit = AuditLog(str(tmp_path))
    config_kwargs.setdefault("retry_backoff", 0)  # тесты не должны спать
    config = Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path),
                    **config_kwargs)
    return OneCClient(config, transport=httpx.MockTransport(handler), audit=audit)


def test_one_c_http_logged_on_success(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    set_trace_id(None)
    client = _client(tmp_path, handler)
    asyncio.run(client.post("/query", {"query": "ВЫБРАТЬ 1"}))
    asyncio.run(client.aclose())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1  # ровно одно событие на запрос
    e = http[0]
    assert e["ok"] is True
    assert e["status"] == 200
    assert e["payload"]["method"] == "POST"
    assert e["payload"]["endpoint"] == "/query"
    assert isinstance(e["payload"]["response_bytes"], int)
    assert isinstance(e["duration_ms"], int)
    assert e["payload"]["attempts"] == 1
    # тело запроса/ответа не логируется
    assert "ВЫБРАТЬ" not in json.dumps(e, ensure_ascii=False)


def test_one_c_http_logged_on_error(tmp_path):
    def handler(request):
        return httpx.Response(503, text="boom")

    set_trace_id(None)
    client = _client(tmp_path, handler)
    try:
        asyncio.run(client.get("/version"))
    except OneCError:
        pass
    asyncio.run(client.aclose())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    e = http[0]
    assert e["ok"] is False
    assert e["level"] == "error"
    assert e["status"] == 503
    assert e["error"]
    # 503 транзиентен: 1 попытка + 2 повтора по умолчанию
    assert e["payload"]["attempts"] == 3


def test_one_c_http_inherits_tool_trace_id(tmp_path):
    """one_c.http наследует trace_id, выставленный traced_text для инструмента."""
    from mcp_baf.tools.common import traced_text

    def handler(request):
        return httpx.Response(200, json={"ok": True})

    audit = AuditLog(str(tmp_path))
    config = Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path))
    client = OneCClient(config, transport=httpx.MockTransport(handler), audit=audit)

    async def scenario():
        async def run():
            await client.post("/query", {"query": "ВЫБРАТЬ 1"})
            return "ok"

        await traced_text(audit, "execute_query", run, args={})
        await client.aclose()

    set_trace_id(None)
    asyncio.run(scenario())

    events = _events(tmp_path)
    http = next(e for e in events if e["event"] == "one_c.http")
    call = next(e for e in events if e["event"] == "tool.call")
    assert http["trace_id"] == call["trace_id"]  # единая операция
    assert http["trace_id"]  # не null


def test_error_body_not_logged_and_message_scrubbed(tmp_path):
    body = "Секрет: ИНН 1234567890 тел +380 50 123-45-67 " + "x" * 5000

    def handler(request):
        return httpx.Response(500, text=body)

    set_trace_id(None)
    client = _client(tmp_path, handler)
    with pytest.raises(OneCError) as excinfo:
        asyncio.run(client.get("/query"))
    asyncio.run(client.aclose())

    message = str(excinfo.value)
    assert "Секрет" in message           # короткий фрагмент остаётся подсказкой
    assert "+380 50 123-45-67" not in message  # ПДн маскируются
    assert len(message) < 400            # тело не утекает целиком

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    assert http[0]["error"] == "http_500"
    assert http[0]["payload"]["error_kind"] == "http_500"
    dumped = json.dumps(http[0], ensure_ascii=False)
    assert "Секрет" not in dumped and "xxxx" not in dumped


def test_scrub_error_detail_masks_and_truncates():
    detail = "строка 1\nстрока 2  тел 0671234567 mail a.b@ex.com " + "y" * 1000
    out = scrub_error_detail(detail)
    assert "\n" not in out
    assert "0671234567" not in out and "a.b@ex.com" not in out
    assert out.startswith("строка 1 строка 2")
    assert len(out) <= 301 and out.endswith("…")


# ── Разделённые таймауты httpx ──


def test_timeouts_are_split_by_phase(tmp_path):
    """connect короткий, read — request_timeout: 300 с не должны висеть на connect."""
    cfg = Config(base_url="http://test/hs/mcp-baf", cache_dir=str(tmp_path),
                 request_timeout=300, connect_timeout=10, write_timeout=60,
                 pool_timeout=7)
    client = OneCClient(cfg, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    timeout = client._http.timeout
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (10, 300, 60, 7)
    asyncio.run(client.aclose())


def test_connect_timeout_defaults_are_short():
    cfg = Config()
    assert cfg.connect_timeout == 10
    assert cfg.pool_timeout == 10
    assert cfg.request_timeout == 300
    assert cfg.connect_timeout < cfg.request_timeout


# ── Повторы идемпотентных запросов ──


def _flaky_handler(responses, seen):
    """Отдаёт responses по порядку; исключения из списка поднимает как есть."""
    def handler(request):
        seen.append(request)
        item = responses[min(len(seen), len(responses)) - 1]
        if isinstance(item, Exception):
            raise item
        return item
    return handler


def test_retry_on_transport_error_then_success(tmp_path):
    seen = []
    handler = _flaky_handler([httpx.ConnectError("refused"), httpx.Response(200, json={"ok": 1})], seen)
    client = _client(tmp_path, handler)

    assert asyncio.run(client.get("/version")) == {"ok": 1}
    assert len(seen) == 2
    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1  # одно событие на логический вызов
    assert http[0]["ok"] is True
    assert http[0]["payload"]["attempts"] == 2
    asyncio.run(client.aclose())


def test_large_error_body_read_stops_early(tmp_path):
    """#79: тіло не-200 читається лише до 4 КиБ, а не повністю."""
    sent = []

    async def body():
        for _ in range(1000):  # ~1 МиБ, якщо вичитувати до кінця
            sent.append(1)
            yield b"x" * 1024

    client = _client(tmp_path, lambda request: httpx.Response(500, content=body()))
    with pytest.raises(OneCError, match="status 500"):
        asyncio.run(client.get("/query"))
    assert len(sent) <= 5
    asyncio.run(client.aclose())


def test_transport_error_not_hidden_by_mask_pii(tmp_path):
    """#78: при --mask-pii фраза-заглушка лише для тіла відповіді 1С;
    причину мережевої помилки агент бачить (через scrub_error_detail)."""
    handler = _flaky_handler([httpx.ConnectError("Name or service not known")], [])
    client = _client(tmp_path, handler, mask_pii=True, retry_attempts=0)
    with pytest.raises(OneCError, match="Name or service not known"):
        asyncio.run(client.get("/version"))
    assert not [e for e in _events(tmp_path) if e["event"] == "pii.error_text"]
    asyncio.run(client.aclose())


@pytest.mark.parametrize("status", [502, 503, 504])
def test_retry_on_transient_5xx(tmp_path, status):
    seen = []
    handler = _flaky_handler([httpx.Response(status, text="busy"), httpx.Response(200, json={})], seen)
    client = _client(tmp_path, handler)

    assert asyncio.run(client.post("/query", {"query": "ВЫБРАТЬ 1"})) == {}
    assert len(seen) == 2
    asyncio.run(client.aclose())


@pytest.mark.parametrize("status", [400, 401, 404, 422, 500, 501])
def test_no_retry_on_deterministic_status(tmp_path, status):
    seen = []
    handler = _flaky_handler([httpx.Response(status, text="nope")], seen)
    client = _client(tmp_path, handler)

    with pytest.raises(OneCError):
        asyncio.run(client.get("/version"))
    assert len(seen) == 1
    asyncio.run(client.aclose())


def test_no_retry_on_read_timeout(tmp_path):
    seen = []
    handler = _flaky_handler([httpx.ReadTimeout("slow")], seen)
    client = _client(tmp_path, handler)

    with pytest.raises(OneCError, match="executing request to 1C"):
        asyncio.run(client.get("/version"))
    assert len(seen) == 1
    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    # ReadTimeout — таймаут, а не «транспортная ошибка»: честный ярлык в аудите.
    assert http[0]["error"] == "timeout"
    assert http[0]["payload"]["error_kind"] == "timeout"
    assert http[0]["payload"]["attempts"] == 1
    asyncio.run(client.aclose())


def test_write_timeout_is_labelled_timeout(tmp_path):
    """WriteTimeout — той самий клас, що й ReadTimeout: ярлик timeout, без повтора."""
    seen = []
    handler = _flaky_handler([httpx.WriteTimeout("write stalled")], seen)
    client = _client(tmp_path, handler)

    with pytest.raises(OneCError, match="executing request to 1C"):
        asyncio.run(client.post("/query", {"query": "ВЫБРАТЬ 1"}))
    assert len(seen) == 1
    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    assert http[0]["error"] == "timeout"
    assert http[0]["payload"]["error_kind"] == "timeout"
    asyncio.run(client.aclose())


# ── Дедлайн запроса (issue #48) ──


class _DripStream(httpx.AsyncByteStream):
    """Медленно «капающий» ответ: read-таймаут на чанк не срабатывает."""

    async def __aiter__(self):
        for _ in range(10_000):
            await asyncio.sleep(0.01)
            yield b" "


def test_request_deadline_aborts_drip_stream(tmp_path):
    """Drip-стрим не должен жить бесконечно: дедлайн → error_kind=timeout."""
    async def drip(request):
        return httpx.Response(200, stream=_DripStream())

    async def run():
        set_trace_id(None)
        client = _client(tmp_path, drip, request_deadline=0.2)
        with pytest.raises(OneCError, match="дедлайн"):
            await client.get("/query")
        await client.aclose()

    asyncio.run(run())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1  # ровно одно событие даже при дедлайне
    e = http[0]
    assert e["ok"] is False
    assert e["error"] == "timeout"
    assert e["payload"]["error_kind"] == "timeout"
    assert e["status"] == 200  # заголовки уже пришли, тело не дочитано
    assert e["payload"]["attempts"] == 1


def test_request_deadline_covers_all_retries(tmp_path):
    """Дедлайн — на весь вызов: повторы не продлевают его бесконечно."""
    seen = []
    handler = _flaky_handler([httpx.ConnectError("down")], seen)
    client = _client(tmp_path, handler, retry_attempts=10, retry_backoff=0.05,
                     request_deadline=0.2)

    with pytest.raises(OneCError, match="дедлайн"):
        asyncio.run(client.get("/version"))
    assert len(seen) >= 1
    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    # Причина незавершённого вызова — дедлайн, а не последняя попытка.
    assert http[0]["payload"]["error_kind"] == "timeout"
    assert http[0]["payload"]["attempts"] == len(seen)
    asyncio.run(client.aclose())


def test_request_deadline_zero_disables_it(tmp_path):
    """request_deadline=0 — без дедлайна (для тестов/особых сценариев)."""
    client = _client(tmp_path, lambda r: httpx.Response(200, json={}),
                     request_deadline=0)
    assert client._request_deadline == 0
    assert asyncio.run(client.get("/version")) == {}
    asyncio.run(client.aclose())


def test_external_cancellation_is_not_converted_to_deadline_error(tmp_path):
    """Зовнішня відміна (`asyncio.wait_for`/task.cancel) не має ставати
    `OneCError` дедлайну: `asyncio.timeout` перетворює на `TimeoutError` лише
    власне спрацювання, а чужий `CancelledError` проходить як є."""
    async def run():
        set_trace_id(None)
        started = asyncio.Event()

        async def slow(request):
            started.set()
            await asyncio.sleep(5)
            return httpx.Response(200, json={})

        client = _client(tmp_path, slow, request_deadline=10)
        task = asyncio.create_task(client.get("/query"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await client.aclose()

    asyncio.run(run())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    assert http[0]["ok"] is False  # отмена — не успех
    assert http[0]["payload"]["error_kind"] == "timeout"


def test_retry_exhausted_raises_and_logs_one_event(tmp_path):
    seen = []
    handler = _flaky_handler([httpx.ConnectError("down")], seen)
    client = _client(tmp_path, handler)

    with pytest.raises(OneCError, match="executing request to 1C"):
        asyncio.run(client.get("/version"))
    assert len(seen) == 3  # 1 попытка + 2 повтора по умолчанию
    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    assert http[0]["ok"] is False
    assert http[0]["payload"]["attempts"] == 3
    asyncio.run(client.aclose())


def test_retry_can_be_disabled(tmp_path):
    seen = []
    handler = _flaky_handler([httpx.ConnectError("down")], seen)
    client = _client(tmp_path, handler, retry_attempts=0)

    with pytest.raises(OneCError):
        asyncio.run(client.get("/version"))
    assert len(seen) == 1
    asyncio.run(client.aclose())


def test_no_retry_for_non_idempotent_request(tmp_path):
    """Запись не повторяется без явного флага (idempotent=False)."""
    seen = []
    handler = _flaky_handler([httpx.Response(503, text="busy")], seen)
    client = _client(tmp_path, handler)

    with pytest.raises(OneCError):
        asyncio.run(client.post("/write", {"x": 1}, idempotent=False))
    assert len(seen) == 1
    asyncio.run(client.aclose())


def test_non_idempotent_retried_only_with_explicit_flag(tmp_path):
    seen = []
    handler = _flaky_handler([httpx.Response(503, text="busy"), httpx.Response(200, json={})], seen)
    client = _client(tmp_path, handler, retry_non_idempotent=True)

    assert asyncio.run(client.post("/write", {"x": 1}, idempotent=False)) == {}
    assert len(seen) == 2
    asyncio.run(client.aclose())


def test_retry_backoff_is_exponential(tmp_path, monkeypatch):
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("mcp_baf.client.asyncio.sleep", fake_sleep)
    seen = []
    handler = _flaky_handler([httpx.ConnectError("down")], seen)
    client = _client(tmp_path, handler, retry_attempts=2, retry_backoff=0.25)

    with pytest.raises(OneCError):
        asyncio.run(client.get("/version"))
    assert delays == [0.25, 0.5]
    asyncio.run(client.aclose())


def test_wait_for_timeout_logged_as_error_not_success(tmp_path):
    """Отмена по asyncio.wait_for — не успех: ok=false, error_kind=timeout.

    httpx-таймаут приходит как TransportError, а wait_for отменяет корутину
    без исключения httpx, поэтому раньше finally писал ok=true, status=null.
    """
    async def slow(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json={"methods": []})

    async def run():
        set_trace_id(None)
        client = _client(tmp_path, slow)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.get("/capabilities"), 0.05)
        await client.aclose()

    asyncio.run(run())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1  # ровно одно событие даже при отмене
    e = http[0]
    assert e["ok"] is False
    assert e["level"] == "error"
    assert e["error"] == "timeout"
    assert e["payload"]["error_kind"] == "timeout"
    assert e["status"] is None
    assert e["payload"]["attempts"] == 1


def test_external_cancel_propagates_and_is_logged(tmp_path):
    """Внешняя отмена не глотается и тоже не выглядит успехом в аудите."""
    async def slow(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json={})

    async def run():
        set_trace_id(None)
        client = _client(tmp_path, slow)
        task = asyncio.create_task(client.get("/version"))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()  # CancelledError дошёл до вызывающего
        await client.aclose()

    asyncio.run(run())

    http = [e for e in _events(tmp_path) if e["event"] == "one_c.http"]
    assert len(http) == 1
    e = http[0]
    assert e["ok"] is False
    assert e["error"] == "timeout"
    assert e["payload"]["error_kind"] == "timeout"
