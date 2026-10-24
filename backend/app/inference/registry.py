"""检测器工厂：根据配置选择真实 YOLO 或模拟检测器，并给出明确原因。"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.inference.base import BaseDetector
from app.inference.mock import MockDetector
from app.inference.yolo import YoloGestureDetector

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DetectorSelection:
    detector: BaseDetector
    requested_mode: str
    reason: str


def create_detector(settings: Settings) -> DetectorSelection:
    if settings.inference_mode == "mock":
        return DetectorSelection(
            MockDetector(settings), "mock", "配置 SOP_INFERENCE_MODE=mock，强制使用模拟检测器"
        )

    has_weights = settings.model_file.exists()
    has_ultralytics = importlib.util.find_spec("ultralytics") is not None

    if settings.inference_mode == "yolo":
        return DetectorSelection(
            YoloGestureDetector(settings),
            "yolo",
            "配置 SOP_INFERENCE_MODE=yolo，强制加载真实 YOLO 模型",
        )

    if has_weights and has_ultralytics:
        return DetectorSelection(
            YoloGestureDetector(settings),
            "auto",
            "检测到本地权重与 ultralytics，使用真实 YOLO",
        )

    missing = []
    if not has_weights:
        missing.append(f"缺少权重 {settings.model_file}")
    if not has_ultralytics:
        missing.append("未安装 ultralytics")
    reason = "auto 模式降级为模拟检测器：" + "；".join(missing)
    logger.warning(reason)
    return DetectorSelection(MockDetector(settings), "auto", reason)
