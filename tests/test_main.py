"""Режим установки и справка CLI не должны импортировать MCP-сервер."""

import subprocess
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('mode', ['--help', '--version', '--install'])
def test_cli_works_when_mcp_sdk_import_is_unavailable(tmp_path, mode):
    # Отдельный процесс исключает уже импортированный другими тестами SDK.
    script = '''
import importlib.abc
import sys

class UnavailableSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mcp" or fullname.startswith("mcp.") or fullname == "mcp_baf.server":
            raise ModuleNotFoundError("MCP SDK unavailable", name=fullname)

sys.meta_path.insert(0, UnavailableSDK())
from mcp_baf import installer
def install(**kwargs):
    assert kwargs["db_path"] == "TEST_DATABASE"
    print("MOCK_INSTALL_CALLED")
installer.install = install
from mcp_baf.__main__ import main
sys.argv = ["mcp-baf"] + sys.argv[1:]
main()
'''
    args = [mode]
    if mode == '--install':
        args += ['TEST_DATABASE', '--cache-dir', str(tmp_path)]
    result = subprocess.run([sys.executable, '-c', script, *args], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    if mode == '--install':
        assert 'MOCK_INSTALL_CALLED' in result.stdout
        assert 'Extension installed successfully.' in result.stdout


# ── --install --dump: разбор --dump-extensions и связка с main() ──


def _run_main(monkeypatch, tmp_path, *argv):
    """main() с подменёнными install/dump; возвращает (calls, exit_code)."""
    from mcp_baf import installer
    from mcp_baf.__main__ import main

    calls = []
    monkeypatch.setattr(installer, "install", lambda **kw: calls.append(("install", kw)))
    monkeypatch.setattr(installer, "dump", lambda **kw: calls.append(("dump", kw))
                        or {"base_error": None, "extensions": {}})
    monkeypatch.setattr(sys, "argv", ["mcp-baf", "--cache-dir", str(tmp_path), *argv])
    try:
        main()
    except SystemExit as exc:
        return calls, exc.code
    return calls, 0


def test_install_dump_list_parsed_and_passed(monkeypatch, tmp_path):
    calls, code = _run_main(monkeypatch, tmp_path, "--install", "db", "--dump", "/out",
                            "--dump-extensions", "A, B,a")
    assert code == 0
    assert [c[0] for c in calls] == ["install", "dump"]
    assert calls[1][1]["extensions"] == ["A", "B", "a"]  # дубли снимает installer.dump


@pytest.mark.parametrize("value", [[], ["ALL"], ["all"]])
def test_install_dump_all_forms(monkeypatch, tmp_path, value):
    calls, code = _run_main(monkeypatch, tmp_path, "--install", "db", "--dump", "/out",
                            "--dump-extensions", *value)
    assert code == 0
    assert calls[1][1]["extensions"] == "all"


def test_install_without_dump_flag_does_not_export(monkeypatch, tmp_path):
    calls, code = _run_main(monkeypatch, tmp_path, "--install", "db")
    assert code == 0
    assert [c[0] for c in calls] == ["install"]


@pytest.mark.parametrize("argv", [
    ["--install", "db", "--dump-extensions"],   # без --dump
    ["--dump", "/out", "--dump-extensions"],    # без --install
])
def test_dump_extensions_requires_install_and_dump(monkeypatch, tmp_path, argv):
    calls, code = _run_main(monkeypatch, tmp_path, *argv)
    assert code == 1
    assert calls == []


@pytest.mark.parametrize("value", [",", " , ", "../x", "Catalogs", "A:B", "."])
def test_bad_extension_names_rejected_before_install(monkeypatch, tmp_path, value):
    calls, code = _run_main(monkeypatch, tmp_path, "--install", "db", "--dump", "/out",
                            f"--dump-extensions={value}")
    assert code == 1
    assert calls == []


def test_failed_extension_exits_1(monkeypatch, tmp_path):
    from mcp_baf import installer
    from mcp_baf.__main__ import _run_dump

    monkeypatch.setattr(installer, "dump",
                        lambda **kw: {"base_error": None, "extensions": {"A": "boom"}})
    args = SimpleNamespace(install="db", dump="/out", server=False, platform="",
                           db_user="", db_password="", platform_version="")
    with pytest.raises(SystemExit) as exc:
        _run_dump(args, ["A"])
    assert exc.value.code == 1


def test_base_dump_error_exits_1(monkeypatch, tmp_path):
    from mcp_baf import installer

    def boom(**kw):
        raise installer.InstallError("nope")

    monkeypatch.setattr(installer, "install", lambda **kw: None)
    monkeypatch.setattr(installer, "dump", boom)
    monkeypatch.setattr(sys, "argv", ["mcp-baf", "--cache-dir", str(tmp_path),
                                      "--install", "db", "--dump", "/out"])
    from mcp_baf.__main__ import main
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


# ── Защита от DNS-rebinding: включена по умолчанию ──


def _settings(**kwargs):
    from mcp_baf.config import Config
    from mcp_baf.__main__ import _http_security

    return _http_security(Config(**kwargs), "https")


def test_dns_rebinding_enabled_by_default():
    settings = _settings()
    assert settings.enable_dns_rebinding_protection is True
    # localhost-сценарии продолжают работать без настройки
    assert "localhost:8001" in settings.allowed_hosts
    assert "127.0.0.1:8001" in settings.allowed_hosts
    assert "[::1]:8001" in settings.allowed_hosts
    # публикация другого порта в Docker не ломает проверку Host
    assert "localhost:*" in settings.allowed_hosts
    assert "https://localhost:8001" in settings.allowed_origins
    # Origin сверяется точно: шаблона `:*` в origins быть не должно
    assert not any(o.endswith(":*") for o in settings.allowed_origins)


def test_dns_rebinding_default_accepts_bind_host_and_hostname():
    import socket

    settings = _settings(http_host="localhost", http_port=9000)
    assert f"{socket.gethostname()}:9000" in settings.allowed_hosts


def test_dns_rebinding_off_by_default_for_non_loopback_bind():
    for host in ("0.0.0.0", "::", "192.168.1.10"):
        assert _settings(http_host=host).enable_dns_rebinding_protection is False


def test_dns_rebinding_explicit_hosts_enable_it_on_wildcard_bind():
    settings = _settings(http_host="0.0.0.0", http_allowed_hosts="mcp-baf:8001")
    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == ["mcp-baf:8001"]


def test_dns_rebinding_rejects_foreign_host_and_accepts_localhost():
    """Функциональная проверка тем же middleware, что использует SDK."""
    from mcp.server.transport_security import TransportSecurityMiddleware

    mw = TransportSecurityMiddleware(_settings())
    assert mw._validate_host("localhost:8001") is True
    assert mw._validate_host("localhost:8443") is True  # шаблон :*
    assert mw._validate_host("evil.example.com:8001") is False
    assert mw._validate_origin("https://evil.example.com") is False


def test_dns_rebinding_explicit_hosts_replace_defaults():
    settings = _settings(http_allowed_hosts="mcp-baf:8001, mcp.example.lan:8001")
    assert settings.allowed_hosts == ["mcp-baf:8001", "mcp.example.lan:8001"]
    assert settings.allowed_origins == [
        "https://mcp-baf:8001", "https://mcp.example.lan:8001"]


def test_dns_rebinding_explicit_host_without_port_matches_any_port():
    """`--http-allowed-hosts mcp-baf` не должен превращать сервис в 421."""
    from mcp.server.transport_security import TransportSecurityMiddleware

    settings = _settings(http_allowed_hosts="mcp-baf", http_port=18001)
    assert settings.allowed_hosts == ["mcp-baf:*"]
    # Host — любой порт, Origin — только реальный порт сервиса
    assert settings.allowed_origins == ["https://mcp-baf:18001"]

    mw = TransportSecurityMiddleware(settings)
    assert mw._validate_host("mcp-baf:18001") is True
    assert mw._validate_host("mcp-baf:8001") is True
    assert mw._validate_host("evil.example.com:18001") is False
    assert mw._validate_origin("https://mcp-baf:18001") is True
    assert mw._validate_origin("https://mcp-baf:18002") is False
    assert mw._validate_origin("https://evil.example.com") is False


def test_dns_rebinding_explicit_host_with_port_stays_exact():
    from mcp.server.transport_security import TransportSecurityMiddleware

    settings = _settings(http_allowed_hosts="mcp-baf, mcp.example.lan:18001", http_port=8001)
    assert settings.allowed_hosts == ["mcp-baf:*", "mcp.example.lan:18001"]
    assert settings.allowed_origins == [
        "https://mcp-baf:8001", "https://mcp.example.lan:18001"]

    mw = TransportSecurityMiddleware(settings)
    assert mw._validate_host("mcp.example.lan:18001") is True
    assert mw._validate_host("mcp.example.lan:18002") is False
    assert mw._validate_origin("https://mcp.example.lan:18001") is True
    assert mw._validate_origin("https://mcp.example.lan:18002") is False


def test_dns_rebinding_ipv6_entries_are_bracketed():
    from mcp.server.transport_security import TransportSecurityMiddleware

    settings = _settings(http_allowed_hosts="[::1]:8001, [::2]")
    assert settings.allowed_hosts == ["[::1]:8001", "[::2]:*"]
    assert settings.allowed_origins == ["https://[::1]:8001", "https://[::2]:8001"]

    mw = TransportSecurityMiddleware(settings)
    assert mw._validate_host("[::1]:8001") is True
    assert mw._validate_host("[::1]:9000") is False
    assert mw._validate_host("[::2]:9000") is True
    assert mw._validate_origin("https://[::1]:8001") is True
    assert mw._validate_origin("https://[::2]:8001") is True
    assert mw._validate_origin("https://[::1]:9000") is False


def test_dns_rebinding_default_port_gets_bare_origin():
    """Для 80/443 браузер шлёт Origin без порту — додаємо й такий варіант."""
    from mcp.server.transport_security import TransportSecurityMiddleware

    settings = _settings(http_allowed_hosts="mcp-baf", http_port=443)
    assert settings.allowed_origins == ["https://mcp-baf:443", "https://mcp-baf"]

    mw = TransportSecurityMiddleware(settings)
    assert mw._validate_origin("https://mcp-baf") is True
    assert mw._validate_origin("https://mcp-baf:443") is True
    assert mw._validate_origin("https://mcp-baf:8443") is False


def test_split_host_port():
    from mcp_baf.tls import host_header, split_host_port

    assert split_host_port("mcp-baf") == ("mcp-baf", None)
    assert split_host_port("mcp-baf:18001") == ("mcp-baf", "18001")
    assert split_host_port("[::1]:8001") == ("::1", "8001")
    assert split_host_port("[::1]") == ("::1", None)
    assert split_host_port("::1") == ("::1", None)
    assert split_host_port("mcp-baf:") == ("mcp-baf", None)
    assert host_header("mcp-baf", None) == "mcp-baf:*"
    assert host_header("::1", "8001") == "[::1]:8001"


def test_dns_rebinding_empty_list_keeps_default_patterns():
    """Порожній список — поведінка #27: типові хости з портом і `:*`."""
    settings = _settings(http_allowed_hosts="")
    assert settings.allowed_hosts == _settings().allowed_hosts
    assert any(h.endswith(":*") for h in settings.allowed_hosts)
    assert all(":" in h for h in settings.allowed_hosts)


def test_dns_rebinding_can_be_disabled_with_warning(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="mcp_baf.__main__"):
        settings = _settings(dns_rebinding_protection=False)
    assert settings.enable_dns_rebinding_protection is False
    assert any("DNS-rebinding" in r.message for r in caplog.records)


def test_dns_rebinding_env_and_cli_switch(monkeypatch):
    from mcp_baf.config import load_config, parse_args

    monkeypatch.delenv("mcp_baf_HTTP_DISABLE_DNS_REBINDING", raising=False)
    assert load_config(parse_args([])).dns_rebinding_protection is True
    monkeypatch.setenv("mcp_baf_HTTP_DISABLE_DNS_REBINDING", "1")
    assert load_config(parse_args([])).dns_rebinding_protection is False
    monkeypatch.delenv("mcp_baf_HTTP_DISABLE_DNS_REBINDING")
    assert load_config(parse_args(["--disable-dns-rebinding"])).dns_rebinding_protection is False

