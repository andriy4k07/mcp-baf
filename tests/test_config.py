"""Тесты конфигурации: приоритет defaults -> env -> CLI."""

from mcp_baf_audit import DEFAULT_AUDIT_ARCHIVES, DEFAULT_AUDIT_MAX_SIZE_MIB

from mcp_baf.config import load_config, parse_args


def test_audit_defaults():
    cfg = load_config(parse_args([]))
    assert cfg.audit_max_size_mib == DEFAULT_AUDIT_MAX_SIZE_MIB
    assert cfg.audit_archives == DEFAULT_AUDIT_ARCHIVES


def test_audit_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("mcp_baf_AUDIT_MAX_SIZE", "5")
    monkeypatch.setenv("mcp_baf_AUDIT_ARCHIVES", "7")
    cfg = load_config(parse_args([]))
    assert cfg.audit_max_size_mib == 5
    assert cfg.audit_archives == 7


def test_audit_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("mcp_baf_AUDIT_MAX_SIZE", "5")
    cfg = load_config(parse_args(["--audit-max-size", "11", "--audit-archives", "3"]))
    assert cfg.audit_max_size_mib == 11
    assert cfg.audit_archives == 3


def test_audit_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("mcp_baf_AUDIT_MAX_SIZE", "not-a-number")
    cfg = load_config(parse_args([]))
    assert cfg.audit_max_size_mib == DEFAULT_AUDIT_MAX_SIZE_MIB


def test_dump_dir_default_empty(monkeypatch):
    monkeypatch.delenv("mcp_baf_DUMP_DIR", raising=False)
    cfg = load_config(parse_args([]))
    assert cfg.dump_dir == ""


def test_dump_dir_from_env(monkeypatch):
    monkeypatch.setenv("mcp_baf_DUMP_DIR", "/dumps/from-env")
    cfg = load_config(parse_args([]))
    assert cfg.dump_dir == "/dumps/from-env"


def test_dump_dir_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("mcp_baf_DUMP_DIR", "/dumps/from-env")
    cfg = load_config(parse_args(["--dump", "/dumps/from-cli"]))
    assert cfg.dump_dir == "/dumps/from-cli"
