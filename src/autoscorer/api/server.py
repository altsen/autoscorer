from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from autoscorer.pipeline import run_only, score_only, run_and_score
# Import scorers package to trigger static registrations on startup
from autoscorer import scorers as _builtin_scorers  # noqa: F401
from autoscorer.utils.errors import AutoscorerError, maybe_print_exception
from autoscorer.scorers.registry import (
    get_registry, list_scorers, load_scorer_file, reload_scorer_file,
    start_watching_file, stop_watching_file, get_watched_files
)
import importlib.util, os, json

app = FastAPI(title="autoscorer API", version="0.1.0")


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


class PipelineRequest(BaseModel):
    workspace: str
    params: Optional[Dict] = None
    backend: Optional[str] = None  # docker|k8s|auto
    scorer: Optional[str] = None  # 可选择特定的scorer


class SubmitRequest(PipelineRequest):
    action: str = "pipeline"  # run|score|pipeline
    callback_url: Optional[str] = None  # 任务完成/失败回调


class TaskStatusResponse(BaseModel):
    id: str
    state: str
    result: Optional[Dict] = None


@app.get("/healthz")
async def healthz():
    return make_success_response({"status": "healthy"})


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
    """列出所有可用的scorer"""
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
    """加载scorer文件"""
    try:
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
    """重新加载scorer文件"""
    try:
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
    """开始监控文件变化"""
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
    """停止监控文件"""
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
    """获取正在监控的文件列表"""
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
    """测试指定的scorer"""
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
async def api_run(req: PipelineRequest):
    """执行推理容器"""
    import time
    start_time = time.time()
    ws = Path(req.workspace)
    
    try:
        result = run_only(ws, backend=req.backend)
        execution_time = time.time() - start_time
        
        data = {
            "run_result": result,
            "workspace": str(ws)
        }
        
        meta = {
            "action": "run_only",
            "execution_time": execution_time,
            "backend_used": req.backend or "auto"
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
async def api_score(req: PipelineRequest):
    """执行评分"""
    import time
    start_time = time.time()
    ws = Path(req.workspace)
    
    try:
        # 支持动态指定scorer
        result, output_path = score_only(ws, req.params or {}, scorer_override=req.scorer)
        execution_time = time.time() - start_time
        
        payload = result.model_dump() if hasattr(result, 'model_dump') else (result.dict() if hasattr(result, 'dict') else result)
        data = {
            "score_result": payload,
            "output_path": str(output_path),
            "workspace": str(ws)
        }
        meta = {
            "action": "score_only",
            "execution_time": execution_time,
            "scorer_used": req.scorer or "auto"
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
    """执行完整流水线(推理+评分)"""
    import time
    start_time = time.time()
    ws = Path(req.workspace)

    try:
        result = run_and_score(ws, req.params or {}, backend=req.backend, scorer_override=req.scorer)
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
            "pipeline_result": result,
            "workspace": str(ws)
        }
        
        meta = {
            "action": "pipeline",
            "execution_time": execution_time,
            "backend_used": req.backend or "auto",
            "scorer_used": req.scorer or "auto"
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
def _load_celery_tasks_module():
    root = Path(__file__).resolve().parents[3]
    tasks_path = root / "celery_app" / "tasks.py"
    spec = importlib.util.spec_from_file_location("celery_tasks", str(tasks_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore
    return module


@app.post("/submit")
async def submit_job(req: SubmitRequest):
    mod = _load_celery_tasks_module()
    ws = str(Path(req.workspace))
    action = (req.action or "pipeline").lower()
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
    if action == "run":
        async_result = mod.run_job.delay(ws, req.backend, req.callback_url)
    elif action == "score":
        async_result = mod.score_job.delay(ws, req.params or {}, req.backend, req.callback_url)
    else:
        async_result = mod.run_and_score_job.delay(ws, req.params or {}, req.backend, req.callback_url)
    data = {"submitted": True, "task_id": async_result.id, "action": action, "workspace": ws}
    return make_success_response(data, {"action": "submit"})


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    mod = _load_celery_tasks_module()
    async_result = mod.celery_app.AsyncResult(task_id)
    resp = {"id": task_id, "state": async_result.state}
    try:
        if async_result.ready():
            resp["result"] = async_result.get(propagate=False)
    except Exception as e:
        resp["result"] = {"error": str(e)}
    return make_success_response(resp, {"action": "task_status"})


# for `uvicorn autoscorer.api.server:app --reload`
__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
