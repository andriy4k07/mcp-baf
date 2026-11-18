"""Чтение технологического журнала 1С (ТЖ) с локального диска.

Каталог: <techlog_dir>/<процесс>_<pid>/yyMMddHH.log, UTF-8 (часто с BOM).
Событие начинается строкой «mm:ss.микросекунды-длительность,ИМЯ,уровень,» и
продолжается парами prop=value через запятую; значения могут быть в кавычках
(' или ", удвоенная кавычка — экранирование) и занимать несколько строк.
Интересны только TLOCK, TTIMEOUT, TDEADLOCK, EXCP. Содержимое событий в аудит
не попадает: наружу уходит только готовый markdown.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

TECHLOG_EVENTS = ("TLOCK", "TTIMEOUT", "TDEADLOCK", "EXCP")

# Бюджеты безопасности: ТЖ бывает десятки гигабайт.
MAX_FILES = 200
MAX_BYTES = 128 << 20          # суммарно прочитанных байт
MAX_EVENTS = 200_000           # разобранных интересных событий
MAX_EVENT_CHARS = 32_768       # хвост очень длинного события отбрасывается
MAX_VALUE_CHARS = 300          # значение в выводе

_FILE_RE = re.compile(r"^(\d\d)(\d\d)(\d\d)(\d\d)\.log$")
_START_RE = re.compile(r"^(\d\d):(\d\d)\.(\d{6})-(\d+),(\w+),")


@dataclass
class TechlogResult:
    start: datetime
    end: datetime
    files: int = 0
    bytes_read: int = 0
    events_parsed: int = 0
    truncated: list[str] = field(default_factory=list)
    skipped_files: int = 0
    # Область блокировки -> [счётчик, суммарное ожидание µs, максимум µs].
    regions: dict[str, list[int]] = field(default_factory=dict)
    tlock: int = 0
    timeouts: list[dict[str, Any]] = field(default_factory=list)
    deadlocks: list[dict[str, Any]] = field(default_factory=list)
    excp: Counter = field(default_factory=Counter)
    excp_total: int = 0


def parse_window(start: str, end: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Окно ISO 8601 (локальное время сервера); по умолчанию — последний час."""
    now = now or datetime.now()
    try:
        e = datetime.fromisoformat(end) if end else now
        s = datetime.fromisoformat(start) if start else e - timedelta(hours=1)
    except ValueError as exc:
        raise ValueError(f"некорректная дата (ожидается ISO 8601): {exc}") from None
    if s.tzinfo or e.tzinfo:
        raise ValueError("укажите локальное время сервера без часового пояса")
    if s > e:
        raise ValueError("start_date позже end_date")
    return s, e


def parse_props(text: str) -> dict[str, str]:
    """Разбирает «prop=value,prop='quoted ''value''',...» (в т.ч. многострочные)."""
    props: dict[str, str] = {}
    i, n = 0, len(text)
    while i < n:
        eq = text.find("=", i)
        if eq < 0:
            break
        key = text[i:eq].strip()
        i = eq + 1
        if i < n and text[i] in "'\"":
            q = text[i]
            i += 1
            buf = []
            while i < n:
                j = text.find(q, i)
                if j < 0:  # незакрытая кавычка: берём остаток
                    buf.append(text[i:])
                    i = n
                    break
                buf.append(text[i:j])
                if text[j + 1:j + 2] == q:  # удвоенная кавычка
                    buf.append(q)
                    i = j + 2
                else:
                    i = j + 1
                    break
            value = "".join(buf)
            comma = text.find(",", i)
            i = n if comma < 0 else comma + 1
        else:
            comma = text.find(",", i)
            value = text[i:] if comma < 0 else text[i:comma]
            i = n if comma < 0 else comma + 1
        if key.isidentifier():
            props.setdefault(key, value.strip())
    return props


def _candidate_files(root: str, start: datetime, end: datetime) -> list[tuple[datetime, str]]:
    """Файлы yyMMddHH.log, пересекающие окно (по имени); симлинки пропускаются."""
    found: list[tuple[datetime, str]] = []
    try:
        procs = [e for e in os.scandir(root) if e.is_dir(follow_symlinks=False)]
    except OSError:
        return found
    for proc in procs:
        try:
            entries = list(os.scandir(proc.path))
        except OSError:
            continue
        for f in entries:
            m = _FILE_RE.match(f.name)
            if not m or not f.is_file(follow_symlinks=False):
                continue
            yy, mo, dd, hh = (int(g) for g in m.groups())
            try:
                hour = datetime(2000 + yy, mo, dd, hh)
            except ValueError:
                continue
            if hour + timedelta(hours=1) > start and hour <= end:
                found.append((hour, f.path))
    found.sort()
    return found


def _iter_events(path: str, hour: datetime, budget: list[int]):
    """Отдаёт [время, длительность µs, имя, текст после уровня] интересных событий."""
    cur = None
    with open(path, "rb") as fh:
        for raw in fh:
            if budget[0] <= 0:
                break
            budget[0] -= len(raw)
            line = raw.decode("utf-8-sig", errors="replace").rstrip("\r\n")
            m = _START_RE.match(line)
            if m:
                if cur:
                    yield cur
                cur = None
                mm, ss, us, dur, name = m.groups()
                if name in TECHLOG_EVENTS:
                    ts = hour + timedelta(minutes=int(mm), seconds=int(ss), microseconds=int(us))
                    # Пропускаем «уровень,» — дальше пары prop=value.
                    rest = line[m.end():].split(",", 1)
                    cur = [ts, int(dur), name, rest[1] if len(rest) > 1 else ""]
            elif cur and len(cur[3]) < MAX_EVENT_CHARS:
                cur[3] += "\n" + line
        if cur:
            yield cur


