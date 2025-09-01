from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timezone

from autoscorer.pipeline import run_only, score_only, run_and_score
# Import scorers package to trigger static registrations on startup
from autoscorer import scorers as _builtin_scorers  # noqa: F401
from autoscorer.utils.errors import AutoscorerError, maybe_print_exception
from autoscorer.utils.config import Config
from autoscorer.utils.task_store import TaskStore
from autoscorer.scorers.registry import (
    get_registry, list_scorers, load_scorer_file, reload_scorer_file,
    start_watching_file, stop_watching_file, get_watched_files
)
import importlib.util, os, json

app = FastAPI(
    title="AutoScorer API", 
    version="0.1.0",
    description="AutoScorer REST API for automated scoring and evaluation"
)

# 任务结果持久化存储（SQLite）
_cfg = Config()
_task_store = TaskStore.from_config(_cfg)


def make_success_response(data: Any, meta: Optional[Dict] = None) -> Dict:
    """创建标准化成功响应"""
    response = {
        "ok": True,
        "data": data,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.1.0"
        }
    }
    if meta:
        response["meta"].update(meta)
    return response


def make_error_response(code: str, message: str, stage: str = "api", details: Optional[Dict] = None) -> Dict:
    """创建标准化错误响应"""
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "stage": stage,
            "details": details or {}
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.1.0"
        }
    }


class RunRequest(BaseModel):
    """Request body for /run

    Fields:
    - workspace: 工作区路径（必填）。
    """
    workspace: str = Field(..., description="工作区路径，包含 meta.json、input/ 与 output/ 等目录")


class ScoreRequest(BaseModel):
    """Request body for /score

    Fields:
    - workspace: 工作区路径（必填）。
    - params: 评分器入参（可选），若不提供则使用默认参数；scorer 从 meta.json 读取。
    """
    workspace: str = Field(..., description="工作区路径")
    params: Optional[Dict] = Field(default=None, description="评分器可选参数（覆盖默认值）")


class PipelineRequest(BaseModel):
    """Request body for /pipeline

    Fields:
    - workspace: 工作区路径（必填）。
    - params: 评分阶段参数（可选）。
    说明：backend 与 scorer 均从 workspace/meta.json 解析，不再通过请求体传入。
    """
    workspace: str = Field(..., description="工作区路径")
    params: Optional[Dict] = Field(default=None, description="传递给评分阶段的参数（可选）")


class SubmitRequest(BaseModel):
    """Request body for /submit (异步提交)

    Fields:
    - action: 任务类型：run|score|pipeline（默认 pipeline）
    - workspace: 工作区路径（必填）。
    - params: 评分阶段参数（可选，仅对 score/pipeline 有效）。
    - callback_url: 回调地址（可选）。
    说明：backend 与 scorer 从 meta.json 解析，不通过该接口传入。
    """
    action: Literal["run", "score", "pipeline"] = Field("pipeline", description="任务动作")
    workspace: str = Field(..., description="工作区路径")
    params: Optional[Dict] = Field(default=None, description="评分参数（可选）")
    callback_url: Optional[str] = Field(default=None, description="任务完成/失败时回调URL（可选）")


class TaskStatusResponse(BaseModel):
    id: str
    state: str
    result: Optional[Dict] = None


@app.get("/healthz")
async def healthz():
    """Health check endpoint

    Response:
    - ok: true
    - data: { status, timestamp, version }
    """
    return make_success_response({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0"
    })


@app.get("/")
async def api_info():
    """API meta info

    Response: 基本信息与主要端点列表。
    """
    return make_success_response({
        "name": "AutoScorer API",
        "version": "0.1.0",
        "description": "AutoScorer REST API for automated scoring and evaluation",
        "endpoints": {
            "core": ["/run", "/score", "/pipeline"],
            "scorers": ["/scorers", "/scorers/load", "/scorers/reload", "/scorers/test", "/scorers/watch"],
            "async": ["/submit", "/tasks/{task_id}"],
            "results": ["/result", "/logs"],
            "system": ["/healthz", "/"]
        },
        "documentation": "/docs"
    })


# 全局异常处理：根据开关友好打印堆栈
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    maybe_print_exception(exc)
    return JSONResponse(
        make_error_response("UNHANDLED_ERROR", str(exc)),
        status_code=500,
    )


