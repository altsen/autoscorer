from celery import Celery
from pathlib import Path
import os
import sys
from typing import Optional, Dict, Any

# 允许以项目根目录直接运行 celery worker 时正确解析包
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# 统一到 autoscorer 日志（确保已加入 sys.path 后再导入）
from autoscorer.utils.logger import get_logger, ensure_logging_configured
ensure_logging_configured()
logger = get_logger("celery")

try:
    from autoscorer.utils.config import Config
    from autoscorer.pipeline import run_only, score_only, run_and_score
    from autoscorer.utils.errors import AutoscorerError, make_error
    from autoscorer.utils.errors import maybe_print_exception, make_error_response
    from autoscorer.utils.task_store import TaskStore
except ImportError as e:
    logger.error(f"Failed to import autoscorer modules: {e}")
    logger.error(f"Python path: {sys.path}")
    logger.error(f"SRC path: {SRC}")
    raise

try:
    cfg = Config()
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    # 使用默认配置
    class DefaultConfig:
        def get(self, key, default=None):
            defaults = {
                'CELERY_BROKER': 'redis://localhost:6379/0',
                'CELERY_BACKEND': 'redis://localhost:6379/0'
            }
            return defaults.get(key, default)
    cfg = DefaultConfig()

celery_app = Celery(
    'autoscorer', 
    broker=cfg.get('CELERY_BROKER', 'redis://localhost:6379/0'), 
    backend=cfg.get('CELERY_BACKEND', 'redis://localhost:6379/0')
)
_task_store = TaskStore.from_config(cfg)

# 配置Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_reject_on_worker_lost=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
)


def _http_post_json(url: str, payload: Dict[str, Any], retries: int = 2) -> None:
    """尽量用 requests 发送，否则回退 urllib。

    非关键路径，失败不抛出，只记录日志。
    """
    attempt = 0
    last_err: Exception | None = None
    while attempt <= max(0, int(retries)):
        try:
            import requests  # type: ignore
            requests.post(url, json=payload, timeout=5)
            return
        except Exception as e:
            last_err = e
            logger.debug(f"requests not available or failed (attempt {attempt+1}): {e}")
        try:
            import json
            from urllib import request
            data = json.dumps(payload).encode('utf-8')
            req = request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with request.urlopen(req, timeout=5) as _:
                return
        except Exception as e:
            last_err = e
            logger.debug(f"urllib post failed (attempt {attempt+1}): {e}")
        # backoff
        attempt += 1
        if attempt <= retries:
            import time
            time.sleep(min(2 ** attempt, 5))
    if last_err:
        logger.warning(f"Callback POST failed after {attempt} attempts: {last_err}")


@celery_app.task(bind=True, name="autoscorer.run_job")
def run_job(self, workspace: str, backend: str | None = None, callback_url: Optional[str] = None):
    """执行推理任务"""
    try:
        logger.info(f"Starting run_job for workspace: {workspace}")
        ws = Path(workspace)
        # 标记 STARTED
        try:
            _task_store.upsert(self.request.id, action="run", workspace=str(ws), state="STARTED")
        except Exception as e:
            logger.debug(f"task_store upsert start failed: {e}")
        result = run_only(ws, backend)
        logger.info(f"Completed run_job for workspace: {workspace}")
        # 成功回调
        if callback_url:
            payload = {"ok": True, "data": {"result": result, "workspace": str(ws)}, "meta": {"task_id": self.request.id}}
            _http_post_json(callback_url, payload)
        # 持久化成功
        try:
            _task_store.upsert(self.request.id, state="SUCCESS", result={"result": result, "workspace": str(ws)}, finished=True)
        except Exception as e:
            logger.debug(f"task_store upsert success failed: {e}")
        return result
    except AutoscorerError as e:
        logger.error(f"AutoscorerError in run_job: {e.code} - {e.message}")
        error_result = make_error("run", e.code, e.message, details=e.details)
        self.update_state(state='FAILURE', meta=error_result)
        ex = Exception(f"{e.code}: {e.message}")
        maybe_print_exception(ex)
        if callback_url:
            payload = make_error_response(e.code, e.message, stage="run")
            payload["meta"]["task_id"] = self.request.id
            payload["error"]["details"] = (e.details or {})
            payload["error"]["details"].update({"workspace": workspace})
            _http_post_json(callback_url, payload)
        # 持久化失败
        try:
            _task_store.upsert(self.request.id, state="FAILURE", error={"code": e.code, "message": e.message, "details": e.details}, finished=True)
        except Exception as ex2:
            logger.debug(f"task_store upsert failure failed: {ex2}")
        raise ex
    except Exception as e:
        logger.error(f"Unexpected error in run_job: {e}")
        error_result = make_error("run", "EXEC_ERROR", str(e))
        self.update_state(state='FAILURE', meta=error_result)
        maybe_print_exception(e)
        if callback_url:
            payload = make_error_response("EXEC_ERROR", str(e), stage="run")
            payload["meta"]["task_id"] = self.request.id
            payload["error"]["details"] = {"workspace": workspace}
            _http_post_json(callback_url, payload)
        try:
            _task_store.upsert(self.request.id, state="FAILURE", error={"code": "EXEC_ERROR", "message": str(e), "details": {"workspace": workspace}}, finished=True)
        except Exception as ex2:
            logger.debug(f"task_store upsert failure failed: {ex2}")
        raise


