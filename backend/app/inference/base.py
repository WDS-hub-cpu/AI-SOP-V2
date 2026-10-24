"""检测器统一接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

import numpy as np

from app.domain.models import Detection


class DetectorStatus(StrEnum):
    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    READY = "READY"
    MOCK = "MOCK"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


class BaseDetector(ABC):
    name = "base"
    simulated = False

    def __init__(self) -> None:
        self.status = DetectorStatus.UNLOADED
        self.error: str | None = None

    @abstractmethod
    def load(self) -> None:
        """加载模型（同步，调用方需放入线程池）。"""

    @abstractmethod
    def predict(self, frame: np.ndarray | None) -> Detection:
        """返回单帧检测结果；无目标时 gesture 为 None。"""

    def unload(self) -> None:
        self.status = DetectorStatus.UNLOADED

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "simulated": self.simulated,
            "error": self.error,
        }
