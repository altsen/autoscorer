from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, Tuple

from autoscorer.schemas.job import JobSpec
from autoscorer.schemas.result import Result
from autoscorer.scheduler import Scheduler
from autoscorer.executor.docker_executor import DockerExecutor
from autoscorer.scorers.registry import get_scorer, load_scorer_directory, get_scorer_class
# Ensure static scorer registration is performed even when called outside CLI/API
from autoscorer import scorers as _builtin_scorers  # noqa: F401
from autoscorer.utils.errors import AutoscorerError, make_error
from autoscorer.utils.logger import get_logger
from autoscorer.utils.artifacts import ArtifactManager

logger = get_logger("pipeline")
from autoscorer.utils.workspace_validator import validate_workspace


def run_only(workspace: Path, backend: Optional[str] = None) -> Dict:
    """执行推理（不评分）。返回阶段状态。"""
    ws = workspace.resolve()
    
    # 工作区校验
    validation_result = validate_workspace(ws)
    if not validation_result["ok"]:
        # 收集所有错误并抛出第一个
        errors = validation_result["errors"]
        first_error = errors[0]
        if ":" in first_error:
            code, message = first_error.split(":", 1)
            code = code.strip()
            message = message.strip()
        else:
            code = "VALIDATION_ERROR"
            message = first_error
        raise AutoscorerError(code=code, message=message, details={"all_errors": errors})
    
    spec = JobSpec.from_workspace(ws)
    # 按既有策略选择执行器
    backend = (backend or "auto").lower()
    if backend == "docker":
        ex = DockerExecutor()
        ex.run(spec, ws)
    else:
        # k8s 或 auto 走调度器逻辑（由调度器自行决定）
        scheduler = Scheduler()
        scheduler.schedule(spec, ws)
    return {"ok": True, "stage": "inference_done", "job_id": spec.job_id}


