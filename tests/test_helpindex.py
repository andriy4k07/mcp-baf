"""HBK-контейнер, двуязычный поиск, кеш и ошибки построения."""

import io
import json
import struct
import sqlite3
import zipfile
from pathlib import Path

import pytest

from mcp_baf.helpindex import HelpIndex, parse_page
from mcp_baf.helpindex.hbk import _body, decode_html, read_pages

FIXTURE = Path(__file__).parent / 'testdata' / 'platform.hbk'


def make_hbk(pages):
    storage = io.BytesIO()
    with zipfile.ZipFile(storage, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, html in pages.items():
            archive.writestr(name, html)
    name = 'FileStorage'.encode('utf-16le')
    header_address = 16 + 31 + 12
    header_payload = bytes(20) + name + bytes(4)
    body_address = header_address + 31 + len(header_payload)
    def block(payload):
        return f'\r\n{len(payload):08x} {len(payload):08x} 7fffffff \r\n'.encode() + payload
    return bytes(16) + block(struct.pack('<III', header_address, body_address, 0x7fffffff)) + block(header_payload) + block(storage.getvalue())


def create_index(tmp_path, reindex=False):
    root = tmp_path / '8.3.14'
    root.mkdir(exist_ok=True)
    (root / 'platform.hbk').write_bytes(FIXTURE.read_bytes())
    index = HelpIndex(str(root), str(tmp_path / 'cache'), reindex)
    assert index.wait_ready(5)
    assert index.error is None
    return index, root


def test_hbk_fixture_and_bilingual_encoding():
    pages = dict(read_pages(FIXTURE))
    assert len(pages) == 6
    assert 'HTTPСоединение' in pages['types/http.html']
    assert decode_html('Массив'.encode('cp1251')) == 'Массив'
    assert decode_html('Массив'.encode()) == 'Массив'


def test_search_exact_title_aliases_filters_and_card(tmp_path):
    index, _ = create_index(tmp_path)
    try:
        assert index.search('Запрос')[0]['title'] == 'Запрос'
        assert index.search('HTTPConnection')[0]['title'] == 'HTTPСоединение (HTTPConnection)'
        assert index.search('СтрНайти')[0]['title'] == 'СтрНайти (StrFind)'
        assert index.search('StrFind')[0]['title'] == 'СтрНайти (StrFind)'
        assert all(p['section'] == 'operators' for p in index.search('Для', section='operators'))
        assert index.search('HTTPConnection', section='functions') == []
        assert index.get('httpconnection')[0]['version'] == '8.3.14'
        assert index.get('HTTPСоединение')[0]['title'].startswith('HTTPСоединение')
        assert 'Синтаксис' in index.get('СтрНайти')[0]['content']
        assert index.get('missing') == []
        with pytest.raises(ValueError, match='functions'):
            index.search('test', section='bad')
        assert index.search('" OR *') == []  # Операторы пользователя не передаются в FTS.
        with pytest.raises(ValueError):
            index.search('" *')
    finally:
        index.close()


def test_disk_cache_invalidation_corruption_and_reindex(tmp_path, monkeypatch):
    index, root = create_index(tmp_path)
    database = index.database
    initial = database.stat().st_mtime_ns
    index.close()
    import mcp_baf.helpindex as implementation
    original = implementation.read_pages
    def unexpected(*args):
        raise AssertionError('unchanged files must use cache')
    monkeypatch.setattr(implementation, 'read_pages', unexpected)
    cached = HelpIndex(str(root), str(tmp_path / 'cache'))
    assert cached.wait_ready(5) and cached.error is None
    assert cached.search('Запрос')
    assert database.stat().st_mtime_ns == initial
    cached.close()
    monkeypatch.setattr(implementation, 'read_pages', original)
    (root / 'extra.hbk').write_bytes(make_hbk({'functions/number.html': '<title>Число (Number)</title><p>Синтаксис: Число(Значение)</p>'}))
    updated = HelpIndex(str(root), str(tmp_path / 'cache'))
    assert updated.wait_ready(5) and updated.error is None
    assert updated.search('Number')
    updated.close()
    database.write_bytes(b'corrupt sqlite')
    recovered = HelpIndex(str(root), str(tmp_path / 'cache'))
    assert recovered.wait_ready(5) and recovered.error is None
    assert recovered.search('Number')
    recovered.close()
    rebuilt = HelpIndex(str(root), str(tmp_path / 'cache'), reindex=True)
    assert rebuilt.wait_ready(5) and rebuilt.error is None
    rebuilt.close()


@pytest.mark.parametrize('damage', ['DELETE FROM state', 'DROP TABLE search', 'DELETE FROM search'])
def test_incomplete_cache_recovers_instead_of_empty_search(tmp_path, damage):
    index, root = create_index(tmp_path)
    database = index.database
    index.close()
    with sqlite3.connect(database) as connection:
        connection.execute(damage)
    recovered = HelpIndex(str(root), str(tmp_path / 'cache'))
    assert recovered.wait_ready(5) and recovered.error is None
    try:
        assert recovered.search('Запрос')
    finally:
        recovered.close()


@pytest.mark.parametrize('bad_file', [None, b'broken HBK'])
def test_build_errors_are_explicit(tmp_path, bad_file):
    root = tmp_path / 'help'
    root.mkdir()
    if bad_file:
        (root / 'broken.hbk').write_bytes(bad_file)
    index = HelpIndex(str(root), str(tmp_path / 'cache'))
    assert index.wait_ready(5)
    try:
        with pytest.raises(RuntimeError, match='Справка недоступна'):
            index.search('Запрос')
    finally:
        index.close()


def test_html_sections_and_script_hidden():
    title, aliases, section, content = parse_page('<title>СКД</title><script>PRIVATE_SCRIPT</script><p>Синтаксис</p>', 'skd.html')
    assert title == 'СКД' and section == 'skd'
    assert 'PRIVATE_SCRIPT' not in content and 'Синтаксис' in content


def test_block_chain_and_cycle_detection():
    def header(total, block, following):
        return f'\r\n{total:08x} {block:08x} {following:08x} \r\n'.encode()
    assert _body(header(6, 3, 34) + b'abc' + header(3, 3, 0x7fffffff) + b'def', 0) == b'abcdef'
    with pytest.raises(ValueError, match='Циклическая'):
        _body(header(6, 3, 0) + b'abc', 0)


def test_ambiguous_cards_source_disambiguates(tmp_path):
    index, root = create_index(tmp_path)
    index.close()
    (root / 'other.hbk').write_bytes(FIXTURE.read_bytes())
    index = HelpIndex(str(root), str(tmp_path / 'cache'))
    assert index.wait_ready(5)
    try:
        candidates = index.get('Запрос')
        assert len(candidates) == 2
        assert len(index.get('Запрос', candidates[0]['source'])) == 1
    finally:
        index.close()


def test_broken_file_does_not_disable_help_and_partial_names_match(tmp_path):
    root = tmp_path / 'help'
    root.mkdir()
    (root / 'good.hbk').write_bytes(FIXTURE.read_bytes())
    (root / 'broken.hbk').write_bytes(b'x' * 100)
    index = HelpIndex(str(root), str(tmp_path / 'cache'))
    try:
        assert index.wait_ready(5) and index.error is None
        # Часть CamelCase-имени, начало имени и фраза с лишним словом.
        for query in ('Найти', 'Str', 'стрнай', 'как работает СтрНайти'):
            assert 'СтрНайти (StrFind)' in [p['title'] for p in index.search(query)], query
    finally:
        index.close()


def test_only_broken_files_report_the_file_name(tmp_path):
    (tmp_path / 'broken.hbk').write_bytes(b'x' * 100)
    index = HelpIndex(str(tmp_path), str(tmp_path / 'cache'))
    assert index.wait_ready(5)
    assert 'broken.hbk' in str(index.error)


def test_table_cells_stay_separate_and_bad_bytes_do_not_fail():
    content = parse_page('<table><tr><td>Имя</td><td>Тип</td></tr></table>', 'a.html')[3]
    assert content == 'Имя Тип'
    assert parse_page('<title>Функциональные опции</title>', 'types/a.html')[2] == 'types'
    assert decode_html('Массив'.encode('cp1251') + b'\x98') == 'Массив�'


def test_unpacked_size_is_measured_not_declared(tmp_path, monkeypatch):
    path = tmp_path / 'big.hbk'
    path.write_bytes(make_hbk({'a.html': '<p>' + 'я' * 100 + '</p>'}))
    monkeypatch.setattr('mcp_baf.helpindex.hbk.MAX_HTML_BYTES', 50)
    with pytest.raises(ValueError, match='лимит'):
        list(read_pages(path))
