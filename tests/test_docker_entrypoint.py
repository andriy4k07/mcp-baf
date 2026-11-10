"""Exec-форма ENTRYPOINT падает с permission denied, если скрипт без +x."""

import os
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_docker_entrypoint_is_executable():
    assert os.access(ROOT / "docker-entrypoint.sh", os.X_OK)
    assert "chmod 0755 /usr/local/bin/docker-entrypoint.sh" in (ROOT / "Dockerfile").read_text(encoding="utf-8")
