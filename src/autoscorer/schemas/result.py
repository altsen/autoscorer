from __future__ import annotations
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class Result(BaseModel):
    """标准化评分结果格式
    
    所有评分器必须返回此格式的结果，确保输出一致性
    """
    summary: Dict[str, Union[float, bool, str]] = Field(
        default_factory=dict,
        description="主要评分摘要: score(主评分), rank(等级), pass(是否通过)等"
    )
    metrics: Dict[str, float] = Field(
        default_factory=dict, 
        description="详细指标数据，必须包含summary中的所有数值指标"
    )
    artifacts: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="生成的文件和资源: {name: {path, size, sha256, metadata}}"
    )
    timing: Dict[str, float] = Field(
        default_factory=dict,
        description="性能时间记录: total_time, load_time, compute_time, save_time"
    )
    resources: Dict[str, Union[float, int]] = Field(
        default_factory=dict,
        description="资源使用情况: memory_peak, memory_average, cpu_usage, disk_usage"
    )
    versioning: Dict[str, str] = Field(
        default_factory=dict,
        description="版本信息: scorer, version, algorithm, timestamp等"
    )
    error: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="标准化错误信息: {code, message, stage, details}"
    )
