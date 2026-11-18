"""Оценка качества search_code: gold-набор -> Recall@1/5/k и MRR по режимам поиска.

Запуск (из корня репозитория):

    .venv/bin/python scripts/eval_search.py --dump /путь/к/выгрузке \\
        --gold scripts/search_gold.json --modes smart[,hybrid] -k 10 \\
        [--embed-url URL --rerank-url URL] [--cache-dir DIR] [--match line|module]

Попадание (hit) — совпадение, у которого имя модуля совпадает с модулем из gold
(путь -> имя через bsl_path_to_module_name) и (при --match line, по умолчанию)
номер строки попадает внутрь тела нужной процедуры/функции. Границы метода
вычисляются парсингом .bsl файла по заголовкам Процедура/Функция и
КонецПроцедуры/КонецФункции. --match module учитывает только совпадение модуля.

Режим hybrid требует, чтобы DumpIndex принимал embed_url/rerank_url и умел
wait_vectors(); до их появления скрипт завершится с понятной ошибкой.
Только стандартная библиотека и сам пакет mcp_baf.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass

from mcp_baf.dumpindex import DumpIndex
from mcp_baf.dumpindex.index import SearchParams
from mcp_baf.dumpindex.modulenames import bsl_path_to_module_name

# Заголовок метода и его конец. Русские и английские ключевые слова — на случай EDT/англ. выгрузок.
_HEADER_RE = re.compile(r"^\s*(?:Процедура|Функция|Procedure|Function)\s+([^\s(]+)\s*\(", re.IGNORECASE)
_END_RE = re.compile(r"^\s*(?:КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)", re.IGNORECASE)

KINDS = ("semantic", "keyword")


@dataclass
class GoldItem:
    query: str
    kind: str
    file: str            # путь относительно --dump
    method: str
    module: str          # человекочитаемое имя модуля
    start: int           # строка заголовка метода (с 1)
    end: int             # строка конца метода (с 1)


def method_ranges(path: str) -> dict[str, tuple[int, int]]:
    """Имя метода -> (строка заголовка, строка КонецПроцедуры/КонецФункции)."""
    ranges: dict[str, tuple[int, int]] = {}
    current: tuple[str, int] | None = None
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            if current is None:
                m = _HEADER_RE.match(line)
                if m:
                    current = (m.group(1), lineno)
            elif _END_RE.match(line):
                ranges[current[0]] = (current[1], lineno)
                current = None
    return ranges


def load_gold(gold_path: str, dump_dir: str) -> list[GoldItem]:
    """Читает gold-набор и проверяет, что каждый эталон существует в выгрузке."""
    with open(gold_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    items: list[GoldItem] = []
    problems: list[str] = []
    cache: dict[str, dict[str, tuple[int, int]]] = {}
    for idx, entry in enumerate(raw, 1):
        kind = entry.get("kind")
        if kind not in KINDS:
            problems.append(f"#{idx}: неизвестный kind={kind!r}")
            continue
        for exp in entry.get("expected", []):
            rel, method = exp["file"], exp["method"]
            abs_path = os.path.join(dump_dir, rel)
            if not os.path.isfile(abs_path):
                problems.append(f"#{idx}: нет файла {rel}")
                continue
            if abs_path not in cache:
                cache[abs_path] = method_ranges(abs_path)
            rng = cache[abs_path].get(method)
            if rng is None:
                problems.append(f"#{idx}: метод {method} не найден в {rel}")
                continue
            items.append(GoldItem(
                query=entry["query"], kind=kind, file=rel, method=method,
                module=bsl_path_to_module_name(rel), start=rng[0], end=rng[1],
            ))
    if problems:
        sys.exit("Ошибки в gold-наборе:\n  " + "\n  ".join(problems))
    return items


def is_hit(item: GoldItem, match, match_mode: str) -> bool:
    if match.module != item.module:
        return False
    if match_mode == "module":
        return True
    return item.start <= match.line <= item.end


def open_index(dump: str, cache_dir: str | None, hybrid: bool, embed_url: str | None,
               rerank_url: str | None, timeout: float) -> DumpIndex:
    """Создаёт DumpIndex; для hybrid передаёт embed/rerank URL и ждёт векторов."""
    kwargs: dict = {"show_progress": True}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    if hybrid:
        if not embed_url:
            sys.exit("Для режима hybrid нужен --embed-url (--rerank-url необязателен: без него чистый RRF)")
        kwargs.update(embed_url=embed_url, rerank_url=rerank_url)
    try:
        index = DumpIndex(dump, **kwargs)
    except TypeError as exc:
        sys.exit(f"DumpIndex не принимает нужные аргументы для hybrid: {exc}")
    if not index.wait_ready(timeout):
        index.close()
        sys.exit("Индекс не готов за отведённое время")
    if index.build_error() is not None:
        index.close()
        sys.exit(f"Ошибка сборки индекса: {index.build_error()}")
    if hybrid:
        wait_vectors = getattr(index, "wait_vectors", None)
        if wait_vectors is None:
            index.close()
            sys.exit("В DumpIndex нет метода wait_vectors(): векторный режим hybrid ещё не реализован")
        if wait_vectors(timeout) is False:
            err = getattr(index._vectors, "error", None)
            index.close()
            sys.exit(f"Векторы не построены: {err or 'таймаут'}")
    return index


def evaluate(index: DumpIndex, items: list[GoldItem], mode: str, k: int, match_mode: str) -> list[dict]:
    """Прогоняет все запросы; для каждого возвращает ранг первого попадания (None — нет)."""
    rows = []
    for item in items:
        matches, _total = index.search(SearchParams(query=item.query, mode=mode, limit=k))
        rank = None
        for pos, m in enumerate(matches[:k], 1):
            if is_hit(item, m, match_mode):
                rank = pos
                break
        rows.append({"item": item, "rank": rank, "top": matches[:3]})
    return rows


def metrics(rows: list[dict], k: int) -> dict[str, dict[str, float]]:
    """Recall@1/5/k и MRR по группам kind и общей группе overall."""
    ks = sorted({1, min(5, k), k})
    out: dict[str, dict[str, float]] = {}
    for group in (*KINDS, "overall"):
        sel = [r for r in rows if group == "overall" or r["item"].kind == group]
        n = len(sel)
        m: dict[str, float] = {"n": n}
        for cut in ks:
            m[f"R@{cut}"] = sum(1 for r in sel if r["rank"] is not None and r["rank"] <= cut) / n if n else 0.0
        m["MRR"] = sum(1.0 / r["rank"] for r in sel if r["rank"] is not None) / n if n else 0.0
        out[group] = m
    return out


def print_mode_table(mode: str, rows: list[dict], k: int, match_mode: str) -> dict[str, dict[str, float]]:
    met = metrics(rows, k)
    ks = sorted({1, min(5, k), k})
    head = ["группа", "n"] + [f"Recall@{c}" for c in ks] + ["MRR"]
    print(f"\n### Режим `{mode}` (match={match_mode}, k={k})\n")
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for group in (*KINDS, "overall"):
        m = met[group]
        cells = [group, str(int(m["n"]))] + [f"{m[f'R@{c}']:.3f}" for c in ks] + [f"{m['MRR']:.3f}"]
        print("| " + " | ".join(cells) + " |")
    misses = [r for r in rows if r["rank"] is None]
    print(f"\nПромахи ({len(misses)} из {len(rows)}):\n")
    if not misses:
        print("нет")
    for r in misses:
        it = r["item"]
        top = "; ".join(f"{m.module}:{m.line}" for m in r["top"]) or "пусто"
        print(f"- [{it.kind}] «{it.query}» -> ожидали {it.module}.{it.method} "
              f"(строки {it.start}-{it.end}); топ: {top}")
    return met


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Оценка search_code на gold-наборе (Recall@k, MRR).")
    p.add_argument("--dump", required=True, help="корень выгрузки конфигурации (.bsl файлы)")
    p.add_argument("--gold", default="scripts/search_gold.json", help="JSON gold-набор")
    p.add_argument("--modes", default="smart", help="режимы через запятую: smart,hybrid")
    p.add_argument("-k", type=int, default=10, help="глубина выдачи и максимальный cutoff")
    p.add_argument("--embed-url", default=None, help="URL эмбеддингов (только для hybrid)")
    p.add_argument("--rerank-url", default=None, help="URL реранкера (только для hybrid)")
    p.add_argument("--cache-dir", default=None, help="каталог дискового кэша индекса")
    p.add_argument("--match", choices=("line", "module"), default="line",
                   help="line: модуль и строка внутри метода; module: только модуль")
    p.add_argument("--timeout", type=float, default=3600.0, help="ожидание готовности индекса, сек")
    args = p.parse_args(argv)

    if args.k <= 0:
        p.error("-k должен быть больше 0")
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in ("smart", "hybrid"):
            p.error(f"неизвестный режим: {m}")

    items = load_gold(args.gold, args.dump)
    print(f"Gold: {len(items)} эталонов ({sum(i.kind == 'semantic' for i in items)} semantic, "
          f"{sum(i.kind == 'keyword' for i in items)} keyword)")

    for mode in modes:
        index = open_index(args.dump, args.cache_dir, mode == "hybrid",
                           args.embed_url, args.rerank_url, args.timeout)
        try:
            rows = evaluate(index, items, mode, args.k, args.match)
        finally:
            index.close()
        print_mode_table(mode, rows, args.k, args.match)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
