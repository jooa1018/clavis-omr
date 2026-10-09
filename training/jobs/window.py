"""One overnight window, with an explicit closing date even after sleep/resume."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Window:
    opens: datetime
    closes: datetime

    @classmethod
    def next(cls, now: datetime) -> "Window":
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour >= 7:
            day += timedelta(days=1)
        return cls(day + timedelta(hours=1), day + timedelta(hours=7))

    def active(self, now: datetime) -> bool:
        return self.opens <= now < self.closes
