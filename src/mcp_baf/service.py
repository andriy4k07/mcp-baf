"""Управление сетевым экземпляром: PID-файл, --stop, фон, служба Windows.

Не импортирует MCP SDK (используется режимами --stop/--install-service).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys

from mcp_baf_audit import default_cache_dir

PID_NAME = "mcp-baf.pid"
CONSOLE_LOG_NAME = "server-console.log"
TASK_NAME = "mcp-baf"
# Секреты, которые нельзя класть в .cmd открытым текстом.
SECRET_ENV = ("mcp_baf_password", "mcp_baf_http_token", "mcp_baf_pii_key",
              "mcp_baf_db_password")
SECRET_FLAGS = ("--http-token", "--pass", "--password")


def resolve_cache_dir(cache_dir: str = "") -> str:
    return cache_dir or os.environ.get("mcp_baf_CACHE_DIR", "") or default_cache_dir("mcp-baf")


# Журналы, которые показывает --logs (имя -> файл в кэш-каталоге).
LOG_FILES = {"console": CONSOLE_LOG_NAME, "server": "server.log", "audit": "audit.log"}
_TASK_CMD_RE = re.compile(r'<Command>(?:&quot;|")?([^<"&]*run-mcp-baf\.cmd)')


def service_cache_dir() -> str:
    """Кэш-каталог службы из задания планировщика ('' — службы нет)."""
    if os.name != "nt":
        return ""
    out = _schtasks("/query", "/tn", TASK_NAME, "/xml")
    m = _TASK_CMD_RE.search(out.stdout) if out.returncode == 0 else None
    return os.path.dirname(m.group(1)) if m else ""


def find_cache_dir(cache_dir: str = "") -> str:
    """Явный --cache-dir/env > каталог установленной службы > умолчание.

    Чтобы --stop/--status/--logs работали без --cache-dir после --install-service.
    """
    if cache_dir or os.environ.get("mcp_baf_CACHE_DIR"):
        return resolve_cache_dir(cache_dir)
    return service_cache_dir() or resolve_cache_dir()


def _pid_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, PID_NAME)


def _read_pid(cache_dir: str) -> int | None:
    try:
        with open(_pid_path(cache_dir), encoding="ascii") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def write_pid(cache_dir: str) -> None:
    """Атомарно пишет PID текущего процесса."""
    os.makedirs(cache_dir, exist_ok=True)
    tmp = _pid_path(cache_dir) + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(str(os.getpid()))
    os.replace(tmp, _pid_path(cache_dir))


def remove_pid(cache_dir: str) -> None:
    """Удаляет PID-файл, только если в нём наш PID."""
    if _read_pid(cache_dir) == os.getpid():
        try:
            os.remove(_pid_path(cache_dir))
        except OSError:
            pass


def _is_ours(pid: int) -> bool:
    """Процесс жив и похож на наш (на Windows — по имени образа)."""
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, errors="replace").stdout.lower()
        return "python" in out or "mcp-baf" in out
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def stop(cache_dir: str = "") -> int:
    """mcp-baf --stop: возвращает код выхода."""
    cache_dir = find_cache_dir(cache_dir)
    pid = _read_pid(cache_dir)
    if pid is None:
        print(f"PID-файл не знайдено ({_pid_path(cache_dir)}): сервер не запущено "
              "(або запущено з іншим --cache-dir).")
        return 1
    if not _is_ours(pid):
        print(f"Процес {pid} не існує або це не mcp-baf: застарілий PID-файл видалено.")
        os.remove(_pid_path(cache_dir))
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print(f"Не вдалося зупинити процес {pid}: {exc}", file=sys.stderr)
        return 1
    try:
        os.remove(_pid_path(cache_dir))
    except OSError:
        pass
    print(f"Сервер (PID {pid}) зупинено.")
    return 0


def status(cache_dir: str = "") -> int:
    """mcp-baf --status: служба, процесс, где лежат журналы. 0 — сервер работает."""
    cache_dir = find_cache_dir(cache_dir)
    if os.name == "nt":
        q = _schtasks("/query", "/tn", TASK_NAME, "/fo", "LIST")
        state = re.search(r"^Status:\s*(.+)$", q.stdout, re.M)
        if q.returncode:
            print(f"Служба: не встановлена (mcp-baf --install-service)")
        else:
            print(f"Служба: встановлена, стан: {state.group(1).strip() if state else '?'}")
    pid = _read_pid(cache_dir)
    alive = pid is not None and _is_ours(pid)
    print(f"Сервер: {f'працює, PID {pid}' if alive else 'не запущено'}")
    print(f"Каталог: {cache_dir}")
    for name, file in LOG_FILES.items():
        path = os.path.join(cache_dir, file)
        if os.path.exists(path):
            print(f"Журнал {name}: {path}  (mcp-baf --logs {name})")
    return 0 if alive else 1


def logs(name: str = "console", cache_dir: str = "", lines: int = 50,
         follow: bool | None = None) -> int:
    """mcp-baf --logs [console|server|audit]: хвост журнала; в консоли — следит (Ctrl+C)."""
    import time

    path = os.path.join(find_cache_dir(cache_dir), LOG_FILES[name])
    if not os.path.exists(path):
        print(f"Журналу ще немає: {path}", file=sys.stderr)
        return 1
    if follow is None:
        follow = sys.stdout.isatty()
    sys.stdout.reconfigure(errors="backslashreplace")
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f.readlines()[-lines:]:
            print(line, end="")
        if not follow:
            return 0
        print(f"--- {path}: стежу за новими рядками, Ctrl+C — вихід ---", flush=True)
        try:
            while True:
                line = f.readline()
                if line:
                    print(line, end="", flush=True)
                    continue
                if os.path.getsize(path) < f.tell():
                    f.seek(0)  # ротация журнала — читаем новый файл сначала
                time.sleep(0.5)
        except KeyboardInterrupt:
            return 0


# ── Фон по клавише d (консоль Windows) ──

BACKGROUND_KEYS = frozenset("dDвВ")  # та же клавиша в украинской раскладке


def is_background_key(ch: str) -> bool:
    return ch in BACKGROUND_KEYS


def start_key_listener(on_background) -> None:
    """Поток опроса консоли Windows; no-op вне интерактивной консоли."""
    if os.name != "nt" or not sys.stdin.isatty():
        return
    import threading
    import time

    def poll() -> None:
        import msvcrt

        while True:
            if msvcrt.kbhit() and is_background_key(msvcrt.getwch()):
                on_background()
                return
            time.sleep(0.2)

    print("Натисніть d — перевести сервер у фон (Ctrl+C — зупинити)")
    threading.Thread(target=poll, daemon=True).start()


def spawn_detached(cache_dir: str) -> subprocess.Popen:
    """Запускает отсоединённую копию сервера с теми же аргументами."""
    log_path = os.path.join(cache_dir, CONSOLE_LOG_NAME)
    # Не DETACHED_PROCESS: python.exe из venv — лаунчер, его дочерний интерпретатор
    # без консоли получил бы новое окно. CREATE_NO_WINDOW даёт скрытую консоль,
    # которую наследуют оба процесса; закрытие исходного окна их не задевает.
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP
             | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
    with open(log_path, "ab") as log:
        return subprocess.Popen(
            [sys.executable, "-m", "mcp_baf", *sys.argv[1:]],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=flags, close_fds=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def wait_child_pid(cache_dir: str, fallback: int, timeout: float = 10.0) -> int:
    """PID настоящего интерпретатора из PID-файла фоновой копии.

    Popen.pid на Windows — лаунчер venv, а --stop работает по PID-файлу;
    ждём, пока копия его запишет, чтобы показать тот же PID.
    """
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pid = _read_pid(cache_dir)
        if pid and pid != os.getpid():
            return pid
        time.sleep(0.2)
    return fallback


# ── Служба Windows (Планировщик заданий) ──


def _cmd_quote(arg: str) -> str:
    q = subprocess.list2cmdline([arg])
    if not q.startswith('"') and re.search(r"[&|<>^()]", q):
        q = f'"{q}"'
    return q.replace("%", "%%")


def _server_args(argv: list[str], cache_dir: str) -> list[str]:
    """argv без --install-service и прежнего --cache-dir, плюс явный cache-dir."""
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
        elif a == "--install-service" or a.startswith("--cache-dir="):
            continue
        elif a == "--cache-dir":
            skip = True
        else:
            out.append(a)
    return [*out, "--cache-dir", cache_dir]


def build_service_cmd(argv: list[str], cache_dir: str, env: dict[str, str],
                      python: str | None = None) -> str:
    log = os.path.join(cache_dir, CONSOLE_LOG_NAME)
    # cmd.exe читает .cmd в OEM-кодировке: без chcp 65001 кириллица (mcp_baf_USER)
    # искажается; PYTHONIOENCODING — чтобы вывод в лог не падал на кириллице.
    lines = ["@echo off", "chcp 65001 >nul", "set PYTHONIOENCODING=utf-8"]
    for k, v in env.items():
        if k.lower().startswith("mcp_baf_"):
            lines.append(f'set "{k}={v.replace("%", "%%")}"')
    cmd = " ".join(_cmd_quote(a) for a in
                   [python or sys.executable, "-m", "mcp_baf", *_server_args(argv, cache_dir)])
    lines.append(f'{cmd} >> {_cmd_quote(log)} 2>&1')
    return "\r\n".join(lines) + "\r\n"


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          errors="replace")


def _require_admin() -> str | None:
    from mcp_baf import installer

    if not (installer._is_windows() and installer._is_admin()):
        return "Потрібен Windows і запуск від імені адміністратора."
    return None


def app_dir() -> str:
    return os.path.join(os.environ.get("ProgramFiles") or r"C:\Program Files", "mcp-baf")


def default_service_data_dir() -> str:
    return os.path.join(os.environ.get("ProgramData") or r"C:\ProgramData", "mcp-baf")


def pip_spec(direct_url: str | None, version: str) -> str:
    """Что ставить в venv службы: тот же источник, откуда запущен текущий процесс (PEP 610)."""
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    try:
        info = json.loads(direct_url) if direct_url else {}
    except ValueError:
        info = {}
    url = info.get("url", "")
    if url.startswith("file:"):
        return url2pathname(urlparse(url).path)
    vcs = info.get("vcs_info")
    if vcs and url:
        rev = vcs.get("commit_id") or vcs.get("requested_revision")
        return f"{vcs.get('vcs', 'git')}+{url}" + (f"@{rev}" if rev else "")
    return url or f"mcp-baf=={version}"


def _current_pip_spec() -> str:
    from importlib import metadata

    dist = metadata.distribution("mcp-baf")
    return pip_spec(dist.read_text("direct_url.json"), dist.version)


def _stop_quiet(cache_dir: str) -> None:
    if cache_dir:
        with contextlib.redirect_stdout(io.StringIO()):
            stop(cache_dir)


def _rmtree(path: str) -> bool:
    import time

    for attempt in (0, 1):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt == 0:
                time.sleep(1)
    return False


def install_service(argv: list[str], cache_dir: str) -> int:
    import time

    err = _require_admin()
    if not err:
        raw = [k for k, v in os.environ.items() if k.lower() in SECRET_ENV and v]
        raw += [a for a in argv if a.split("=", 1)[0] in SECRET_FLAGS]
        if raw:
            err = ("Секрети не можна записати у службу відкритим текстом: "
                   f"{', '.join(raw)}. Використайте mcp_baf_PASSWORD_FILE / "
                   "mcp_baf_HTTP_TOKEN_FILE (файли мають бути доступні SYSTEM).")
    if err:
        print(err, file=sys.stderr)
        return 1
    app = app_dir()
    venv = os.path.join(app, "venv")
    venv_python = os.path.join(venv, "Scripts", "python.exe")
    spec = _current_pip_spec()
    # Старую службу (и в другом каталоге данных) останавливаем, чтобы pip мог заменить файлы.
    old_dir = service_cache_dir()
    if _schtasks("/query", "/tn", TASK_NAME).returncode == 0:
        _schtasks("/end", "/tn", TASK_NAME)
    for d in {old_dir, cache_dir}:
        _stop_quiet(d)
    time.sleep(2)
    os.makedirs(cache_dir, exist_ok=True)
    acl = subprocess.run(["icacls", cache_dir, "/inheritance:r", "/grant:r",
                          "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"],
                         capture_output=True, text=True, errors="replace")
    if acl.returncode:
        print(f"Увага: не вдалося обмежити доступ до {cache_dir}: {acl.stdout}{acl.stderr}",
              file=sys.stderr)
    # shortcut: служба залежить від базового Python, з якого створено venv; якщо його
    # видалити чи оновити мажорно — повторіть --install-service.
    base_python = getattr(sys, "_base_executable", sys.executable)
    steps = []
    if not os.path.exists(venv_python):
        os.makedirs(app, exist_ok=True)
        steps.append([base_python, "-m", "venv", venv])
    steps.append([venv_python, "-m", "pip", "install", "--upgrade", spec])
    print(f"Встановлюю mcp-baf ({spec}) у {venv} — це може тривати хвилину...", flush=True)
    for step in steps:
        if subprocess.run(step).returncode:
            print(f"Помилка: {' '.join(step)}\nСлужбу не створено.", file=sys.stderr)
            return 1
    cmd_path = os.path.join(cache_dir, "run-mcp-baf.cmd")
    with open(cmd_path, "w", encoding="utf-8", newline="") as f:
        f.write(build_service_cmd(argv, cache_dir, dict(os.environ), venv_python))
    created = _schtasks("/create", "/tn", TASK_NAME, "/sc", "onstart", "/ru", "SYSTEM",
                        "/rl", "HIGHEST", "/f", "/tr", f'"{cmd_path}"')
    if created.returncode:
        print(f"schtasks /create: {created.stdout}{created.stderr}", file=sys.stderr)
        return 1
    started = _schtasks("/run", "/tn", TASK_NAME)
    if started.returncode:
        print(f"schtasks /run: {started.stdout}{started.stderr}", file=sys.stderr)
        return 1
    print(f"Службу створено й запущено.\n"
          f"Програма: {app}\n"
          f"Дані: {cache_dir}  (запуск: {cmd_path})\n"
          f"Журнал: {os.path.join(cache_dir, CONSOLE_LOG_NAME)}\n"
          f"Перевірити: mcp-baf --status  (або schtasks /query /tn {TASK_NAME})\n"
          f"Зупинити: mcp-baf --stop  (або schtasks /end /tn {TASK_NAME})\n"
          "Видалити: mcp-baf --uninstall-service\n"
          "Файли токена/пароля мають бути доступні обліковому запису SYSTEM.")
    return 0


def uninstall_service() -> int:
    err = _require_admin()
    if err:
        print(err, file=sys.stderr)
        return 1
    data = service_cache_dir()
    _schtasks("/end", "/tn", TASK_NAME)
    deleted = _schtasks("/delete", "/tn", TASK_NAME, "/f")
    if deleted.returncode:
        print(f"Завдання {TASK_NAME} не знайдено або не видалено: "
              f"{(deleted.stdout + deleted.stderr).strip()}")
    else:
        print(f"Завдання {TASK_NAME} видалено.")
    _stop_quiet(data)
    app = app_dir()
    if os.path.isdir(app):
        if _rmtree(app):
            print(f"Програму видалено: {app}")
        else:
            print(f"Увага: не вдалося видалити {app} — видаліть вручну.", file=sys.stderr)
    if data:
        print(f"Дані збережено: {data} (журнали, TLS CA, pii.key).")
    return 0
