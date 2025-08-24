from __future__ import annotations
from pathlib import Path
from abc import ABC, abstractmethod
from ..schemas.job import JobSpec


class Executor(ABC):
    @abstractmethod
    def run(self, spec: JobSpec, workspace: Path) -> None:
        """执行选手容器完成推理阶段。"""
        raise NotImplementedError
