# 模型权重目录

将训练好的 YOLO 权重放在此目录（例如 `gesture_yolo.pt`），并在 `backend/.env` 中配置：

```
SOP_MODEL_PATH=models/weights/gesture_yolo.pt
SOP_INFERENCE_MODE=auto
```

权重文件不会提交到 Git。类别映射见 `models/class_map.json`。