@celery_app.task(bind=True, name="autoscorer.score_job")
def score_job(self, workspace: str, params: dict = None, backend: str | None = None, callback_url: Optional[str] = None):
    """执行评分任务"""
    try:
        logger.info(f"Starting score_job for workspace: {workspace}")
        ws = Path(workspace)
        try:
            _task_store.upsert(self.request.id, action="score", workspace=str(ws), state="STARTED")
        except Exception as e:
            logger.debug(f"task_store upsert start failed: {e}")
        # score_only 返回 (Result, Path)
        result_model, out = score_only(ws, params or {})
        # pydantic v2 序列化
        payload = (
            result_model.model_dump() if hasattr(result_model, "model_dump")
            else (result_model.dict() if hasattr(result_model, "dict") else result_model)
        )
        result = {"result": payload, "output_path": str(out), "workspace": str(ws)}
        logger.info(f"Completed score_job for workspace: {workspace}")
        if callback_url:
            cb = {"ok": True, "data": result, "meta": {"task_id": self.request.id}}
            _http_post_json(callback_url, cb)
        try:
            _task_store.upsert(self.request.id, state="SUCCESS", result=result, finished=True)
        except Exception as e:
            logger.debug(f"task_store upsert success failed: {e}")
        return result
    except AutoscorerError as e:
        logger.error(f"AutoscorerError in score_job: {e.code} - {e.message}")
        error_result = make_error("score", e.code, e.message, details=e.details)
        self.update_state(state='FAILURE', meta=error_result)
        ex = Exception(f"{e.code}: {e.message}")
        maybe_print_exception(ex)
        if callback_url:
            payload = make_error_response(e.code, e.message, stage="score")
            payload["meta"]["task_id"] = self.request.id
            payload["error"]["details"] = (e.details or {})
            payload["error"]["details"].update({"workspace": workspace})
            _http_post_json(callback_url, payload)
        try:
            _task_store.upsert(self.request.id, state="FAILURE", error={"code": e.code, "message": e.message, "details": e.details}, finished=True)
        except Exception as ex2:
            logger.debug(f"task_store upsert failure failed: {ex2}")
        raise ex
    except Exception as e:
        logger.error(f"Unexpected error in score_job: {e}")
        error_result = make_error("score", "SCORE_ERROR", str(e))
        self.update_state(state='FAILURE', meta=error_result)
        maybe_print_exception(e)
        if callback_url:
            payload = make_error_response("SCORE_ERROR", str(e), stage="score")
            payload["meta"]["task_id"] = self.request.id
            payload["error"]["details"] = {"workspace": workspace}
            _http_post_json(callback_url, payload)
        try:
            _task_store.upsert(self.request.id, state="FAILURE", error={"code": "SCORE_ERROR", "message": str(e), "details": {"workspace": workspace}}, finished=True)
        except Exception as ex2:
            logger.debug(f"task_store upsert failure failed: {ex2}")
        raise


@celery_app.task(bind=True, name="autoscorer.run_and_score_job")
def run_and_score_job(self, workspace: str, params: dict = None, backend: str | None = None, callback_url: Optional[str] = None):
    """执行完整流水线任务(推理+评分)"""
    try:
        logger.info(f"Starting run_and_score_job for workspace: {workspace}")
        ws = Path(workspace)
        try:
            _task_store.upsert(self.request.id, action="pipeline", workspace=str(ws), state="STARTED")
        except Exception as e:
            logger.debug(f"task_store upsert start failed: {e}")
        result = run_and_score(ws, params or {}, backend)
        logger.info(f"Completed run_and_score_job for workspace: {workspace}")
        if callback_url:
            payload = {"ok": True, "data": {"result": result, "workspace": str(ws)}, "meta": {"task_id": self.request.id}}
            _http_post_json(callback_url, payload)
        try:
            _task_store.upsert(self.request.id, state="SUCCESS", result={"result": result, "workspace": str(ws)}, finished=True)
        except Exception as e:
            logger.debug(f"task_store upsert success failed: {e}")
        return result
    except AutoscorerError as e:
        logger.error(f"AutoscorerError in run_and_score_job: {e.code} - {e.message}")
        error_result = make_error("pipeline", e.code, e.message, details=e.details)
        self.update_state(state='FAILURE', meta=error_result)
        ex = Exception(f"{e.code}: {e.message}")
        maybe_print_exception(ex)
        if callback_url:
            payload = make_error_response(e.code, e.message, stage="pipeline")
            payload["meta"]["task_id"] = self.request.id
            payload["error"]["details"] = (e.details or {})
            payload["error"]["details"].update({"workspace": workspace})
            _http_post_json(callback_url, payload)
        try:
            _task_store.upsert(self.request.id, state="FAILURE", error={"code": e.code, "message": e.message, "details": e.details}, finished=True)
        except Exception as ex2:
            logger.debug(f"task_store upsert failure failed: {ex2}")
        raise ex
    except Exception as e:
        logger.error(f"Unexpected error in run_and_score_job: {e}")
        error_result = make_error("pipeline", "PIPELINE_ERROR", str(e))
        self.update_state(state='FAILURE', meta=error_result)
        maybe_print_exception(e)
        if callback_url:
            payload = make_error_response("PIPELINE_ERROR", str(e), stage="pipeline")
            payload["meta"]["task_id"] = self.request.id
            payload["error"]["details"] = {"workspace": workspace}
            _http_post_json(callback_url, payload)
        try:
            _task_store.upsert(self.request.id, state="FAILURE", error={"code": "PIPELINE_ERROR", "message": str(e), "details": {"workspace": workspace}}, finished=True)
        except Exception as ex2:
            logger.debug(f"task_store upsert failure failed: {ex2}")
        raise
