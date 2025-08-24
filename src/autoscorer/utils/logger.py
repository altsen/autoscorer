import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import sys
import os


class StructuredLogger:
    """结构化日志记录器，支持JSON格式和文件轮转"""
    
    def __init__(self, log_path: Path, max_size_mb: int = 10, backup_count: int = 5):
        self.log_path = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用RotatingFileHandler实现日志轮转
        self._handler = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # 配置格式
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self._handler.setFormatter(formatter)
        
        # 创建logger
        self._logger = logging.getLogger(f"autoscorer.{log_path.stem}")
        self._logger.setLevel(logging.INFO)
        self._logger.addHandler(self._handler)

    def log(self, event: str, data: Dict[str, Any], level: str = "INFO"):
        """记录结构化日志条目"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data,
        }
        
        # 将结构化数据作为JSON字符串记录
        message = json.dumps(entry, ensure_ascii=False, default=str)
        
        # 根据level记录
        log_level = getattr(logging, level.upper(), logging.INFO)
        self._logger.log(log_level, message)

    def info(self, event: str, data: Dict[str, Any]):
        """记录INFO级别日志"""
        self.log(event, data, "INFO")
    
    def warning(self, event: str, data: Dict[str, Any]):
        """记录WARNING级别日志"""
        self.log(event, data, "WARNING")
    
    def error(self, event: str, data: Dict[str, Any]):
        """记录ERROR级别日志"""
        self.log(event, data, "ERROR")

    def close(self):
        """关闭日志记录器"""
        if self._handler:
            self._handler.close()
            self._logger.removeHandler(self._handler)


def setup_logging(log_dir: str = "logs", 
                 level: str = "INFO",
                 enable_console: bool = True,
                 enable_file: bool = True) -> logging.Logger:
    """设置应用程序的基础日志配置
    
    Args:
        log_dir: 日志目录
        level: 日志级别
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        
    Returns:
        配置好的根logger
    """
    
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 配置根logger
    root_logger = logging.getLogger("autoscorer")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 清除现有handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # 文件handler
    if enable_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / "autoscorer.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取命名的logger"""
    return logging.getLogger(f"autoscorer.{name}")


class JobLogger:
    """作业特定的日志记录器"""
    
    def __init__(self, job_id: str, workspace: Path):
        self.job_id = job_id
        self.workspace = workspace
        self.logs_dir = workspace / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建结构化日志记录器
        self.structured_logger = StructuredLogger(
            self.logs_dir / "job.jsonl"
        )
        
        # 创建标准logger
        self.logger = get_logger(f"job.{job_id}")
    
    def start(self, spec_data: Dict[str, Any]):
        """记录作业开始"""
        self.structured_logger.info("job_started", {
            "job_id": self.job_id,
            "workspace": str(self.workspace),
            "spec": spec_data
        })
        self.logger.info(f"Job {self.job_id} started in workspace {self.workspace}")
    
    def execution_start(self, backend: str, executor_info: Dict[str, Any]):
        """记录执行开始"""
        self.structured_logger.info("execution_started", {
            "job_id": self.job_id,
            "backend": backend,
            "executor_info": executor_info
        })
        self.logger.info(f"Job {self.job_id} execution started with {backend} backend")
    
    def execution_end(self, success: bool, duration: float, details: Dict[str, Any]):
        """记录执行结束"""
        event = "execution_completed" if success else "execution_failed"
        self.structured_logger.log(event, {
            "job_id": self.job_id,
            "success": success,
            "duration_seconds": duration,
            "details": details
        }, "INFO" if success else "ERROR")
        
        status = "completed" if success else "failed"
        self.logger.info(f"Job {self.job_id} execution {status} in {duration:.2f}s")
    
    def scoring_start(self, scorer: str, params: Dict[str, Any]):
        """记录评分开始"""
        self.structured_logger.info("scoring_started", {
            "job_id": self.job_id,
            "scorer": scorer,
            "params": params
        })
        self.logger.info(f"Job {self.job_id} scoring started with {scorer}")
    
    def scoring_end(self, success: bool, duration: float, result: Optional[Dict[str, Any]] = None):
        """记录评分结束"""
        event = "scoring_completed" if success else "scoring_failed"
        log_data = {
            "job_id": self.job_id,
            "success": success,
            "duration_seconds": duration
        }
        
        if result:
            log_data["result_summary"] = result.get("summary", {})
        
        self.structured_logger.log(event, log_data, "INFO" if success else "ERROR")
        
        status = "completed" if success else "failed"
        self.logger.info(f"Job {self.job_id} scoring {status} in {duration:.2f}s")
    
    def error(self, stage: str, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        """记录错误"""
        self.structured_logger.error("job_error", {
            "job_id": self.job_id,
            "stage": stage,
            "error_code": error_code,
            "message": message,
            "details": details or {}
        })
        self.logger.error(f"Job {self.job_id} error in {stage}: {error_code} - {message}")
    
    def close(self):
        """关闭日志记录器"""
        self.structured_logger.close()


# 全局配置
_logging_configured = False


def ensure_logging_configured(log_dir: str = "logs", level: str = "INFO"):
    """确保日志已配置（只配置一次）"""
    global _logging_configured
    if not _logging_configured:
        setup_logging(log_dir, level)
        _logging_configured = True