# === Scorer管理API ===

@app.get("/scorers")
async def list_available_scorers():
    """List registered scorers

    Response: { scorers, total, watched_files }
    """
    try:
        scorers = list_scorers()
        watched_files = get_watched_files()
        
        data = {
            "scorers": scorers,
            "total": len(scorers),
            "watched_files": watched_files
        }
        
        return make_success_response(data)
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("LIST_ERROR", str(e), "scorer_management"),
            status_code=500
        )


class LoadScorerRequest(BaseModel):
    file_path: str
    force_reload: bool = False
    auto_watch: bool = True


@app.post("/scorers/load")
async def load_scorer(req: LoadScorerRequest):
    """Load a scorer Python file and register scorers defined with @register

    Request: { file_path, force_reload?, auto_watch? }
    Response: 加载到的注册名与类名映射。
    """
    try:
        # 检查文件是否存在
        if not Path(req.file_path).exists():
            return JSONResponse(
                make_error_response("FILE_NOT_FOUND", f"File not found: {req.file_path}", "scorer_loading"),
                status_code=404
            )
            
        loaded = load_scorer_file(req.file_path, req.force_reload)
        
        # 如果启用自动监控，开始监控文件
        if req.auto_watch and loaded:
            start_watching_file(req.file_path)
        
        data = {
            "loaded_scorers": {name: cls.__name__ for name, cls in loaded.items()},
            "count": len(loaded),
            "auto_watch": req.auto_watch,
            "file_path": req.file_path
        }
        
        return make_success_response(data, {"action": "load_scorer"})
        
    except FileNotFoundError as e:
        return JSONResponse(
            make_error_response("FILE_NOT_FOUND", str(e), "scorer_loading"),
            status_code=404
        )
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("LOAD_ERROR", str(e), "scorer_loading"),
            status_code=500
        )


@app.post("/scorers/reload")
async def reload_scorer(req: LoadScorerRequest):
    """Reload a scorer Python file and re-register scorers

    Request: { file_path }
    Response: 重新加载到的注册名与类名映射。
    """
    try:
        # 检查文件是否存在
        if not Path(req.file_path).exists():
            return JSONResponse(
                make_error_response("FILE_NOT_FOUND", f"File not found: {req.file_path}", "scorer_reloading"),
                status_code=404
            )
            
        loaded = reload_scorer_file(req.file_path)
        
        data = {
            "reloaded_scorers": {name: cls.__name__ for name, cls in loaded.items()},
            "count": len(loaded),
            "file_path": req.file_path
        }
        
        return make_success_response(data, {"action": "reload_scorer"})
        
    except FileNotFoundError as e:
        return JSONResponse(
            make_error_response("FILE_NOT_FOUND", str(e), "scorer_reloading"),
            status_code=404
        )
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("RELOAD_ERROR", str(e), "scorer_reloading"),
            status_code=500
        )


class WatchFileRequest(BaseModel):
    file_path: str
    check_interval: float = 1.0


@app.post("/scorers/watch")
async def start_watch_file(req: WatchFileRequest):
    """Start watching a file for changes (hot-reload)

    Request: { file_path, check_interval? }
    Response: 启动监控的确认信息。
    """
    try:
        start_watching_file(req.file_path, req.check_interval)
        data = {
            "message": f"Started watching {req.file_path}",
            "file_path": req.file_path,
            "check_interval": req.check_interval
        }
        return make_success_response(data, {"action": "watch_start"})
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("WATCH_ERROR", str(e), "scorer_watch", {"file_path": req.file_path}),
            status_code=500
        )


@app.delete("/scorers/watch")
async def stop_watch_file(file_path: str):
    """Stop watching a file

    Query: file_path
    Response: 停止监控的确认信息或未在监控的提示。
    """
    try:
        success = stop_watching_file(file_path)
        if success:
            return make_success_response({
                "message": f"Stopped watching {file_path}",
                "file_path": file_path
            }, {"action": "watch_stop"})
        else:
            return JSONResponse(
                make_error_response("NOT_WATCHING", f"File {file_path} is not being watched", "scorer_watch", {"file_path": file_path}),
                status_code=404
            )
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("STOP_WATCH_ERROR", str(e), "scorer_watch", {"file_path": file_path}),
            status_code=500
        )


