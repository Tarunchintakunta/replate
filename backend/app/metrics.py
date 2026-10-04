"""In-process timings so performance can be measured, not guessed."""

from __future__ import annotations

from threading import Lock
from time import perf_counter
from typing import Any

_lock = Lock()
_samples: list[dict[str, Any]] = []


def record(name: str, elapsed_ms: float, **extra: Any) -> None:
    item = {"name": name, "elapsed_ms": round(elapsed_ms, 2), **extra}
    with _lock:
        _samples.append(item)
        if len(_samples) > 500:
            del _samples[:100]


def snapshot() -> list[dict[str, Any]]:
    with _lock:
        return list(_samples)


def clear() -> None:
    with _lock:
        _samples.clear()


class Timer:
    def __init__(self) -> None:
        self._start = perf_counter()

    def ms(self) -> float:
        return (perf_counter() - self._start) * 1000.0
