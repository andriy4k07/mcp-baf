"""https-транспорт: токен обязателен, plain http — двойной opt-in, TLS c генерируемым CA."""

import os
import socket
import ssl
import subprocess
import sys
import time

import httpx
import pytest

from mcp_baf import config
from mcp_baf.tls import ensure_self_signed, self_signed_hosts


def _load(*argv):
    return config.load_config(config.parse_args(list(argv)))


def test_stdio_is_default_and_needs_no_token(monkeypatch):
    monkeypatch.delenv("mcp_baf_TRANSPORT", raising=False)
    assert _load().transport == "stdio"


@pytest.mark.parametrize("argv, message", [
    (["--transport", "http", "--http-token", "t"], "--allow-insecure-http"),
    (["--transport", "https"], "bearer token"),
    (["--transport", "https", "--http-token", "t", "--tls-cert", "/c.pem"], "mcp_baf_TLS_KEY"),
])
def test_network_transport_guards(argv, message):
    with pytest.raises(config.ConfigError, match=message):
        _load(*argv)


def test_transport_options_from_env(monkeypatch):
    monkeypatch.setenv("mcp_baf_TRANSPORT", "http")
    monkeypatch.setenv("mcp_baf_ALLOW_INSECURE_HTTP", "1")
    monkeypatch.setenv("mcp_baf_HTTP_TOKEN", "tok")
    monkeypatch.setenv("mcp_baf_HTTP_PORT", "9100")
    cfg = _load()
    assert (cfg.transport, cfg.allow_insecure_http, cfg.http_token, cfg.http_port) == (
        "http", True, "tok", 9100)


def test_self_signed_ca_verifies_strictly(tmp_path):
    ca, cert, key = ensure_self_signed(str(tmp_path), self_signed_hosts("mcp-baf"))
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert, key)
    client_ctx = ssl.create_default_context(cafile=ca)
    client_ctx.verify_flags |= ssl.VERIFY_X509_STRICT  # дефолт Python 3.13+
    c_in, c_out, s_in, s_out = (ssl.MemoryBIO() for _ in range(4))
    client = client_ctx.wrap_bio(c_in, c_out, server_hostname="mcp-baf")
    server = server_ctx.wrap_bio(s_in, s_out, server_side=True)
    done = {"c": False, "s": False}
    for _ in range(10):
        for name, side, out, peer_in in (("c", client, c_out, s_in), ("s", server, s_out, c_in)):
            if not done[name]:
                try:
                    side.do_handshake()
                    done[name] = True
                except ssl.SSLWantReadError:
                    pass
            peer_in.write(out.read())
    assert all(done.values())


def test_https_server_end_to_end(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("mcp_baf_")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_baf", "--base", "http://127.0.0.1:9/hs/mcp-baf",
         "--cache-dir", str(tmp_path), "--quiet", "--transport", "https",
         "--http-port", str(port), "--http-token", "tok"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )
    url = f"https://localhost:{port}/mcp"
    ca = tmp_path / "tls" / "ca.crt"
    try:
        deadline = time.monotonic() + 30
        while True:
            assert proc.poll() is None, proc.stderr.read()
            try:
                if ca.exists():
                    verify = ssl.create_default_context(cafile=str(ca))
                    denied = httpx.post(url, verify=verify)
                    break
            except httpx.ConnectError:
                pass
            assert time.monotonic() < deadline, "server did not come up"
            time.sleep(0.2)
        assert denied.status_code == 401
        allowed = httpx.post(url, verify=verify, headers={
            "Authorization": "Bearer tok", "Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"}}})
        assert allowed.status_code == 200, allowed.text
    finally:
        proc.terminate()
        proc.wait(timeout=10)
