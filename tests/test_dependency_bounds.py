"""Гарды на контракт зависимостей (issue #37, #49).

`mcp-baf-audit` пишет `audit.log` по схеме v2; формат — часть контракта между
mcp-baf и пакетом аудита. Без верхней границы в pyproject minor bump 0.3 мог бы
тихо сменить формат, а тест на SCHEMA_VERSION поймал бы это только в момент
установки. Оба гарда держат контракт явным.

Плюс границы прямых зависимостей (#49): pydantic/uvicorn/anyio импортируются
напрямую, но раньше приходили только транзитивно; httpx/cryptography были без
верхних границ; certifi ниже 2026.10.23 содержит скомпрометированные
промежуточные CA (GHSA-6q48-6c7w-9gw2).
"""

import pathlib
import re
import tomllib

import mcp_baf_audit

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTED_SPEC = "mcp-baf-audit~=0.2.1"
EXPECTED_SCHEMA_VERSION = "2"

# Прямые зависимости: объявлены явно, верхние границы совпадают с baf-write-mcp.
EXPECTED_SPECS = {
    "mcp-baf-audit": EXPECTED_SPEC,
    "httpx": "httpx>=0.27,<1",
    "cryptography": "cryptography>=42,<51",
    "pydantic": "pydantic>=2.12,<3",
    "uvicorn": "uvicorn>=0.31,<1",
    "anyio": "anyio>=4.9,<5",
    "regex": "regex>=2024.11.6,<2027",
    # Нижняя граница — фикс CA-компрометации; верхнюю не ставим: свежие
    # корневые сертификаты нужны как можно раньше.
    "certifi": "certifi>=2026.10.23",
}


def _dependency_specs() -> dict[str, list[str]]:
    """Имя пакета (нормализованное) -> список объявленных spec-строк."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    by_name: dict[str, list[str]] = {}
    for dep in data["project"]["dependencies"]:
        name = re.split(r"[<>=!~\[;\s]", dep, maxsplit=1)[0].strip().lower()
        by_name.setdefault(name, []).append(dep)
    return by_name


def _spec(name: str) -> str:
    specs = _dependency_specs().get(name, [])
    assert len(specs) == 1, f"ожидался один spec {name}, получено: {specs}"
    return specs[0]


def test_audit_dependency_has_upper_bound():
    assert _spec("mcp-baf-audit") == EXPECTED_SPEC


def test_audit_schema_version_is_v2():
    assert mcp_baf_audit.SCHEMA_VERSION == EXPECTED_SCHEMA_VERSION, (
        "SCHEMA_VERSION пакета mcp-baf-audit изменился — формат audit.log "
        "больше не совпадает с контрактом mcp-baf"
    )


def test_direct_dependencies_are_declared_with_bounds():
    """Все прямые импорты объявлены явно и с ожидаемыми границами."""
    declared = _dependency_specs()
    for name, expected in EXPECTED_SPECS.items():
        assert name in declared, f"{name} импортируется напрямую, но не объявлен"
        assert declared[name] == [expected], (
            f"границы {name} разошлись: {declared[name]} != [{expected}]"
        )


def test_transport_and_crypto_have_upper_bounds():
    """httpx/cryptography не должны «уехать» на мажор без ревью."""
    for name in ("httpx", "cryptography"):
        assert "<" in _spec(name), f"у {name} нет верхней границы"


def test_certifi_not_below_ca_fix():
    """certifi ниже 2026.10.23 несёт скомпрометированные промежуточные CA."""
    assert _spec("certifi") == "certifi>=2026.10.23"
