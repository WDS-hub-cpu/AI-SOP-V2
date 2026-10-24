"""pytest 公共夹具：使用临时数据库、关闭采集线程、强制模拟检测器。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        runtime_enabled=False,
        inference_mode="mock",
        camera_mode="off",
        data_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        database_path=tmp_path / "test.db",
        station_id="TEST-01",
        station_name="测试工位",
    )


@pytest.fixture()
def client(settings: Settings):
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
