"""Режим установки и справка CLI не должны импортировать MCP-сервер."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode', ['--help', '--version', '--install'])
def test_cli_works_when_mcp_sdk_import_is_unavailable(tmp_path, mode):
    # Отдельный процесс исключает уже импортированный другими тестами SDK.
    script = '''
import importlib.abc
import sys

class UnavailableSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mcp" or fullname.startswith("mcp.") or fullname == "mcp_baf.server":
            raise ModuleNotFoundError("MCP SDK unavailable", name=fullname)

sys.meta_path.insert(0, UnavailableSDK())
from mcp_baf import installer
def install(**kwargs):
    assert kwargs["db_path"] == "TEST_DATABASE"
    print("MOCK_INSTALL_CALLED")
installer.install = install
from mcp_baf.__main__ import main
sys.argv = ["mcp-baf"] + sys.argv[1:]
main()
'''
    args = [mode]
    if mode == '--install':
        args += ['TEST_DATABASE', '--cache-dir', str(tmp_path)]
    result = subprocess.run([sys.executable, '-c', script, *args], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    if mode == '--install':
        assert 'MOCK_INSTALL_CALLED' in result.stdout
        assert 'Extension installed successfully.' in result.stdout
