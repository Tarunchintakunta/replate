"""One background thread for model inference.

Paddle and PyTorch are not reliable when the same loaded model is called from
whichever thread a request happens to run on. A single lane also keeps the two
models from running at the same time.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="inference")
_lane_ident: int | None = None
_ident_lock = threading.Lock()


def run_inference(func: Callable[[], T]) -> T:
    ident = threading.get_ident()
    if ident == _lane_ident:
        return func()
    return _executor.submit(_enter, func).result()


def _enter(func: Callable[[], T]) -> T:
    global _lane_ident
    with _ident_lock:
        _lane_ident = threading.get_ident()
    return func()
