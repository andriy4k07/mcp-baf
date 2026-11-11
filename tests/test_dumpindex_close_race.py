"""Гонка close() проти потока-строителя DumpIndex (issue #56).

CI флат: сегфолт (exit 139) у tests/test_protocol.py — faulthandler показал,
что текущий поток был в `self._db.execute(...)` внутри `_finish_build`, пока
main уже вернулся из `index.close()` в lifespan сервера. Причина: close()
закрывала SQLite-соединение, не дожидаясь потока-строителя, а sqlite3_step
отпускает GIL — sqlite3_close посреди шага освобождает нативные структуры под
активным statement (use-after-free).

Регрессия проверяет контракт фикса: close() возвращает управление только
когда поток-строитель завершён, а соединение закрывается исключительно между
statement'ами (никаких «Cannot operate on a closed database» и крашей).
"""

import logging
import threading
import time

from mcp_baf.dumpindex import DumpIndex
from mcp_baf.dumpindex import index as idxmod

CONTENT = "Процедура Тест()\nСообщить('привіт світ');\nКонецПроцедуры\n" * 12


class _SyntheticBuild(DumpIndex):
    """Индекс без реального dump: файлы и содержимое — синтетика в памяти.

    `gate` — Event, который поток-строитель выставляет внутри последнего
    statement (count(*) в _finish_build) через progress handler SQLite:
    тест закрывает индекс именно посреди активного sqlite3_step.

    Инвариант размера: синтетический скан обязан укладываться в
    миллисекунды и на загруженном раннере — он выполняется под _db_lock
    на пути join'а close(), и если когда-нибудь перерастёт
    CLOSE_JOIN_TIMEOUT (10 с), сама регрессия попадёт в отложенный путь
    close(). Поэтому держим строки тысячами, не десятками тысяч: это запас
    безопасности, а не тюнинг — gate срабатывает на первой же виртуальной
    операции, длина скана для воспроизведения гонки не нужна.
    """

    def __init__(self, *args, gate: threading.Event | None = None,
                 n_rows: int = 2000, **kwargs):
        self._gate = gate
        self._n_rows = n_rows
        super().__init__(*args, **kwargs)

    def _walk_files(self):
        return {
            f"mod{i:06d}.bsl": idxmod._FileState(
                abs_path=f"/nonexistent/mod{i:06d}.bsl", mtime_ms=1, size=len(CONTENT)
            )
            for i in range(self._n_rows)
        }

    @staticmethod
    def _read_content(abs_path):
        return CONTENT

    def _finish_build(self, from_cache):
        if self._gate is not None and self._db is not None:
            # Полноскановый запрос выполняется в VDBE построчно и гарантированно
            # дёргает progress handler (изнутри sqlite3_step, с GIL): сигнал
            # здесь означает «statement точно выполняется сейчас». count(*)
            # для этого не годится — SQLite оптимизирует его без вызовов.
            self._db.set_progress_handler(self._gate.set, 1)
            self._db.execute(
                "SELECT count(*) FROM docs WHERE length(content) > 0"
            ).fetchone()
        super()._finish_build(from_cache)


def test_close_during_active_build_joins_builder_thread(tmp_path):
    """close() посреди долгой сборки ждёт поток, а не рвёт соединение под ним."""
    reading = threading.Event()

    class SlowRead(_SyntheticBuild):
        @staticmethod
        def _read_content(abs_path):
            reading.set()
            time.sleep(0.4)  # держим поток-строитель в сборке
            return CONTENT

    idx = SlowRead(str(tmp_path), use_cache=False, n_rows=5)
    assert reading.wait(timeout=30), "поток-строитель не начал чтение"

    started = time.monotonic()
    idx.close()  # обязано дождаться потока, а не закрыть соединение под ним

    assert not idx._thread.is_alive(), "close() вернул управление при живом потоке"
    assert time.monotonic() - started > 0.1, "close() даже не пытался дождаться сборки"
    error = idx.build_error()
    assert error is None, f"сборка после close() упала: {error!r}"


