import json
from pathlib import Path

import pytest

from athena.cli import main


def test_openapi_export_does_not_touch_the_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "real-data-dir"
    monkeypatch.setenv("ATHENA_DATA_DIR", str(data_dir))
    out = tmp_path / "openapi.json"
    assert main(["openapi", "--output", str(out)]) == 0
    assert "/api/auth/login" in json.loads(out.read_text())["paths"]
    assert not data_dir.exists()
