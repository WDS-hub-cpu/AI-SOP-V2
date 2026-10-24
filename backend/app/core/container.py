"""依赖容器：集中构建数据库、推理、采集、规则与实时推送组件。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.db.database import Database
from app.db.repositories import EventRepository, SessionRepository, SopRepository
from app.inference.base import BaseDetector
from app.inference.registry import create_detector
from app.services.camera import CameraManager
from app.services.runtime import RuntimeService
from app.services.stream_hub import StreamHub

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Container:
    settings: Settings
    db: Database
    sop_repo: SopRepository
    session_repo: SessionRepository
    event_repo: EventRepository
    detector: BaseDetector
    detector_reason: str
    camera: CameraManager
    hub: StreamHub
    runtime: RuntimeService

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        settings.ensure_directories()

        db = Database(settings.database_file)
        db.init()

        sop_repo = SopRepository(db)
        sop_repo.seed_if_empty()
        session_repo = SessionRepository(db)
        event_repo = EventRepository(db)

        closed = session_repo.close_stale_running()
        if closed:
            logger.warning("检测到 %d 个上次未正常结束的会话，已标记为 ABORTED", closed)

        selection = create_detector(settings)
        camera = CameraManager(settings)
        hub = StreamHub()

        runtime = RuntimeService(
            settings,
            db=db,
            sop_repo=sop_repo,
            session_repo=session_repo,
            event_repo=event_repo,
            detector=selection.detector,
            detector_reason=selection.reason,
            camera=camera,
            hub=hub,
        )
        logger.info(
            "依赖容器构建完成：模型=%s（%s），摄像头模式=%s，数据库=%s",
            selection.detector.name,
            selection.reason,
            settings.camera_mode,
            db.path,
        )
        return cls(
            settings=settings,
            db=db,
            sop_repo=sop_repo,
            session_repo=session_repo,
            event_repo=event_repo,
            detector=selection.detector,
            detector_reason=selection.reason,
            camera=camera,
            hub=hub,
            runtime=runtime,
        )
