from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ClassEvent:
    title: str
    start_dt: datetime
    end_dt: datetime
    location: Optional[str]
    status: Optional[str]
    remark: Optional[str]
    instructor: Optional[str]
    student: Optional[str]
    raw_id: Optional[str]

    def uid_basis(self) -> str:
        parts = [
            self.start_dt.strftime("%Y-%m-%d %H:%M"),
            self.end_dt.strftime("%Y-%m-%d %H:%M"),
            self.title or "",
            self.instructor or "",
            self.student or "",
        ]
        return "|".join(parts)

