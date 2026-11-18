"""PID-файл, --stop, фон и установка службы (без реального Windows)."""

import os
import signal
import subprocess
import sys
from types import SimpleNamespace

from mcp_baf import installer, service


def test_pid_roundtrip_and_foreign_pid_kept(tmp_path):
    d = str(tmp_path)
    service.write_pid(d)
    assert service._read_pid(d) == os.getpid()
    service.remove_pid(d)
    assert service._read_pid(d) is None
    (tmp_path / service.PID_NAME).write_text("999999")
    service.remove_pid(d)  # чужой PID не трогаем
    assert service._read_pid(d) == 999999


def test_stop_kills_ours_and_removes_file(tmp_path, monkeypatch):
    (tmp_path / service.PID_NAME).write_text("4242")
    kills = []
    monkeypatch.setattr(service, "_is_ours", lambda pid: True)
    monkeypatch.setattr(os, "kill", lambda pid, sig: kills.append((pid, sig)))
    assert service.stop(str(tmp_path)) == 0
    assert kills == [(4242, signal.SIGTERM)]
    assert not (tmp_path / service.PID_NAME).exists()


def test_stop_stale_pid_and_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(service, "_is_ours", lambda pid: False)
    assert service.stop(str(tmp_path)) == 1
    (tmp_path / service.PID_NAME).write_text("4242")
    assert service.stop(str(tmp_path)) == 0
    assert not (tmp_path / service.PID_NAME).exists()
    assert "застарілий" in capsys.readouterr().out


def test_background_keys():
    assert all(service.is_background_key(c) for c in "dDвВ")
    assert not service.is_background_key("x")


def test_spawn_detached_command(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(sys, "argv", ["mcp-baf", "--transport", "https"])
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: seen.update(cmd=cmd, kw=kw))
    service.spawn_detached(str(tmp_path))
    assert seen["cmd"] == [sys.executable, "-m", "mcp_baf", "--transport", "https"]
    assert seen["kw"]["stdin"] == subprocess.DEVNULL and seen["kw"]["close_fds"]
    assert (tmp_path / service.CONSOLE_LOG_NAME).exists()


def _win_admin(monkeypatch, admin=True):
    monkeypatch.setattr(installer, "_is_windows", lambda: True)
    monkeypatch.setattr(installer, "_is_admin", lambda: admin)
    for k in list(os.environ):
        if k.lower().startswith("mcp_baf_"):
            monkeypatch.delenv(k)


def test_build_service_cmd(tmp_path):
    env = {"mcp_baf_USER": "MCP", "mcp_baf_PASSWORD_FILE": r"C:\p 100%.txt", "PATH": "x"}
    text = service.build_service_cmd(
        ["--install-service", "--cache-dir", "old", "--base", "http://h/a b"],
        str(tmp_path), env)
    lines = text.split("\r\n")
    assert lines[0] == "@echo off"
    assert 'set "mcp_baf_USER=MCP"' in lines
    assert r'set "mcp_baf_PASSWORD_FILE=C:\p 100%%.txt"' in lines
    assert 'set "PATH' not in text and " old" not in text
    run = lines[-2]
    assert "--install-service" not in run
    assert '"http://h/a b"' in run and run.endswith('2>&1')
    assert f'--cache-dir {subprocess.list2cmdline([str(tmp_path)])}' in run


def test_install_service_refuses_raw_secrets(tmp_path, monkeypatch):
    _win_admin(monkeypatch)
    calls = []
    monkeypatch.setattr(service, "_schtasks", lambda *a: calls.append(a))
    monkeypatch.setenv("mcp_baf_PASSWORD", "x")
    assert service.install_service(["--install-service"], str(tmp_path)) == 1
    monkeypatch.delenv("mcp_baf_PASSWORD")
    assert service.install_service(["--http-token=abc"], str(tmp_path)) == 1
    assert service.install_service(["--pass", "abc"], str(tmp_path)) == 1
    assert not calls


def test_install_service_requires_admin(tmp_path, monkeypatch):
    _win_admin(monkeypatch, admin=False)
    assert service.install_service([], str(tmp_path)) == 1
    assert service.uninstall_service() == 1


def test_install_service_schtasks(tmp_path, monkeypatch):
    _win_admin(monkeypatch)
    calls = []
    ok = SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(service, "_schtasks", lambda *a: calls.append(a) or ok)
    assert service.install_service(["--install-service", "--transport", "https"],
                                   str(tmp_path)) == 0
    cmd_path = str(tmp_path / "run-mcp-baf.cmd")
    assert os.path.exists(cmd_path)
    assert calls[0] == ("/create", "/tn", "mcp-baf", "/sc", "onstart", "/ru", "SYSTEM",
                        "/rl", "HIGHEST", "/f", "/tr", f'"{cmd_path}"')
    assert calls[1] == ("/run", "/tn", "mcp-baf")


def test_uninstall_service_ignores_not_found(monkeypatch, capsys):
    _win_admin(monkeypatch)
    bad = SimpleNamespace(returncode=1, stdout="", stderr="not found")
    calls = []
    monkeypatch.setattr(service, "_schtasks", lambda *a: calls.append(a) or bad)
    assert service.uninstall_service() == 0
    assert [c[0] for c in calls] == ["/end", "/delete"]


def test_find_cache_dir_from_scheduled_task(monkeypatch, tmp_path):
    xml = '<Exec><Command>"C:\\mcp-baf\\cache\\run-mcp-baf.cmd"</Command></Exec>'
    monkeypatch.setattr(service.os, "name", "nt")
    monkeypatch.delenv("mcp_baf_CACHE_DIR", raising=False)
    monkeypatch.setattr(service, "_schtasks", lambda *a: SimpleNamespace(returncode=0, stdout=xml))
    monkeypatch.setattr(service.os.path, "dirname", lambda p: p.rsplit("\\", 1)[0])
    assert service.find_cache_dir() == "C:\\mcp-baf\\cache"
    # Явный --cache-dir важнее службы.
    assert service.find_cache_dir(str(tmp_path)) == str(tmp_path)


def test_status_reports_server_and_logs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(service.os, "name", "posix")
    assert service.status(str(tmp_path)) == 1
    assert "не запущено" in capsys.readouterr().out
    service.write_pid(str(tmp_path))
    (tmp_path / "audit.log").write_text("x\n")
    assert service.status(str(tmp_path)) == 0
    out = capsys.readouterr().out
    assert f"PID {os.getpid()}" in out and "mcp-baf --logs audit" in out


def test_logs_tail_without_follow(tmp_path, capsys):
    assert service.logs("console", str(tmp_path), follow=False) == 1
    (tmp_path / "server-console.log").write_text("".join(f"l{i}\n" for i in range(60)), encoding="utf-8")
    assert service.logs("console", str(tmp_path), lines=3, follow=False) == 0
    assert capsys.readouterr().out == "l57\nl58\nl59\n"