def test_close_under_active_count_statement(tmp_path):
    """Воспроизведение краша в CI (issue #56): close() во время count(*) в _finish_build.

    До фикса close() проходила мгновенно (join не было) и соединение
    закрывалось под активным sqlite3_step потока-строителя: в CI — SIGSEGV,
    локально — «Cannot operate on a closed database» в build_error.
    """
    gate = threading.Event()
    idx = _SyntheticBuild(str(tmp_path), use_cache=False, gate=gate)
    assert gate.wait(timeout=30), "statement не зафиксирован в активном шаге"

    idx.close()

    assert not idx._thread.is_alive(), "close() вернул управление при живом потоке"
    error = idx.build_error()
    assert error is None or "closed database" not in str(error), (
        f"соединение закрыто посреди statement: {error!r}"
    )
    assert idx._db is None


def test_repeated_create_close_cycles_stay_clean(tmp_path):
    """Циклы «создать индекс → сразу закрыть» — как 4×create_server в protocol-тестах."""
    for attempt in range(3):
        gate = threading.Event()
        idx = _SyntheticBuild(
            str(tmp_path / str(attempt)), use_cache=False, gate=gate, n_rows=1000
        )
        gate.wait(timeout=30)  # можем и не успеть в окно — это нормально
        idx.close()
        assert not idx._thread.is_alive(), f"цикл {attempt}: поток остался жив"
        error = idx.build_error()
        assert error is None or "closed database" not in str(error), (attempt, error)


def test_close_bounds_lock_wait_and_defers_to_builder(tmp_path, monkeypatch, caplog):
    """close() не висит на _db_lock дольше таймаута и не теряет соединение.

    Поток-строитель держит _db_lock весь тёплый старт (_open_cache_and_diff:
    обход дерева + перечитывание файлов + diff-запросы). Если join истёк, а
    замок занят, close() обязана: вернуться за ~2×CLOSE_JOIN_TIMEOUT,
    предупредить и ОТЛОЖИТЬ закрытие соединения на строительный поток —
    иначе lifespan сервера (await asyncio.to_thread(index.close)) висел бы
    на бесконечном acquire замка всю сборку, либо соединение утекало бы.

    Синхронизация детерминированная (Event'ы), без sleep-гонок: строитель
    блокируется ровно внутри держания замка, пока тест его не отпустит.
    """
    monkeypatch.setattr(idxmod, "CLOSE_JOIN_TIMEOUT", 0.5)
    dump_dir = str(tmp_path / "dump")
    cache_dir = str(tmp_path / "cache")

    # Тёплый кэш: следующее открытие пойдёт в _open_cache_and_diff.
    warm = _SyntheticBuild(dump_dir, cache_dir=cache_dir, n_rows=200)
    assert warm.wait_ready(timeout=30), f"тёплый пролог не собрался: {warm.build_error()!r}"
    warm.close()

    class HoldingBuilder(_SyntheticBuild):
        """Строитель, который держит _db_lock после открытия соединения.

        _open_cache_and_diff_locked вызывается уже под _db_lock — блокировка
        внутри неё означает «замок занят, self._db открыт».
        """

        def __init__(self, *args, **kwargs):
            self.lock_held = threading.Event()
            self.release_lock = threading.Event()
            super().__init__(*args, **kwargs)

        def _open_cache_and_diff_locked(self):
            super()._open_cache_and_diff_locked()  # соединение self._db уже открыто
            self.lock_held.set()
            assert self.release_lock.wait(timeout=30), "тест не отпустил замок"

    idx = HoldingBuilder(dump_dir, cache_dir=cache_dir)
    assert idx.lock_held.wait(timeout=30), "строитель не занял _db_lock"

    started = time.monotonic()
    with caplog.at_level(logging.WARNING, logger=idxmod.logger.name):
        idx.close()
    elapsed = time.monotonic() - started
    # join(0.5) + acquire(0.5): close() обязана вернуться, не дожидаясь строителя.
    assert elapsed < 4 * idxmod.CLOSE_JOIN_TIMEOUT, (
        f"close() зависла на замке: {elapsed:.1f}s"
    )
    assert idx._db is not None, (
        "соединение закрыто под активным замком строителя — отложения не случилось"
    )
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("deferring" in m for m in warnings), f"нет предупреждения об отложении: {warnings}"

    # Отпускаем строитель: он обязан увидеть _closed под _db_lock и закрыть
    # соединение сам (отложенное закрытие), без краша и без утечки.
    idx.release_lock.set()
    idx._thread.join(timeout=30)
    assert not idx._thread.is_alive(), "строитель не завершился после отпуска замка"
    assert idx._db is None, "строитель не освободил соединение после _closed"
    idx.close()  # повторный close() — идемпотентность, без краша