@app.get("/scorers/watch")
async def get_watched_files_api():
    """List watched files

    Response: { watched_files, count }
    """
    try:
        watched = get_watched_files()
        data = {
            "watched_files": watched,
            "count": len(watched)
        }
        return make_success_response(data, {"action": "watch_list"})
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("GET_WATCHED_ERROR", str(e), "scorer_watch"),
            status_code=500
        )


class TestScorerRequest(BaseModel):
    scorer_name: str
    workspace: str
    params: Optional[Dict] = None


@app.post("/scorers/test")
async def test_scorer(req: TestScorerRequest):
    """Run a scorer class directly for a workspace (debug/testing)

    Request: { scorer_name, workspace, params? }
    Response: 完整 Result 对象的序列化结果。
    """
    try:
        from autoscorer.scorers.registry import get_scorer_class
        from pathlib import Path
        import time
        
        start_time = time.time()
        
        # 检查scorer是否存在
        scorer_cls = get_scorer_class(req.scorer_name)
        if scorer_cls is None:
            available_scorers = list_scorers()
            return JSONResponse(
                make_error_response(
                    "SCORER_NOT_FOUND", 
                    f"Scorer '{req.scorer_name}' not found",
                    "scorer_testing",
                    {"available_scorers": list(available_scorers.keys())}
                ),
                status_code=404
            )
        
        # 执行scorer
        workspace = Path(req.workspace)
        scorer = scorer_cls()
        result = scorer.score(workspace, req.params or {})
        
        execution_time = time.time() - start_time
        
        # 序列化 Result (兼容 pydantic v1/v2)
        result_payload = result.model_dump() if hasattr(result, "model_dump") else (result.dict() if hasattr(result, "dict") else result)
        data = {
            "scorer_name": req.scorer_name,
            "scorer_class": scorer_cls.__name__,
            "workspace": str(workspace),
            "result": result_payload  # 完整的Result对象
        }
        
        meta = {
            "action": "test_scorer",
            "execution_time": execution_time,
            "scorer_used": req.scorer_name
        }
        
        return make_success_response(data, meta)
        
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("TEST_ERROR", str(e), "scorer_testing"),
            status_code=500
        )


@app.post("/run")
async def api_run(req: RunRequest):
    """Run inference only

    Request: { workspace }
    Behavior: backend 从 workspace/meta.json 或系统默认策略解析，本接口不再接收 backend 参数。
    Response: { ok, stage, job_id }
    """
    import time
    start_time = time.time()

    # 验证工作区路径
    ws = Path(req.workspace)
    if not ws.exists():
        return JSONResponse(
            make_error_response("WORKSPACE_NOT_FOUND", f"Workspace not found: {req.workspace}", "validation", {"workspace": str(ws)}),
            status_code=404
        )
    
    try:
        # backend 由系统策略/配置决定，不通过API传入
        result = run_only(ws, backend=None)
        execution_time = time.time() - start_time
        
        data = {
            "result": result,
            "workspace": str(ws)
        }
        
        meta = {
            "action": "run_only",
            "execution_time": execution_time,
            "backend_used": "auto"
        }
        
        return make_success_response(data, meta)
        
    except AutoscorerError as e:
        logs_path = str((ws / "logs" / "container.log").resolve())
        details = {}
        if getattr(e, "details", None):
            try:
                details.update(e.details)  # type: ignore[arg-type]
            except Exception:
                pass
        details.update({"logs_path": logs_path, "workspace": str(ws)})
        return JSONResponse(
            make_error_response(e.code, e.message, "execution", details),
            status_code=400
        )
    except Exception as e:
        logs_path = str((ws / "logs" / "container.log").resolve())
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("EXEC_ERROR", str(e), "execution", {
                "logs_path": logs_path,
                "workspace": str(ws)
            }),
            status_code=500
        )


