"""Чтение HBK: адаптация контейнерного парсера rzateev/onec-help-mcp @ f66860b.

SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev
Copyright (c) 2026 andriy4k07
Полный текст MIT: LICENSE-onec-help-mcp.txt рядом с этим модулем.
"""

from __future__ import annotations

import io
import re
import struct
import zipfile
from pathlib import Path

MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_STORAGE_BYTES = 512 * 1024 * 1024


def _number(data: bytes, offset: int) -> int:
    raw = data[offset:offset + 8]
    if len(raw) != 8:
        raise ValueError("Обрезанный заголовок HBK")
    if not re.fullmatch(rb"[0-9a-fA-F]{8}", raw):
        raise ValueError("Некорректное число в заголовке HBK")
    return int(raw, 16)


def _slice(data: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError("Адрес блока HBK выходит за пределы файла")
    return data[offset:offset + size]


def _body(data: bytes, offset: int) -> bytes:
    """Цепочка блоков контейнера; защита от циклов и неверных размеров."""
    total = _number(data, offset + 2)
    if total > MAX_STORAGE_BYTES:
        raise ValueError("Блок HBK превышает 512 MiB")
    chunks = []
    visited = set()
    remaining = total
    while remaining:
        if offset in visited:
            raise ValueError("Циклическая цепочка блоков HBK")
        visited.add(offset)
        block_size = _number(data, offset + 11)
        following = _number(data, offset + 20)
        if block_size <= 0:
            raise ValueError("Пустой блок HBK")
        amount = min(remaining, block_size)
        chunks.append(_slice(data, offset + 31, amount))
        remaining -= amount
        if remaining and following == 0x7fffffff:
            raise ValueError("Обрезанная цепочка HBK")
        offset = following
    return b"".join(chunks)


def decode_html(raw: bytes) -> str:
    # UTF-8 проверяем раньше cp1251: cp1251 часто принимает UTF-8 как мусор.
    charset = re.search(br'charset\s*=\s*["\']?([\w-]+)', raw[:4096], re.I)
    encodings = ([charset.group(1).decode("ascii")] if charset else []) + ["utf-8-sig", "cp1251"]
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    # Один неопределённый байт не должен стоить всей страницы.
    return raw.decode("cp1251", errors="replace")


def read_pages(path: Path):
    """Выдаёт HTML-страницы FileStorage без извлечения файлов на диск."""
    if path.stat().st_size > MAX_STORAGE_BYTES:
        raise ValueError("Файл HBK превышает 512 MiB")
    data = path.read_bytes()
    infos = _body(data, 16)
    if not infos or len(infos) % 12:
        raise ValueError("Некорректная таблица сущностей HBK")
    storage = None
    for header, body, reserved in struct.iter_unpack("<III", infos):
        if reserved != 0x7fffffff:
            continue
        payload = _number(data, header + 2)
        name = _slice(data, header + 51, payload - 24).decode("utf-16le").rstrip("\x00").strip('"')
        if name == "FileStorage":
            storage = _body(data, body)
            break
    if storage is None:
        raise ValueError("HBK не содержит FileStorage с HTML-справкой")
    with zipfile.ZipFile(io.BytesIO(storage)) as archive:
        unpacked = 0
        for entry in archive.infolist():
            if not entry.filename.lower().endswith((".html", ".htm")):
                continue
            # Заявленному в заголовке размеру не верим: считаем реально распакованное.
            with archive.open(entry) as stream:
                raw = stream.read(MAX_HTML_BYTES + 1)
            unpacked += len(raw)
            if len(raw) > MAX_HTML_BYTES or unpacked > MAX_STORAGE_BYTES:
                raise ValueError("Распакованная справка HBK превышает лимит размера")
            yield entry.filename, decode_html(raw)
