"""应用配置：所有可变项均通过环境变量或 backend/.env 管理。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """全局配置。环境变量前缀统一为 SOP_。"""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="SOP_",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 基础 ----------
    app_name: str = "工业 AI SOP 智能监控系统"
    app_version: str = "2.0.0"
    env: Literal["dev", "prod", "test"] = "dev"
    host: str = "127.0.0.1"
    port: int = 8000
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    # NoDecode：允许 .env 中使用英文逗号分隔，而不是强制 JSON 数组
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # ---------- 路径 ----------
    data_dir: Path = PROJECT_ROOT / "data"
    log_dir: Path = PROJECT_ROOT / "logs"
    database_path: Path | None = None

    # ---------- 工位 ----------
    station_id: str = "WS-01"
    station_name: str = "装配工位 A"

    # ---------- 推理 ----------
    inference_mode: Literal["auto", "mock", "yolo"] = "auto"
    model_path: Path = PROJECT_ROOT / "models" / "weights" / "gesture_yolo.pt"
    model_class_map: Path = PROJECT_ROOT / "models" / "class_map.json"
    model_device: str = "cpu"
    model_conf: float = 0.45
    model_iou: float = 0.50
    model_imgsz: int = 640
    inference_fps: float = 5.0
    detection_min_confidence: float = 0.50
    detection_stable_frames: int = 3
    detection_reset_ms: int = 500

    # ---------- 摄像头 ----------
    camera_mode: Literal["auto", "device", "synthetic", "off"] = "auto"
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: float = 12.0

    # ---------- 模拟检测器 ----------
    mock_scenario: Literal["clean", "faulty"] = "clean"
    mock_step_dwell_seconds: float = 2.0
    mock_rest_seconds: float = 1.0

    # ---------- SOP 规则策略 ----------
    fail_on_sequence_error: bool = True
    fail_on_timeout: bool = True
    session_max_seconds: int = 300
    auto_start_session: bool = True

    # ---------- 实时推送 ----------
    ws_telemetry_interval_ms: int = 300

    # ---------- 运行时 ----------
    runtime_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # ---------- 派生路径 ----------
    @property
    def database_file(self) -> Path:
        if self.database_path is None:
            return self.data_dir / "sop.db"
        return self._resolve(self.database_path)

    @property
    def model_file(self) -> Path:
        return self._resolve(self.model_path)

    @property
    def class_map_file(self) -> Path:
        return self._resolve(self.model_class_map)

    @property
    def logs_dir(self) -> Path:
        return self._resolve(self.log_dir)

    def _resolve(self, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