@app.post("/score")
async def api_score(req: ScoreRequest):
    """Score only

    Request: { workspace, params? }
    Behavior: scorer 从 workspace/meta.json 解析，本接口不再接收 scorer 参数。
    Response: { result, output_path, workspace }
    """
    import time
    start_time = time.time()

    # 验证工作区路径
    ws = Path(req.workspace)
    if not ws.exists():
        return JSONResponse(
            make_error_response("WORKSPACE_NOT_FOUND", f"Workspace not found: {req.workspace}", "validation", {"workspace": str(ws)}),
            status_code=404
        )
    
    try:
        # scorer 由 meta.json 决定
        result, output_path = score_only(ws, req.params or {}, scorer_override=None)
        execution_time = time.time() - start_time
        
        payload = result.model_dump() if hasattr(result, 'model_dump') else (result.dict() if hasattr(result, 'dict') else result)
        data = {
            "result": payload,
            "output_path": str(output_path),
            "workspace": str(ws)
        }
        meta = {
            "action": "score_only",
            "execution_time": execution_time,
            "scorer_used": "auto"
        }
        return make_success_response(data, meta)
        
    except AutoscorerError as e:
        details = {}
        if getattr(e, "details", None):
            try:
                details.update(e.details)  # type: ignore[arg-type]
            except Exception:
                pass
        details.update({"workspace": str(ws)})
        return JSONResponse(
            make_error_response(e.code, e.message, "scoring", details),
            status_code=400
        )
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("SCORE_ERROR", str(e), "scoring", {
                "workspace": str(ws)
            }),
            status_code=500
        )


@app.post("/pipeline")
async def api_pipeline(req: PipelineRequest):
    """Run inference then score (pipeline)

    Request: { workspace, params? }
    Behavior: backend & scorer 从 workspace/meta.json 解析，不再通过API传入。
    Response: { ok, result, result_path } 或标准化错误。
    """
    import time
    start_time = time.time()

    # 验证工作区路径
    ws = Path(req.workspace)
    if not ws.exists():
        return JSONResponse(
            make_error_response("WORKSPACE_NOT_FOUND", f"Workspace not found: {req.workspace}", "validation", {"workspace": str(ws)}),
            status_code=404
        )

    try:
        # backend/scorer 由 meta.json 决定
        result = run_and_score(ws, req.params or {}, backend=None, scorer_override=None)
        execution_time = time.time() - start_time
        
        # 检查结果中是否有错误
        if isinstance(result, dict) and result.get("error"):
            return JSONResponse(
                make_error_response(
                    result["error"].get("code", "PIPELINE_ERROR"),
                    result["error"].get("message", "Pipeline execution failed"),
                    result["error"].get("stage", "pipeline"),
                    result["error"].get("details", {})
                ),
                status_code=400
            )
        
        data = {
            "result": result,
            "workspace": str(ws)
        }
        
        meta = {
            "action": "pipeline",
            "execution_time": execution_time,
            "backend_used": "auto",
            "scorer_used": "auto"
        }
        
        return make_success_response(data, meta)
        
    except AutoscorerError as e:
        logs_path = str((ws / "logs" / "container.log").resolve())
        details = {}
        if getattr(e, "details", None):
            try:
                details.update(e.details)  # type: ignore[arg-type]
            except Exception:
                pass
        details.update({"logs_path": logs_path, "workspace": str(ws)})
        return JSONResponse(
            make_error_response(e.code, e.message, "pipeline", details),
            status_code=400
        )
    except Exception as e:
        logs_path = str((ws / "logs" / "container.log").resolve())
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("PIPELINE_ERROR", str(e), "pipeline", {
                "logs_path": logs_path,
                "workspace": str(ws)
            }),
            status_code=500
        )


# 同步结果与日志查询（基于 workspace）
@app.get("/result")
async def get_result(workspace: str):
    ws = Path(workspace)
    out = ws / "output" / "result.json"
    if not out.exists():
        return JSONResponse(
            make_error_response("RESULT_NOT_FOUND", "result.json not found", "score", {"path": str(out)}),
            status_code=404
        )
    try:
        data = json.loads(out.read_text())
        return make_success_response({
            "result": data,
            "path": str(out)
        }, {"action": "get_result"})
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("READ_RESULT_ERROR", str(e), "score", {"path": str(out)}),
            status_code=500
        )


@app.get("/logs")
async def get_logs(workspace: str):
    ws = Path(workspace)
    logf = ws / "logs" / "container.log"
    if not logf.exists():
        return JSONResponse(
            make_error_response("LOG_NOT_FOUND", "container.log not found", "run", {"path": str(logf)}),
            status_code=404
        )
    try:
        return make_success_response({"path": str(logf), "content": logf.read_text()}, {"action": "get_logs"})
    except Exception as e:
        maybe_print_exception(e)
        return JSONResponse(
            make_error_response("READ_LOG_ERROR", str(e), "run", {"path": str(logf)}),
            status_code=500
        )


