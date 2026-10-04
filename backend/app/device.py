"""CPU/GPU detection. A GPU is used when present and never required."""

from __future__ import annotations


def torch_device() -> str:
    try:
        import torch
    except Exception:
        return "cpu"
    try:
        if torch.cuda.is_available():
            return "cuda"
        # Apple GPU. LaMa on MPS matched CPU output within 4e-5 and ran ~16x faster warm.
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        return "cpu"
    return "cpu"


def paddle_device() -> str:
    try:
        import paddle
    except Exception:
        return "cpu"
    try:
        compiled = paddle.device.is_compiled_with_cuda()
        count = paddle.device.cuda.device_count() if compiled else 0
        if compiled and count > 0:
            return "gpu"
    except Exception:
        return "cpu"
    return "cpu"


def rss_mb() -> float | None:
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except OSError:
        return None
    return None
