from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime, timezone

# 友好堆栈打印
try:
    from rich.console import Console
    from rich.traceback import Traceback
except Exception:  # pragma: no cover - 可选依赖保护
    Console = None
    Traceback = None

try:
    from .config import Config
except Exception:
    Config = None  # 在极早期导入失败时兜底


@dataclass
class AutoscorerError(Exception):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def make_error(stage: str, code: str, message: str, *, details: Optional[Dict[str, Any]] = None, logs_path: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "stage": stage,
        "code": code,
        "message": message,
    }
    if details:
        payload["details"] = details
    if logs_path:
        payload["logs"] = logs_path
    return payload


def _get_cfg_bool(key: str, default: bool = False) -> bool:
    """读取布尔配置（环境变量覆写优先）。"""
    try:
        if Config is None:
            return default
        cfg = Config()
        val = cfg.get(key, default)
        return bool(val)
    except Exception:
        return default


def maybe_print_exception(exc: BaseException):
    """根据配置决定是否打印堆栈，采用 rich 友好展示。

    配置开关：PRINT_STACKTRACE=true|false（默认 false）
    """
    enabled = _get_cfg_bool("PRINT_STACKTRACE", False)
    if not enabled:
        return

    # rich 可用则友好打印，否则回退到标准打印
    if Console and Traceback:
        console = Console(stderr=True, force_terminal=True)
        tb = Traceback.from_exception(type(exc), exc, exc.__traceback__)
        console.print(tb)
    else:  # pragma: no cover
        import traceback
        traceback.print_exception(type(exc), exc, exc.__traceback__)


def make_error_response(code: str, message: str, *, stage: str = "api", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """标准化错误响应（用于回调或API层统一组装）。"""
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "stage": stage,
            "details": details or {},
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.1.0",
        },
    }