def scan(root: str, start: datetime, end: datetime, event: str = "") -> TechlogResult:
    res = TechlogResult(start, end)
    files = _candidate_files(os.path.realpath(root), start, end)
    if len(files) > MAX_FILES:
        res.truncated.append(f"файлов в окне {len(files)}, прочитано {MAX_FILES}")
        files = files[:MAX_FILES]
    budget = [MAX_BYTES]
    for hour, path in files:
        if budget[0] <= 0:
            res.truncated.append(f"достигнут лимит чтения {MAX_BYTES >> 20} МиБ")
            break
        if res.events_parsed >= MAX_EVENTS:
            res.truncated.append(f"достигнут лимит {MAX_EVENTS} событий")
            break
        try:
            for ts, dur, name, body in _iter_events(path, hour, budget):
                if not start <= ts <= end or (event and name != event):
                    continue
                res.events_parsed += 1
                _account(res, ts, dur, name, parse_props(body))
                if res.events_parsed >= MAX_EVENTS:
                    break
            res.files += 1
        except OSError:
            res.skipped_files += 1  # битый/занятый файл не фатален
    res.bytes_read = MAX_BYTES - max(budget[0], 0)
    return res


def _account(res: TechlogResult, ts: datetime, dur: int, name: str, p: dict[str, str]) -> None:
    common = {
        "ts": ts, "usr": p.get("Usr", ""), "conn": p.get("connectID", ""),
        "ctx": p.get("Context", ""),
    }
    if name == "TLOCK":
        res.tlock += 1
        for region in filter(None, (r.strip() for r in p.get("Regions", "").split(","))):
            r = res.regions.setdefault(region, [0, 0, 0])
            r[0] += 1
            r[1] += dur
            r[2] = max(r[2], dur)
    elif name == "TTIMEOUT":
        res.timeouts.append({**common, "wait": p.get("WaitConnections", ""),
                             "regions": p.get("Regions", ""), "dur": dur})
    elif name == "TDEADLOCK":
        res.deadlocks.append({**common, "inter": p.get("DeadlockConnectionIntersections", "")})
    else:
        res.excp_total += 1
        res.excp[p.get("Descr", "")] += 1


def format_techlog(res: TechlogResult, limit: int, mask: Callable[[Any], str] | None = None) -> str:
    """Markdown-зведення. mask — функция маскирования ПДн для Usr/Descr/Context."""
    mk = mask or (lambda v: str(v or ""))

    def short(v: Any) -> str:
        t = " ".join(mk(v).split())
        return t if len(t) <= MAX_VALUE_CHARS else t[:MAX_VALUE_CHARS] + "…"

    def secs(us: int) -> str:
        return f"{us / 1_000_000:.3f} с"

    out = ["## Технологический журнал", "",
           f"Окно: {res.start.isoformat()} — {res.end.isoformat()}. Файлов: {res.files}, "
           f"событий: {res.events_parsed}. Длительности в журнале 8.3.x — микросекунды "
           "(у 8.2 единица иная: 1e-4 с)."]
    if res.skipped_files:
        out.append(f"Пропущено нечитаемых файлов: {res.skipped_files}.")
    for t in res.truncated:
        out.append(f"Неполно: {t}. Сузьте окно.")

    out += ["", f"### Блокировки (TLOCK): {res.tlock}"]
    top = sorted(res.regions.items(), key=lambda kv: -kv[1][1])[:min(limit, 20)]
    if top:
        out.append("Области по суммарному ожиданию:")
        out += [f"- {short(k)}: {v[0]} шт., ожидание {secs(v[1])}, макс. {secs(v[2])}"
                for k, v in top]
    else:
        out.append("Нет данных.")

    def listing(title: str, rows: list[dict[str, Any]], detail: Callable[[dict[str, Any]], str]):
        out.extend(["", f"### {title}: {len(rows)}"])
        for r in sorted(rows, key=lambda r: r["ts"])[:limit]:
            out.append(f"- {r['ts'].isoformat(timespec='seconds')} Usr={short(r['usr'])} "
                       f"connectID={r['conn']} {detail(r)}")
        if len(rows) > limit:
            out.append(f"- … показано {limit} из {len(rows)}")

    listing("Дедлоки (TDEADLOCK)", res.deadlocks,
            lambda r: f"пересечения={short(r['inter'])} контекст={short(r['ctx'])}")
    listing("Таймауты блокировок (TTIMEOUT)", res.timeouts,
            lambda r: f"ожидает={short(r['wait'])} области={short(r['regions'])} "
                      f"контекст={short(r['ctx'])}")

    out += ["", f"### Исключения (EXCP): {res.excp_total}"]
    out += [f"- {n} x {short(d)}" for d, n in res.excp.most_common(min(limit, 10))]
    return "\n".join(out) + "\n"