# 异步提交与任务查询（Celery）
_celery_tasks_module_cache = None

def _load_celery_tasks_module():
    global _celery_tasks_module_cache
    if _celery_tasks_module_cache is not None:
        return _celery_tasks_module_cache
    root = Path(__file__).resolve().parents[3]
    tasks_path = root / "celery_app" / "tasks.py"
    spec = importlib.util.spec_from_file_location("celery_tasks", str(tasks_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore
    _celery_tasks_module_cache = module
    return module


@app.post("/submit")
async def submit_job(req: SubmitRequest):
    """Submit an async job via Celery

    Request: { action, workspace, params?, callback_url? }
    Behavior: backend & scorer 从 meta.json 解析；此处仅提交任务。
    Response: { submitted, task_id, action, workspace }（若去重则返回 running=true 和已有 task_id）。
    """
    mod = _load_celery_tasks_module()
    ws = str(Path(req.workspace))
    action = req.action.lower()
    # 去重：同一 workspace 正在运行则直接返回正在运行的任务ID
    existing_id: Optional[str] = None
    try:
        insp = mod.celery_app.control.inspect()
        active = insp.active() or {}
        for worker, tasks in (active or {}).items():
            for t in tasks or []:
                # 任务名可能是 celery_app.tasks.<func>
                args = t.get("argsrepr") or ""
                if ws in args:
                    existing_id = t.get("id")
                    break
            if existing_id:
                break
    except Exception as e:
        # 忽略去重检查错误，但打印堆栈（可选）
        maybe_print_exception(e)

    if existing_id:
        data = {"submitted": False, "running": True, "task_id": existing_id, "action": action, "workspace": ws}
        return make_success_response(data, {"action": "submit_dedup"})
    # 通过稳定的任务名提交，避免导入名导致的不一致
    task_name_map = {
        "run": "autoscorer.run_job",
        "score": "autoscorer.score_job",
        "pipeline": "autoscorer.run_and_score_job",
    }
    task_name = task_name_map.get(action, "autoscorer.run_and_score_job")
    args = {
        "autoscorer.run_job": (ws, None, req.callback_url),
        "autoscorer.score_job": (ws, req.params or {}, None, req.callback_url),
        "autoscorer.run_and_score_job": (ws, req.params or {}, None, req.callback_url),
    }[task_name]
    async_result = mod.celery_app.send_task(task_name, args=args)
    data = {"submitted": True, "task_id": async_result.id, "action": action, "workspace": ws}
    # 持久化初始状态
    try:
        _task_store.upsert(async_result.id, action=action, workspace=ws, state="SUBMITTED", result=None, error=None)
    except Exception as e:
        maybe_print_exception(e)
    return make_success_response(data, {"action": "submit"})


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    mod = _load_celery_tasks_module()
    async_result = mod.celery_app.AsyncResult(task_id)
    resp = {"id": task_id, "state": async_result.state}
    try:
        if async_result.ready():
            res = async_result.get(propagate=False)
            resp["result"] = res
            # 写回持久化（SUCCESS/FAILURE）
            try:
                state = async_result.state
                if state == "SUCCESS":
                    _task_store.upsert(task_id, state=state, result=res, finished=True)
                elif state in ("FAILURE", "REVOKED"):
                    # 尝试标准错误形态
                    err = res if isinstance(res, dict) else {"error": str(res)}
                
                    _task_store.upsert(task_id, state=state, error=err, finished=True)
                else:
                    _task_store.upsert(task_id, state=state)
            except Exception as e:
                maybe_print_exception(e)
        else:
            # 未就绪则回退到持久化（例如 broker/backend 丢失）
            stored = _task_store.get(task_id)
            if stored:
                resp.update({
                    "state": stored.get("state") or resp["state"],
                    "result": stored.get("result") or stored.get("error")
                })
    except Exception as e:
        resp["result"] = {"error": str(e)}
    return make_success_response(resp, {"action": "task_status"})


# for `uvicorn autoscorer.api.server:app --reload`
__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
