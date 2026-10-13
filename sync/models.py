from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ClassEvent:
    title: str
    start_dt: datetime
    end_dt: datetime
    location: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    instructor: Optional[str] = None
    student: Optional[str] = None
    raw_id: Optional[str] = None

    def uid_basis(self) -> str:
        """What makes a lesson the same lesson across runs (status and remarks may change)."""
        parts = [
            self.start_dt.strftime("%Y-%m-%d %H:%M"),
            self.end_dt.strftime("%Y-%m-%d %H:%M"),
            self.title or "",
            self.instructor or "",
            self.student or "",
        ]
        return "|".join(parts)

    @property
    def uid(self) -> str:
        return hashlib.sha1(self.uid_basis().encode("utf-8")).hexdigest() + "@krutoosync"

    @property
    def description(self) -> str:
        lines = []
        if self.instructor:
            lines.append(f"Teacher: {self.instructor}")
        if self.status:
            lines.append(f"Status: {self.status}")
        if self.remark:
            lines.append(f"Remark: {self.remark}")
        lines.append("Source: krutooschool.com")
        return "\n".join(lines)
