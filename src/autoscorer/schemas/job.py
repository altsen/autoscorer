from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
import json


class Resources(BaseModel):
    cpu: float = 1.0
    memory: str = "2Gi"
    gpus: int = 0


class ContainerSpec(BaseModel):
    image: str
    cmd: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    shm_size: Optional[str] = None
    gpus: Optional[int] = None
    network_policy: Optional[str] = None  # none|restricted|allowlist


class JobSpec(BaseModel):
    job_id: str
    task_type: str
    scorer: str
    input_uri: str
    output_uri: str
    time_limit: int = 1800
    resources: Resources = Field(default_factory=Resources)
    container: ContainerSpec

    @staticmethod
    def from_workspace(ws: Path) -> "JobSpec":
        meta_path = ws / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"meta.json not found in {ws}")
        data = json.loads(meta_path.read_text())
        return JobSpec(**data)
