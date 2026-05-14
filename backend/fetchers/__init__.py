from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchResult:
    source: str
    title: str
    detail: str | None = None
    time: str | None = None
    url: str | None = None
    priority: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "detail": self.detail,
            "time": self.time,
            "url": self.url,
            "priority": self.priority,
        }
