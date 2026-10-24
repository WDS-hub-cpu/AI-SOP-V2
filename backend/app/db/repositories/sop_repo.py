"""SOP 步骤配置仓储。"""

from __future__ import annotations

from app.core.timeutil import iso
from app.db.database import Database
from app.domain.models import SopStep

DEFAULT_STEPS: tuple[SopStep, ...] = (
    SopStep(1, "举起 1 根手指", "ONE", "确认来料到位，核对工单", 20, True, True),
    SopStep(2, "举起 2 根手指", "TWO", "扫码核对物料编码", 20, True, True),
    SopStep(3, "举起 3 根手指", "THREE", "安装定位销并确认到位", 25, True, True),
    SopStep(4, "举起 4 根手指", "FOUR", "拧紧固定螺钉至规定扭矩", 30, True, True),
    SopStep(5, "举起 5 根手指", "FIVE", "完成自检，允许放行", 20, True, True),
)


class SopRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def seed_if_empty(self) -> None:
        if self.count() == 0:
            self.replace_steps(list(DEFAULT_STEPS))

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS c FROM sop_steps")
        return int(row["c"]) if row else 0

    def list_steps(self, *, enabled_only: bool = False) -> list[SopStep]:
        sql = "SELECT * FROM sop_steps"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY step_order ASC"
        return [self._to_step(row) for row in self.db.query_all(sql)]

    def replace_steps(self, steps: list[SopStep]) -> None:
        timestamp = iso()
        with self.db.connect() as conn:
            conn.execute("DELETE FROM sop_steps")
            conn.executemany(
                """
                INSERT INTO sop_steps
                    (step_order, name, expected_gesture, description,
                     timeout_seconds, enabled, required, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        step.order,
                        step.name,
                        step.gesture,
                        step.description,
                        step.timeout_seconds,
                        int(step.enabled),
                        int(step.required),
                        timestamp,
                    )
                    for step in steps
                ],
            )

    def reset_to_defaults(self) -> list[SopStep]:
        self.replace_steps(list(DEFAULT_STEPS))
        return self.list_steps()

    @staticmethod
    def _to_step(row) -> SopStep:
        return SopStep(
            order=int(row["step_order"]),
            name=str(row["name"]),
            gesture=str(row["expected_gesture"]),
            description=str(row["description"] or ""),
            timeout_seconds=int(row["timeout_seconds"]),
            enabled=bool(row["enabled"]),
            required=bool(row["required"]),
        )
