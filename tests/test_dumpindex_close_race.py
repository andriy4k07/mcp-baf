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
    """

    def __init__(self, *args, gate: threading.Event | None = None,
                 n_rows: int = 20000, **kwargs):
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
    """Round CI-крашу: close() во время count(*) в _finish_build.

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
            str(tmp_path / str(attempt)), use_cache=False, gate=gate, n_rows=5000
        )
        gate.wait(timeout=30)  # можем и не успеть в окно — это нормально
        idx.close()
        assert not idx._thread.is_alive(), f"цикл {attempt}: поток остался жив"
        error = idx.build_error()
        assert error is None or "closed database" not in str(error), (attempt, error)
