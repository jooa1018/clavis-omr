"""Per-run clock dependencies; tests never replace the shared time module."""

import time
from datetime import datetime


class Clock:
    def now(self) -> datetime:
        return datetime.now()

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