def score_only(workspace: Path, params: Optional[Dict] = None, scorer_override: Optional[str] = None) -> Tuple[Result, Path]:
    """执行评分，返回标准化Result与result.json路径。"""
    ws = workspace.resolve()
    spec = JobSpec.from_workspace(ws)
    import time
    t0 = time.perf_counter()
    t_validate = 0.0
    t_compute = 0.0
    t_save = 0.0
    
    # 如果指定了scorer_override，使用它覆盖meta.json中的设置
    if scorer_override:
        logger.info(f"Using scorer override: {scorer_override} (original: {spec.scorer})")
        spec.scorer = scorer_override
    
    # 尝试加载自定义scorer（优先从当前工作目录）
    for custom_dir in [
        Path.cwd() / "custom_scorers",  # 当前工作目录
        ws.parent / "custom_scorers",   # workspace父目录
        ws / "custom_scorers"           # workspace内
    ]:
        if custom_dir.exists():
            try:
                loaded_custom = load_scorer_directory(str(custom_dir))
                if loaded_custom:
                    logger.info(
                        f"Loaded {len(loaded_custom)} custom scorer(s) from {custom_dir}: {list(loaded_custom.keys())}"
                    )
            except Exception as e:
                logger.warning(f"Failed to load custom scorers from {custom_dir}: {e}")
    
    # 获取scorer（可能是内置的也可能是自定义的）
    try:
        scorer = get_scorer(spec.scorer)
        logger.info(f"Using scorer: {spec.scorer}")
    except KeyError:
        # 如果找不到scorer，尝试从class获取
        scorer_cls = get_scorer_class(spec.scorer)
        if scorer_cls is None:
            from autoscorer.scorers.registry import list_scorers
            available_scorers = list(list_scorers().keys())
            raise AutoscorerError(
                code="SCORER_NOT_FOUND",
                message=f"Scorer '{spec.scorer}' not found. Available scorers: {available_scorers}",
                details={"requested_scorer": spec.scorer, "available_scorers": available_scorers}
            )
        scorer = scorer_cls()
        logger.info(f"Using scorer class: {spec.scorer} -> {scorer_cls.__name__}")
    # 评分器自校验（若实现了 validate 方法）
    try:
        if hasattr(scorer, "validate") and callable(getattr(scorer, "validate")):
            logger.info("Running scorer-specific validation ...")
            v0 = time.perf_counter()
            scorer.validate(ws, params or {})
            t_validate = time.perf_counter() - v0
    except AutoscorerError:
        raise
    except Exception as e:
        raise AutoscorerError(code="DATA_VALIDATION_ERROR", message=str(e))

    # 评分计算
    c0 = time.perf_counter()
    result: Result = scorer.score(ws, params or {})
    t_compute = time.perf_counter() - c0
    out = ws / "output" / "result.json"
    # 合并 timing（以流水线观测为主，保留评分器已有的 timing 字段）
    timing = {}
    try:
        # 兼容 v1/v2
        timing = dict(getattr(result, "timing", {}) or {})
    except Exception:
        timing = {}
    timing.update({
        "validate_time": t_validate,
        "compute_time": t_compute,
    })
    # 构建 artifacts（通用输入输出文件 + artifacts目录收集）
    input_gt = ws / "input" / "gt.csv"
    if not input_gt.exists():
        input_gt = ws / "input" / "gt.json"
    output_pred = ws / "output" / "pred.csv"
    if not output_pred.exists():
        output_pred = ws / "output" / "pred.json"
    artifacts = {}
    if input_gt.exists():
        artifacts["input_gt"] = ArtifactManager.file_info(input_gt)
    if output_pred.exists():
        artifacts["output_pred"] = ArtifactManager.file_info(output_pred)
    # 收集 output/artifacts 下的常见文件
    art_dir = ws / "output" / "artifacts"
    dir_items = ArtifactManager.collect_dir(art_dir, patterns=("*.json", "*.csv", "*.txt", "*.png", "*.svg"))
    for name, info in dir_items.items():
        artifacts[f"artifacts/{name}"] = info
    # 预先写一次（若评分器未包含 timing/artifacts，避免覆盖）
    try:
        data = result.model_dump()
    except Exception:
        data = getattr(result, "dict", lambda: getattr(result, "__dict__", {}))()
    # 合并已有 artifacts
    existing_artifacts = dict(data.get("artifacts", {}) or {})
    existing_artifacts.update(artifacts)
    data["artifacts"] = existing_artifacts
    data["timing"] = timing
    # 保存 result.json
    import json as _json
    s0 = time.perf_counter()
    out.write_text(_json.dumps(data, ensure_ascii=False, indent=2))
    t_save = time.perf_counter() - s0
    # 追加 result.json 自身文件信息
    existing_artifacts["result_json"] = ArtifactManager.file_info(out)
    data["artifacts"] = existing_artifacts
    # 更新 total_time
    total_time = (time.perf_counter() - t0)
    data["timing"]["save_time"] = t_save
    data["timing"]["total_time"] = total_time
    # 覆盖写入，确保 timing/artifacts 完整
    out.write_text(_json.dumps(data, ensure_ascii=False, indent=2))
    # 回组 Result 对象
    try:
        result = Result(**data)
    except Exception:
        # 回退：返回原始 result，但文件已含完整信息
        pass
    return result, out


def run_and_score(workspace: Path, params: Optional[Dict] = None, backend: Optional[str] = None, scorer_override: Optional[str] = None) -> Dict:
    """先运行容器完成推理，随后立即评分，形成流水线。"""
    ws = workspace.resolve()
    # Run
    try:
        run_only(ws, backend=backend)
    except AutoscorerError as e:
        logs = str((ws / "logs" / "container.log").resolve())
        return make_error("run", e.code, e.message, details=e.details, logs_path=logs)
    except Exception as e:
        logs = str((ws / "logs" / "container.log").resolve())
        return make_error("run", "EXEC_ERROR", str(e), logs_path=logs)

    # Score - 支持scorer覆盖
    try:
        result, out = score_only(ws, params or {}, scorer_override=scorer_override)
        return {"ok": True, "result": result.model_dump(), "result_path": str(out)}
    except AutoscorerError as e:
        out = ws / "output" / "result.json"
        result = Result(error=make_error("score", e.code, e.message, details=e.details))
        out.write_text(result.model_dump_json(indent=2))
        return result.model_dump()
    except Exception as e:
        out = ws / "output" / "result.json"
        result = Result(error=make_error("score", "SCORE_ERROR", str(e)))
        out.write_text(result.model_dump_json(indent=2))
        return result.model_dump()
