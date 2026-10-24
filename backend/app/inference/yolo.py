"""Ultralytics YOLO 手势检测器。

- 权重与类别映射均通过配置提供，不写死本机路径；
- 类别名到 ONE..FIVE 的映射由 models/class_map.json 决定；
- 模型未加载/加载失败时状态为 ERROR，不会静默返回伪造结果。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import Settings
from app.domain.models import Box, Detection
from app.inference.base import BaseDetector, DetectorStatus

logger = logging.getLogger(__name__)

_GESTURES = {"ONE", "TWO", "THREE", "FOUR", "FIVE"}
_DEFAULT_ALIASES = {
    "one": "ONE",
    "1": "ONE",
    "two": "TWO",
    "2": "TWO",
    "three": "THREE",
    "3": "THREE",
    "four": "FOUR",
    "4": "FOUR",
    "five": "FIVE",
    "5": "FIVE",
}


class YoloGestureDetector(BaseDetector):
    name = "Ultralytics YOLO"
    simulated = False

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._model: Any = None
        self._aliases: dict[str, str] = {}
        self._class_names: dict[str, str] = {}
        self._mapped_classes: list[str] = []
        self._device = settings.model_device

    def load(self) -> None:
        self.status = DetectorStatus.LOADING
        self.error = None
        self._model = None
        self._mapped_classes = []
        self._class_names = {}

        path = self._settings.model_file
        if not path.exists():
            self.status = DetectorStatus.ERROR
            self.error = f"未找到模型权重：{path}"
            logger.error(self.error)
            return

        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - 依赖缺失
            self.status = DetectorStatus.ERROR
            self.error = f"ultralytics 导入失败：{exc}"
            logger.error(self.error)
            return

        try:
            self._aliases = self._load_aliases(self._settings.class_map_file)
            self._model = YOLO(str(path))
            names = getattr(self._model, "names", {}) or {}
            self._class_names = {str(k): str(v) for k, v in dict(names).items()}
            self._mapped_classes = [
                key
                for key, name in self._class_names.items()
                if self._resolve_gesture(name) is not None
            ]
            if not self._mapped_classes:
                sample = ", ".join(list(self._class_names.values())[:12]) or "空"
                raise ValueError(
                    "模型类别无法映射到 ONE..FIVE，请检查 models/class_map.json。"
                    f"当前类别示例：{sample}"
                )
            try:
                self._model.to(self._device)
            except Exception as exc:  # 设备不可用时回落到 CPU，并明确记录
                logger.warning("模型迁移到 %s 失败，回落到 CPU：%s", self._device, exc)
                self._device = "cpu"
                self._model.to("cpu")
            self.status = DetectorStatus.READY
            logger.info(
                "YOLO 模型加载完成：%s，类别数=%d，可映射类别=%s",
                path,
                len(self._class_names),
                self._mapped_classes,
            )
        except Exception as exc:
            self.status = DetectorStatus.ERROR
            self.error = f"模型加载失败：{exc}"
            self._model = None
            logger.error(self.error)

    def predict(self, frame: np.ndarray | None) -> Detection:
        started = time.perf_counter()
        if self.status != DetectorStatus.READY or self._model is None or frame is None:
            return Detection(None, None, 0.0, False, 0.0)

        try:
            results = self._model.predict(
                frame,
                conf=self._settings.model_conf,
                iou=self._settings.model_iou,
                imgsz=self._settings.model_imgsz,
                device=self._device,
                verbose=False,
            )
        except Exception as exc:
            logger.error("YOLO 推理失败：%s", exc)
            self.error = f"推理失败：{exc}"
            self.status = DetectorStatus.ERROR
            return Detection(None, None, 0.0, False, 0.0)

        inference_ms = (time.perf_counter() - started) * 1000
        if not results:
            return Detection(None, None, 0.0, False, inference_ms)

        boxes: list[Box] = []
        height, width = frame.shape[:2]
        best: tuple[str, str, float] | None = None
        top_label: str | None = None
        top_conf = 0.0

        for result in results:
            names = getattr(result, "names", {}) or {}
            xyxy = getattr(result.boxes, "xyxy", None)
            if xyxy is None:
                continue
            for row, conf_tensor, cls_tensor in zip(
                xyxy.cpu().numpy(),
                result.boxes.conf.cpu().numpy(),
                result.boxes.cls.cpu().numpy(),
            ):
                confidence = float(conf_tensor)
                class_name = str(names.get(int(cls_tensor), int(cls_tensor)))
                gesture = self._resolve_gesture(class_name)
                if confidence > top_conf:
                    top_conf = confidence
                    top_label = class_name
                if gesture is None:
                    continue
                x1, y1, x2, y2 = (float(v) for v in row[:4])
                boxes.append(
                    Box(
                        x1=x1 / max(width, 1),
                        y1=y1 / max(height, 1),
                        x2=x2 / max(width, 1),
                        y2=y2 / max(height, 1),
                        confidence=confidence,
                        label=class_name,
                        gesture=gesture,
                    )
                )
                if best is None or confidence > best[2]:
                    best = (gesture, class_name, confidence)

        if best is None:
            return Detection(None, top_label, round(top_conf, 4), False, inference_ms, [])

        return Detection(
            gesture=best[0],
            label=best[1],
            confidence=round(best[2], 4),
            simulated=False,
            inference_ms=round(inference_ms, 2),
            boxes=[box.as_dict() for box in boxes],
        )

    def unload(self) -> None:
        self._model = None
        self.status = DetectorStatus.UNLOADED

    def describe(self) -> dict[str, Any]:
        path = self._settings.model_file
        return {
            "name": self.name,
            "status": self.status,
            "simulated": False,
            "error": self.error,
            "backend": "ultralytics",
            "model_path": str(path),
            "weights_exist": path.exists(),
            "device": self._device,
            "confidence_threshold": self._settings.model_conf,
            "iou_threshold": self._settings.model_iou,
            "image_size": self._settings.model_imgsz,
            "class_count": len(self._class_names),
            "mapped_classes": self._mapped_classes,
            "class_map_path": str(self._settings.class_map_file),
        }

    # ---------- 类别映射 ----------
    def _resolve_gesture(self, class_name: str) -> str | None:
        key = class_name.strip()
        if key.upper() in _GESTURES:
            return key.upper()
        mapped = self._aliases.get(key) or self._aliases.get(key.lower())
        if mapped:
            return mapped
        return _DEFAULT_ALIASES.get(key.lower())

    @staticmethod
    def _load_aliases(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        classes = payload.get("classes", payload) if isinstance(payload, dict) else {}
        aliases: dict[str, str] = {}
        for raw, gesture in classes.items():
            value = str(gesture).strip().upper()
            if value in _GESTURES:
                aliases[str(raw)] = value
        return aliases
